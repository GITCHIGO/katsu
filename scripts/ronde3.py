"""
Ronde 3 (docs/onderzoeksplan_edge.md §12): order block, Fibonacci/OTE, RSI-divergentie, BPR, exhaustion-FVG,
range-FVG en equal highs/lows — laag 1 op de VERKENNINGSHELFT, hoofdmaat R15.

Gebruik: python -m scripts.ronde3 <map met htf-pickles> <uitmap>
Schrijft: <uitmap>/events_ronde3.pkl en research/register_ronde3.csv
"""
import os
import sys
import time

import numpy as np
import pandas as pd

from katsu import blocks as B
from katsu import research as R
from katsu.structure import atr
from scripts.ronde1 import COST, MARKETS, TFS, load
from scripts.ronde1_poort import gate, rows_for

VARIANTS = {
    "OB": [("alle", None, ""), ("TF+1 mee", "htf1_mee", "_h1"), ("met FVG", "fvg", "")],
    "Fib 61,8": [("alle", None, ""), ("TF+1 mee", "htf1_mee", "_h1")],
    "Fib 70,5": [("alle", None, "")],
    "RSI-divergentie": [("alle", None, ""), ("RSI extreem", "extreem", ""), ("TF+1 mee", "htf1_mee", "_h1")],
    "BPR": [("alle", None, "")],
    "Exhaustion-FVG": [("alle", None, "")],
    "Range-FVG": [("TF+1 neutraal", "htf1_neutraal", "_h1")],
    "Equal highs/lows": [("alle", None, ""), ("TF+1 mee", "htf1_mee", "_h1")],
}


def events_for(bars, tf, a):
    rows = []

    def add(df, fam, L=None):
        if df is not None and len(df):
            df = df.copy(); df["fam"], df["L"] = fam, L; rows.append(df)

    for L in (1, 3, 5):
        add(B.ob_events(bars, tf, L), "OB", L)
        add(B.fib_events(bars, tf, L, 0.618), "Fib 61,8", L)
        add(B.fib_events(bars, tf, L, 0.705), "Fib 70,5", L)
    for L in (3, 5):
        rd = B.rsi_div_events(bars, L)
        rd["extreem"] = np.where(rd.d > 0, rd.rsi2 < 30, rd.rsi2 > 70)
        add(rd, "RSI-divergentie", L)
    add(B.bpr_events(bars), "BPR")
    add(B.exhaustion_events(bars, a), "Exhaustion-FVG")
    add(R.fvg_events(bars)["vorming"], "Range-FVG")
    add(B.equal_sweep_events(bars, a, L=3), "Equal highs/lows", 3)
    ev = pd.concat(rows, ignore_index=True)
    for col in ("entry_bar", "entry_price", "fvg", "extreem", "sweep"):
        if col not in ev:
            ev[col] = np.nan
    return ev


def main(folder, outdir):
    os.makedirs(outdir, exist_ok=True)
    allev = []
    for sym in MARKETS:
        for tfn, tf in TFS.items():
            t0 = time.time()
            bars = load(folder, sym, tfn)
            a = atr(bars, 14).to_numpy()
            n = len(bars)
            explore = R.explore_mask(bars.index)
            h1, h2 = (R.htf_trend(bars, tf, r) for r in R.HTF[tf])
            ev = events_for(bars, tf, a)
            k = ev.k.to_numpy(int)
            ev = ev[(k < n) & explore[np.minimum(k, n - 1)]].reset_index(drop=True)
            k = ev.k.to_numpy(int); d = ev.d.to_numpy(int)
            want = np.where(d > 0, "UP", "DOWN")
            ev["htf1_mee"] = h1[k] == want
            ev["htf1_neutraal"] = h1[k] == "NEUTRAL"
            ev["htf2_mee"] = (h2[k] == want) & ev["htf1_mee"].to_numpy()
            ev["disp"] = R.displacement(bars, a, k)
            ev["fvg3"] = R.fvg_recent(bars, k, d)
            ev["time"] = bars.index[k]
            limit = ev.entry_bar.notna().to_numpy()
            m = R.measure(bars, a, k, d)
            if limit.any():
                ml = R.measure(bars, a, k[limit], d[limit], entry_bar=ev.entry_bar[limit].to_numpy(int),
                               entry_price=ev.entry_price[limit].to_numpy(float))
                m.loc[limit, :] = ml.to_numpy()
            ev = pd.concat([ev, m], axis=1)
            pool = np.where(explore[: n - 49])[0]
            for tag, strata in (("", None), ("_h1", h1)):
                bl = R.baseline(bars, a, k, d, pool, strata=strata, per_event=5, seed=31)
                for col, src in (("base", "R21"), ("base15", "R15"), ("base11", "R11")):
                    ev[col + tag] = np.nanmean(bl[src].to_numpy().reshape(-1, 5), axis=1)
            ev["market"], ev["tf"] = sym, tfn
            ev["cost_R"] = COST[sym] / np.nanmedian(a[explore])
            allev.append(ev)
            print(f"{sym} {tfn}: {len(ev)} gebeurtenissen ({time.time() - t0:.0f}s)", flush=True)
    ev = pd.concat(allev, ignore_index=True)
    ev.to_pickle(os.path.join(outdir, "events_ronde3.pkl"))
    reg = gate(rows_for(ev, "R15", VARIANTS))
    reg.to_csv("research/register_ronde3.csv", index=False, float_format="%.4f")
    print(f"{len(reg)} combinaties; {int(reg.poort.sum())} door de poort")


if __name__ == "__main__":
    main(*sys.argv[1:3])
