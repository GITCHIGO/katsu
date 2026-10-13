"""
Test AMD / Power of 3 (docs/spec_v0.6.md §3). Verkenningsdata: vóór 2025 (FX 2010–19, goud 2016–19, oneven maanden
2020–24) en 2025 – okt 2026. Even maanden 2020–24 blijven dicht.
Gebruik: python -m scripts.amd_test <htf-map> <uitmap>
"""
import itertools
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

from katsu import research as R
from katsu.amd import amd_setups, make_amd_plan
from katsu.execution import M1, simulate
from katsu.structure import atr
from scripts.dashboard_build import free, placebo_plan
from scripts.eindtest_gfvg import final_mask, load_full
from scripts.gfvg_test import INS
from scripts.ronde1 import load

MARKETS = ("EURUSD", "GBPUSD", "XAUUSD")
VARIANTS = list(itertools.product(("range", "open"), ("market", "fvg"), (False, True)))
LAB = {"range": "C1", "open": "C2", "market": "E1", "fvg": "E2", False: "B0", True: "B1"}
PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.1}


def vname(v):
    return "-".join(LAB[x] for x in v)


def gate(s):
    return bool(s["n"] >= 100 and s["R"] >= 0.10 and s["t"] >= 2.0 and s["R_voor"] > 0 and s["R_na"] > 0
                and s["vrij"] > s["plac_vrij"])


def periods(folder, mkt):
    yield "vóór 2025", load(folder, mkt, "M15"), R.explore_mask
    yield "2025–26", load_full(folder, mkt), final_mask


def describe(bars, mask):
    """Premisse: valt de low/high van de dag in het venster; sluit de dag boven de midnight open."""
    t = bars.index; m = (t.hour * 60 + t.minute)
    df = pd.DataFrame({"h": bars.high.values, "l": bars.low.values, "c": bars.close.values, "o": bars.open.values,
                       "day": t.normalize(), "min": m, "ok": mask(t)})
    g = df.groupby("day")
    rows = []
    for day, d in g:
        if not d.ok.any() or (d["min"] == 420).sum() == 0 or len(d) < 80:
            continue
        mo = d.o[d["min"] == 420].iloc[0]
        win = (d["min"] >= 420) & (d["min"] < 720)
        rows.append({"day": day, "low_in_win": d.l.idxmin() in d.index[win], "high_in_win": d.h.idxmax() in d.index[win],
                     "close_above_mo": d.c.iloc[-1] > mo, "mo": mo})
    return pd.DataFrame(rows).set_index("day")


def run(folder, outdir, seed=20261013):
    os.makedirs(outdir, exist_ok=True)
    rng = np.random.default_rng(seed)
    rows, desc = [], []
    for mkt in MARKETS:
        for per, bars, mask in periods(folder, mkt):
            a = atr(bars, 14).to_numpy()
            d1 = R.htf_trend(bars, "15min", "1D")
            ins = replace(INS[mkt], min_sl_atr=0.0, max_hold_days=None, close_eod=True)
            insf = free(ins)
            M, Mf = M1(bars, ins), M1(bars, insf)
            ok = mask(bars.index) & np.isfinite(a)
            slot = (bars.index.hour * 60 + bars.index.minute).to_numpy()
            pool = {k: np.nonzero(ok & (slot == k))[0] for k in np.unique(slot)}
            dd = describe(bars, mask); dd["markt"] = mkt; dd["periode"] = per; desc.append(dd)
            for v in VARIANTS:
                conf, ent, bias = v
                S = amd_setups(bars, conf, ent, trend=d1 if bias else None, day_mask=mask)
                for s in S:
                    if not np.isfinite(a[s.k_conf]):
                        continue
                    p = make_amd_plan(s, bars, a, mkt)
                    tr = simulate(p, M, ins)
                    trf = simulate(p, Mf, insf)
                    row = {"markt": mkt, "periode": per, "variant": vname(v), "richting": s.direction, "dag": s.day,
                           "status": tr.status, "uitkomst": tr.exit_reason, "r_net": tr.r_net,
                           "r_free": trf.r_net if trf.status == "gesloten" else np.nan,
                           "entry_time": tr.entry_time, "risk_pips": (tr.risk / PIP[mkt]) if tr.risk else np.nan,
                           "asia_pips": (s.asia_hi - s.asia_lo) / PIP[mkt], "r_placebo_free": np.nan}
                    if tr.status == "gesloten":
                        k_fill = int(bars.index.searchsorted(tr.entry_time, side="right") - 1)
                        cand = pool.get(int(slot[k_fill]), np.array([], int))
                        cand = cand[(np.abs(cand - k_fill) >= 96 * 5) & (cand + 1 < len(bars))]
                        if len(cand):
                            i = int(cand[rng.integers(len(cand))])
                            tp_dist = abs(tr.tp - tr.fill)
                            sgn = 1 if s.direction == "LONG" else -1
                            pf = simulate(placebo_plan(sgn, insf, Mf, bars, i, trf.risk if trf.risk else tr.risk,
                                                       tp_dist, a[i], mkt), Mf, insf)
                            row["r_placebo_free"] = pf.r_net if pf.status == "gesloten" else np.nan
                    rows.append(row)
            print(mkt, per, "klaar", flush=True)
    df = pd.DataFrame(rows)
    wk = pd.to_datetime(df.dag).dt.isocalendar()
    df["week"] = (wk.year * 100 + wk.week).astype(int)
    df.to_pickle(os.path.join(outdir, "amd_trades.pkl"))
    pd.concat(desc).to_pickle(os.path.join(outdir, "amd_dagen.pkl"))
    return df


def summarize(df):
    from katsu.dashboard_calc import clustered_t
    out = []
    for v, g in df.groupby("variant", sort=False):
        f = g[g.status == "gesloten"]
        s = {"variant": v, "setups": len(g), "n": len(f), "win": (f.r_net > 0).mean(), "R": f.r_net.mean(),
             "t": clustered_t(f.r_net.to_numpy(), f.week.to_numpy()), "vrij": f.r_free.mean(),
             "plac_vrij": f.r_placebo_free.mean(),
             "R_voor": f[f.periode == "vóór 2025"].r_net.mean(), "n_voor": int((f.periode == "vóór 2025").sum()),
             "R_na": f[f.periode == "2025–26"].r_net.mean(), "n_na": int((f.periode == "2025–26").sum())}
        for m in MARKETS:
            s["R_" + m] = f[f.markt == m].r_net.mean()
        s["poort"] = gate(s)
        out.append(s)
    return pd.DataFrame(out)


if __name__ == "__main__":
    d = run(*sys.argv[1:3])
    r = summarize(d)
    os.makedirs("research", exist_ok=True)
    r.to_csv("research/register_amd.csv", index=False, float_format="%.4f")
    print(r.round(3).to_string())
