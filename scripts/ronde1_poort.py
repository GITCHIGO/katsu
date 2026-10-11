"""
Laag 1, ronde 1: poort toepassen en het testregister schrijven (docs/onderzoeksplan_edge.md §9).

Gebruik: python -m scripts.ronde1_poort <events_ronde1.pkl> <register.csv> [R21|R15]
(kolomnamen R21/basis_R21 in het register bevatten de gekozen maat; zie kolom 'maat')
"""
import sys

import numpy as np
import pandas as pd

from katsu.research import clustered_t

# Vooraf vastgelegde varianten per familie (plan §9) en hun basislijn-kolom
VARIANTS = {
    "BOS": [("alle", None, ""), ("displacement", "disp", ""), ("TF+1 mee", "htf1_mee", "_h1"),
            ("TF+1 en TF+2 mee", "htf2_mee", "_h12")],
    "CHoCH": [("alle", None, ""), ("displacement", "disp", ""), ("MSS", "mss", ""),
              ("TF+1 mee", "htf1_mee", "_h1"), ("met sweep", "sweep", "")],
    "sweep_swing": [("alle", None, ""), ("TF+1 mee", "htf1_mee", "_h1")],
    "sweep_dag": [("alle", None, ""), ("TF+1 mee", "htf1_mee", "_h1")],
    "sweep_week": [("alle", None, ""), ("TF+1 mee", "htf1_mee", "_h1")],
    "sweep_azie": [("alle", None, ""), ("TF+1 mee", "htf1_mee", "_h1")],
    "FVG_vorming": [("alle", None, ""), ("TF+1 mee", "htf1_mee", "_h1")],
    "FVG_retest": [("TF+1 mee", "htf1_mee", "_h1")],
    "FVG_inverse": [("alle", None, "")],
}
MIN_N = 100


def rows_for(ev, metric="R21", variants=None):
    """metric = "R21" (TP 2 ATR) of "R15" (TP 1,5 ATR); SL is altijd 1 ATR."""
    bcol = {"R21": "base", "R15": "base15"}[metric]
    ev = ev.copy()
    ev["mss"] = ev["disp"].astype(bool) & ev["fvg3"].astype(bool)
    ev["sweep"] = ev["sweep"].fillna(False).astype(bool)
    wk = ev["time"].dt.isocalendar()
    ev["week"] = wk.year.astype(int) * 100 + wk.week.astype(int)
    ev["jaar"] = ev["time"].dt.year
    out = []
    variants = variants or VARIANTS
    for (mkt, tf, fam, L), g in ev.groupby(["market", "tf", "fam", ev["L"].fillna(0)], sort=False):
        for vname, col, btag in variants[fam]:
            s = g if col is None else g[g[col].astype(bool)]
            s = s[s[metric].notna() & s[bcol + btag].notna()]
            diff = (s[metric] - s[bcol + btag]).to_numpy()
            m, se = clustered_t(diff, s.week.to_numpy())
            pre = diff[s.jaar.to_numpy() < 2020]; post = diff[s.jaar.to_numpy() >= 2020]
            yrs = pd.Series(diff).groupby(s.jaar.to_numpy()).agg(["mean", "size"])
            yrs = yrs[yrs["size"] >= 10]
            out.append({
                "markt": mkt, "tf": tf, "familie": fam, "L": int(L) if L else None, "variant": vname,
                "n": len(s), "R21": s[metric].mean(), "basis_R21": s[bcol + btag].mean(), "edge": m,
                "maat": metric, "winrate": float((s[metric] >= {"R21": 2.0, "R15": 1.5}[metric]).mean()) if len(s) else np.nan,
                "se": se, "t": m / se if se and se > 0 else np.nan,
                "R11": s.R11.mean(), "edge_R11": (s.R11 - s["base11" + btag]).mean(),
                "fwd12_atr": s.fwd12.mean(), "kosten_R": s.cost_R.iloc[0] if len(s) else np.nan,
                "edge_voor_2020": pre.mean() if len(pre) >= 20 else np.nan,
                "edge_2020_24": post.mean() if len(post) >= 20 else np.nan,
                "jaren_zelfde_teken": float((np.sign(yrs["mean"]) == np.sign(m)).mean()) if len(yrs) else np.nan,
                "aantal_jaren": len(yrs),
            })
    return pd.DataFrame(out)


def gate(reg):
    reg = reg.copy()
    key = ["tf", "familie", "L", "variant"]
    # steun van andere markten: zelfde combinatie, zelfde teken, t >= 1
    sup = []
    for i, r in reg.iterrows():
        o = reg[(reg.tf == r.tf) & (reg.familie == r.familie) & (reg.L.fillna(0) == (r.L or 0)) &
                (reg.variant == r.variant) & (reg.markt != r.markt)]
        sup.append(int(((np.sign(o.t) == np.sign(r.t)) & (o.t.abs() >= 1)).sum()))
    reg["andere_markten_mee"] = sup
    # buren: andere L, zelfde markt/tf/familie/variant, zelfde teken
    bur = []
    for i, r in reg.iterrows():
        if pd.isna(r.L):
            bur.append(np.nan); continue
        o = reg[(reg.markt == r.markt) & (reg.tf == r.tf) & (reg.familie == r.familie) & (reg.variant == r.variant)]
        if len(o) < 2:                       # maar één waarde van L getest: geen buren om te vergelijken
            bur.append(np.nan); continue
        bur.append(int((np.sign(o.edge) == np.sign(r.edge)).sum()))   # inclusief zichzelf
    reg["L_zelfde_teken"] = bur
    need_t = np.where(reg.andere_markten_mee >= 1, 3.0, 3.5)
    halves_ok = reg.edge_voor_2020.isna() | reg.edge_2020_24.isna() | \
        (np.sign(reg.edge_voor_2020) == np.sign(reg.edge_2020_24))
    net = np.where(reg.edge > 0, reg.R21 - reg.kosten_R, -reg.R11 - reg.kosten_R)
    reg["netto_na_kosten"] = net
    reg["poort"] = (reg.n >= MIN_N) & (reg.t.abs() >= need_t) & halves_ok & \
        (reg.jaren_zelfde_teken > 0.5) & (reg.L_zelfde_teken.isna() | (reg.L_zelfde_teken >= 2)) & (net >= 0.05)
    reg["richting"] = np.where(reg.edge > 0, "mee", "omgekeerd")
    return reg


def main(evpath, regpath, metric="R21"):
    ev = pd.read_pickle(evpath)
    reg = gate(rows_for(ev, metric))
    reg.to_csv(regpath, index=False, float_format="%.4f")
    print(f"{len(reg)} combinaties getest; {int(reg.poort.sum())} door de poort")
    cols = ["markt", "tf", "familie", "L", "variant", "n", "R21", "basis_R21", "edge", "t", "netto_na_kosten",
            "andere_markten_mee", "jaren_zelfde_teken"]
    with pd.option_context("display.width", 250, "display.max_rows", 100):
        print(reg[reg.poort][cols].round(3).to_string(index=False))
        print("\nsterkste |t| (ongeacht poort):")
        print(reg.reindex(reg.t.abs().sort_values(ascending=False).index)[cols].head(40).round(3).to_string(index=False))


if __name__ == "__main__":
    main(*sys.argv[1:4])
