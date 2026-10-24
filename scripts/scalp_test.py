"""
Spec v0.8 — verkenning (de poort). Gebruik: python -m scripts.scalp_test <uitmap>
Periodes: A = 2025 – 9 okt 2026 · B = oneven maanden 2020–2024. De even maanden 2020–2024 worden NIET berekend
(eindtest, één keer, pas na de poort).
"""
import json
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

from katsu import scalp
from katsu.dashboard_calc import clustered_t
from katsu.execution import EURUSD, XAUUSD, M1, OrderPlan, simulate

SRC = {"EURUSD": "/home/claude/katsu_research/eur_m1_full.pkl", "XAUUSD": "/home/claude/katsu_research/xau_m1_full.pkl"}
INS = {m: replace(i, min_sl_atr=0.0, close_at_min=scalp.CLOSE_AT_MIN) for m, i in (("EURUSD", EURUSD), ("XAUUSD", XAUUSD))}
FREE = {m: replace(i, min_spread=0.0, slip=0.0, commission=0.0, swap=0.0, swap_short=0.0, rollover_min_spread=0.0,
                   point=0.0) for m, i in INS.items()}
END = pd.Timestamp("2026-10-10")
PERIODS = {
    "A_2025_26": lambda t: (t >= "2025-01-01") & (t < END),
    "B_oneven_2020_24": lambda t: (t.year >= 2020) & (t.year <= 2024) & (t.month % 2 == 1),
}


def one_at_a_time(rows):
    rows = sorted(rows, key=lambda r: r["fill_time"])
    last, keep = None, []
    for r in rows:
        if last is not None and r["fill_time"] < last:
            continue
        last = r["exit_time"]
        keep.append(r)
    return keep


def ambiguous(tr, d: M1) -> bool:
    """SL en TP in dezelfde M1-candle bij een SL-uitstap (de motor nam de SL)."""
    if tr.exit_reason != "SL":
        return False
    k = int(d.t.searchsorted(tr.exit_time))
    if tr.direction == "LONG":
        return d.h[k] >= tr.tp
    return d.lo[k] + d.sp[k] <= tr.tp


def run(mkt, rng):
    m1 = pd.read_pickle(SRC[mkt])
    m1 = m1[m1.index < END]
    f = scalp.features(m1)
    d, dfree = M1(m1, INS[mkt]), M1(m1, FREE[mkt])
    out = {}
    for pname, pf in PERIODS.items():
        allow = np.asarray(pf(pd.DatetimeIndex(f["t_close"])))
        sig = scalp.signals(f, mkt, allow)
        # handelsdagen van deze periode (voor de placebo): weekdagen met data
        days = pd.DatetimeIndex(np.unique(f.index[allow & (f.index.dayofweek < 5)].normalize()))
        for v, plans in sig.items():
            rows = []
            for p in plans:
                tr = simulate(p, d, INS[mkt])
                if tr.status != "gesloten":
                    continue
                trf = simulate(p, dfree, FREE[mkt])
                rows.append({"markt": mkt, "variant": v, "periode": pname, "richting": tr.direction,
                             "signal_time": p.signal_time, "fill_time": tr.entry_time, "exit_time": tr.exit_time,
                             "fill": tr.fill, "sl": tr.sl, "tp": tr.tp, "risk": tr.risk, "reden": tr.exit_reason,
                             "r_net": tr.r_net, "r_gross": tr.r_gross, "kosten_r": tr.cost_r,
                             "r_free": trf.r_net if trf.status == "gesloten" else np.nan,
                             "twijfel": ambiguous(tr, d)})
            rows = one_at_a_time(rows)
            for r in rows:                        # placebo: zelfde uur/kwartier, willekeurige andere handelsdag
                tod = r["signal_time"] - r["signal_time"].normalize()
                for _ in range(5):
                    t = days[rng.integers(len(days))] + tod
                    if t.normalize() == r["signal_time"].normalize():
                        continue
                    i = int(dfree.t.searchsorted(t))
                    if i >= len(dfree.t) or dfree.t[i] - t > pd.Timedelta(minutes=5):
                        continue
                    s = 1.0 if r["richting"] == "LONG" else -1.0
                    fill = dfree.o[i]
                    pl = OrderPlan(r["richting"], t, "market", float(fill - s * r["risk"]), 0.0, market=mkt,
                                   tp_price=float(fill + s * abs(r["tp"] - r["fill"])))
                    pt = simulate(pl, dfree, FREE[mkt])
                    r["r_placebo_free"] = pt.r_net if pt.status == "gesloten" else np.nan
                    break
                else:
                    r["r_placebo_free"] = np.nan
            out[(pname, v)] = rows
    return out


def summary(rows):
    if not rows:
        return {"trades": 0}
    df = pd.DataFrame(rows)
    x = df["r_net"].to_numpy(float)
    week = pd.to_datetime(df["fill_time"]).dt.to_period("W").astype(str).to_numpy()
    ndays = pd.to_datetime(df["fill_time"]).dt.normalize().nunique()
    s = {"trades": len(df), "dagen_met_trade": int(ndays), "winrate": float((x > 0).mean()), "gem_R": float(x.mean()),
         "t": clustered_t(x, week), "zonder_kosten": float(df["r_free"].mean()),
         "placebo_zonder_kosten": float(df["r_placebo_free"].mean()), "kosten_R": float(df["kosten_r"].mean()),
         "twijfel": float(df["twijfel"].mean()), "totaal_R": float(x.sum()),
         "per_markt": {m: {"n": int(len(g)), "gem_R": float(g["r_net"].mean())} for m, g in df.groupby("markt")},
         "per_jaar": {str(y): {"n": int(len(g)), "gem_R": float(g["r_net"].mean())}
                      for y, g in df.groupby(pd.to_datetime(df["fill_time"]).dt.year)},
         "uitstap": df["reden"].value_counts().to_dict()}
    return s


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    rng = np.random.default_rng(20261024)
    allrows = {}
    for mkt in ("EURUSD", "XAUUSD"):
        for k, rows in run(mkt, rng).items():
            allrows.setdefault(k, []).extend(rows)
    res = {}
    for (pname, v), rows in sorted(allrows.items()):
        res.setdefault(v, {})[pname] = summary(rows)
    for v, r in res.items():
        a, b = r.get("A_2025_26", {}), r.get("B_oneven_2020_24", {})
        gate = {
            "1_trades_ge_300": a.get("trades", 0) >= 300,
            "2_gem_ge_0.10": a.get("gem_R", -9) >= 0.10,
            "2_t_ge_2": (a.get("t") or -9) >= 2.0,
            "3_beter_dan_placebo": a.get("zonder_kosten", -9) > a.get("placebo_zonder_kosten", 9),
            "4_B_niet_negatief": b.get("gem_R", -9) >= 0.0,
            "5_twijfel_le_5pct": a.get("twijfel", 1) <= 0.05,
        }
        r["poort"] = gate
        r["geslaagd"] = all(gate.values())
    pd.DataFrame([r for rows in allrows.values() for r in rows]).to_pickle(os.path.join(outdir, "scalp_trades.pkl"))
    with open(os.path.join(outdir, "scalp_resultaat.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1])
