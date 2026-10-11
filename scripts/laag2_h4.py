"""
Laag 2 voor de beste H4-aanwijzingen (docs/onderzoeksplan_edge.md §10), alleen op de VERKENNINGSHELFT.

Gebruik: python -m scripts.laag2_h4 <map met htf-pickles> <uitmap>
Schrijft: <uitmap>/laag2_h4_trades.pkl en research/register_laag2_h4.csv
"""
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

from katsu import research as R
from katsu.backtest import metrics
from katsu.execution import EURUSD, M1, Instrument, OrderPlan, run_portfolio
from katsu.structure import atr
from scripts.ronde1 import load

GBPUSD = Instrument("GBPUSD", tick=0.00001, point=0.00001, min_spread=0.00003, slip=0.00003,
                    commission=0.00008, swap=0.00008, swap_short=0.00008, rollover_min_spread=0.00005)
INS = {"EURUSD": EURUSD, "GBPUSD": GBPUSD}
CANDIDATES = [  # (markt, familie, L, variant) — plan §10
    ("GBPUSD", "BOS", 1, "TF+1 mee"),
    ("EURUSD", "CHoCH", 3, "alle"),
    ("EURUSD", "CHoCH", 3, "displacement"),
    ("EURUSD", "CHoCH", 3, "TF+1 mee"),
    ("GBPUSD", "CHoCH", 5, "alle"),
    ("GBPUSD", "FVG_vorming", None, "TF+1 mee"),
]


def events(bars, fam, L):
    if fam == "BOS":
        return R.bos_events(bars, "4h", L)
    if fam == "CHoCH":
        return R.choch_events(bars, L)
    return R.fvg_events(bars)["vorming"]


def run_candidate(folder, mkt, fam, L, variant, rr):
    bars = load(folder, mkt, "H4")
    a = atr(bars, 14).to_numpy()
    ev = events(bars, fam, L)
    ev = ev[R.explore_mask(bars.index[ev.k.to_numpy(int)])].reset_index(drop=True)
    k = ev.k.to_numpy(int); d = ev.d.to_numpy(int)
    if variant == "displacement":
        keep = R.displacement(bars, a, k)
    elif variant == "TF+1 mee":
        d1 = R.htf_trend(bars, "4h", "1D")
        keep = d1[k] == np.where(d > 0, "UP", "DOWN")
    else:
        keep = np.ones(len(ev), bool)
    ev = ev[keep].reset_index(drop=True)
    k = ev.k.to_numpy(int); d = ev.d.to_numpy(int)
    anchor = R.structural_anchor(bars, fam, ev)
    ins = replace(INS[mkt], rr=rr)
    plans = [OrderPlan("LONG" if dd > 0 else "SHORT", bars.index[kk] + pd.Timedelta("4h"), "market",
                       float(an), float(a[kk]), market=mkt, max_cost_r=0.2)
             for kk, dd, an in zip(k, d, anchor) if np.isfinite(a[kk])]
    m15 = load(folder, mkt, "M15")
    out = run_portfolio(plans, {mkt: M1(m15, ins)}, {mkt: ins})
    out["kandidaat"] = f"{mkt} {fam} L{L or '-'} {variant}"
    out["rr"] = rr
    return out


def summarize(tr):
    g = tr[tr.status == "gesloten"].sort_values("entry_time").copy()
    g["jaar"] = g.entry_time.dt.year
    wk = g.entry_time.dt.isocalendar()
    m, se = R.clustered_t(g.r_net.to_numpy(float), (wk.year * 100 + wk.week).to_numpy())
    pre = g[g.jaar < 2020].r_net.mean(); post = g[g.jaar >= 2020].r_net.mean()
    yrs = g.groupby("jaar").r_net.mean()
    base = metrics(g.r_net)
    return {**base, "t": m / se if se else np.nan, "voor_2020": pre, "2020_24": post,
            "jaren_positief": float((yrs > 0).mean()), "aantal_jaren": len(yrs),
            "statussen": tr.status.value_counts().to_dict()}


def main(folder, outdir):
    os.makedirs(outdir, exist_ok=True)
    rows, alltr = [], []
    for mkt, fam, L, variant in CANDIDATES:
        for rr in (1.5, 2.0):
            tr = run_candidate(folder, mkt, fam, L, variant, rr)
            alltr.append(tr)
            s = summarize(tr)
            s.update({"kandidaat": tr.kandidaat.iloc[0], "rr": rr})
            s["poort"] = bool(rr == 1.5 and s["trades"] >= 100 and s["gem_r"] >= 0.10 and s["t"] >= 2.0
                              and s["voor_2020"] > 0 and s["2020_24"] > 0 and s["jaren_positief"] > 0.5)
            rows.append(s)
            print(f"{s['kandidaat']:40s} RR {rr}: n={s['trades']} win={s['winrate']:.2f} gem={s['gem_r']:+.3f} "
                  f"t={s['t']:.2f} <2020={s['voor_2020']:+.3f} 2020+={s['2020_24']:+.3f} "
                  f"jaren+={s['jaren_positief']:.2f} maxDD={s['max_dd']:.1f} poort={s['poort']}", flush=True)
    pd.concat(alltr).to_pickle(os.path.join(outdir, "laag2_h4_trades.pkl"))
    pd.DataFrame(rows).to_csv("research/register_laag2_h4.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main(*sys.argv[1:3])
