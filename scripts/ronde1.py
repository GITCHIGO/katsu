"""
Laag 1, ronde 1 (docs/onderzoeksplan_edge.md §9): signaalonderzoek op de VERKENNINGSHELFT.

Gebruik: python -m scripts.ronde1 <map met htf-pickles> <uitmap>
Schrijft: <uitmap>/events_ronde1.pkl (elke gebeurtenis met meting en gepaarde basislijn)
          research/register_ronde1.csv (testregister: één rij per geteste combinatie, met poort-uitslag)
Alles vanaf 1 jan 2025 wordt weggesneden vóór er iets berekend wordt.
"""
import glob
import os
import sys
import time

import numpy as np
import pandas as pd

from katsu import research as R
from katsu.structure import atr

MARKETS = ["XAUUSD", "EURUSD", "GBPUSD", "XAGUSD", "US500"]
TFS = {"M15": "15min", "H1": "1h", "H4": "4h"}
START = {"XAUUSD": "2016-02-01", "XAGUSD": "2016-02-01", "US500": "2016-02-08",
         "EURUSD": "2010-01-04", "GBPUSD": "2010-01-04"}
# Kosten per trade in prijs (spread + 2 × slippage + commissie), benaderend, vooraf vastgelegd
COST = {"XAUUSD": 0.10 + 2 * 0.25 + 0.08, "EURUSD": 0.00002 + 2 * 0.00003 + 0.00008,
        "GBPUSD": 0.00005 + 2 * 0.00003 + 0.00008, "XAGUSD": 0.010 + 2 * 0.005 + 0.002,
        "US500": 0.50 + 2 * 0.25}
LS = (1, 3, 5)
END = pd.Timestamp("2025-01-01")


def load(folder, sym, tf):
    fs = sorted(glob.glob(os.path.join(folder, f"{sym}_{tf}_*.pkl")))
    df = pd.read_pickle(fs[0]) if fs else None
    if df is not None and df.index[0] > pd.Timestamp(START[sym]) + pd.Timedelta(days=30):
        df = None                          # bestand begint te laat (EURUSD-H4 pas in 2020)
    if df is not None:
        pass
    elif tf == "H4":                       # bouw H4 uit H1 (zelfde servertijd, zelfde grenzen)
        h1 = load(folder, sym, "H1")
        agg = {"open": "first", "high": "max", "low": "min", "close": "last", "tickvol": "sum", "spread": "max"}
        df = h1.resample("4h", label="left", closed="left").agg(agg).dropna(subset=["open"])
    else:
        raise FileNotFoundError(sym + tf)
    df = df[(df.index >= START[sym]) & (df.index < END)]
    return df


def events_for(bars, tf, a):
    """Alle gebeurtenissen van ronde 1 voor één markt/timeframe, met varianten als kolommen."""
    rows = []

    def add(df, fam, L=None, **extra):
        if df is None or len(df) == 0:
            return
        df = df.copy()
        df["fam"], df["L"] = fam, L
        for k_, v_ in extra.items():
            df[k_] = v_
        rows.append(df)

    for L in LS:
        add(R.bos_events(bars, tf, L), "BOS", L)
        add(R.choch_events(bars, L), "CHoCH", L)
        add(R.swing_sweep_events(bars, L), "sweep_swing", L)
    if tf in ("15min", "1h"):
        add(R.level_sweep_events(bars, "day"), "sweep_dag")
        add(R.level_sweep_events(bars, "asia"), "sweep_azie")
    if tf in ("1h", "4h"):
        add(R.level_sweep_events(bars, "week"), "sweep_week")
    fv = R.fvg_events(bars)
    add(fv["vorming"], "FVG_vorming")
    add(fv["retest"], "FVG_retest")
    add(fv["inverse"], "FVG_inverse")
    ev = pd.concat(rows, ignore_index=True)
    for c in ("entry_bar", "entry_price", "sweep"):
        if c not in ev:
            ev[c] = np.nan
    return ev


def main(folder, outdir):
    os.makedirs(outdir, exist_ok=True)
    allev = []
    for sym in MARKETS:
        for tfn, tf in TFS.items():
            t0 = time.time()
            bars = load(folder, sym, tfn)
            assert bars.index.max() < END
            a = atr(bars, 14).to_numpy()
            n = len(bars)
            explore = R.explore_mask(bars.index)
            h1, h2 = (R.htf_trend(bars, tf, r) for r in R.HTF[tf])
            ev = events_for(bars, tf, a)
            k = ev.k.to_numpy(int); d = ev.d.to_numpy(int)
            ev = ev[explore[k]].reset_index(drop=True)          # alleen de verkenningshelft
            k = ev.k.to_numpy(int); d = ev.d.to_numpy(int)
            want = np.where(d > 0, "UP", "DOWN")
            ev["htf1_mee"] = h1[k] == want
            ev["htf2_mee"] = (h2[k] == want) & ev["htf1_mee"].to_numpy()
            ev["disp"] = R.displacement(bars, a, k)
            ev["fvg3"] = R.fvg_recent(bars, k, d)
            ev["time"] = bars.index[k]
            # meting
            limit = ev.entry_bar.notna().to_numpy()
            m = R.measure(bars, a, k, d)
            if limit.any():
                ml = R.measure(bars, a, k[limit], d[limit], entry_bar=ev.entry_bar[limit].to_numpy(int),
                               entry_price=ev.entry_price[limit].to_numpy(float))
                m.loc[limit, :] = ml.to_numpy()
            ev = pd.concat([ev, m], axis=1)
            # gepaarde basislijn: zelfde uur (+ trendstand voor de trendvarianten), zelfde richting
            pool = np.where(explore[: n - 49])[0]
            for tag, strata in (("", None), ("_h1", h1), ("_h12", np.char.add(h1.astype(str), h2.astype(str)))):
                bl = R.baseline(bars, a, k, d, pool, strata=strata, per_event=5, seed=11)
                ev["base" + tag] = np.nanmean(bl.R21.to_numpy().reshape(-1, 5), axis=1)
                ev["base11" + tag] = np.nanmean(bl.R11.to_numpy().reshape(-1, 5), axis=1)
            ev["market"], ev["tf"] = sym, tfn
            ev["cost_R"] = COST[sym] / np.nanmedian(a[explore])
            allev.append(ev)
            print(f"{sym} {tfn}: {len(ev)} gebeurtenissen ({time.time() - t0:.0f}s)", flush=True)
    ev = pd.concat(allev, ignore_index=True)
    ev.to_pickle(os.path.join(outdir, "events_ronde1.pkl"))
    print("klaar", len(ev))


if __name__ == "__main__":
    main(*sys.argv[1:3])
