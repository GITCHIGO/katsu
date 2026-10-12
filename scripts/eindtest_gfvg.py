"""
EENMALIGE eindtest 2025–2026 van de Gitchi-FVG (docs/spec_v0.4.md §11). Alles ligt vast vóór de run.

Gebruik: python -m scripts.eindtest_gfvg <htf-map> <uitmap>
"""
import glob
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

from katsu import research as R
from katsu.execution import M1, run_portfolio
from katsu.gfvg import detect_gfvg, make_gfvg_plan
from katsu.structure import atr
from scripts.gfvg_test import INS
from scripts.laag2_h4 import summarize

START = pd.Timestamp("2025-01-01")
EXCLUDED_DAYS = {pd.Timestamp(x).date() for x in
                 ("2026-09-03", "2026-09-21", "2026-09-22", "2026-09-29", "2026-09-30", "2026-10-06")}
ENTRY, VALID = 0.382, "ongeldig"


def final_mask(times: pd.DatetimeIndex, server_offset_h: int = 1) -> np.ndarray:
    """Signalen in de eindtest: vanaf 1 jan 2025 (servertijd), behalve Gitchi's screenshotdagen (Belgische datum)."""
    be = (times - pd.Timedelta(hours=server_offset_h)).date
    return np.asarray(times >= START) & ~np.isin(be, list(EXCLUDED_DAYS))


def load_full(folder, sym):
    f = sorted(glob.glob(os.path.join(folder, f"{sym}_M15_*.pkl")))
    df = pd.read_pickle(f[0])
    return df[df.index >= "2023-01-01"]          # opwarming voor swings/ATR; signalen pas vanaf 2025


def plans_for(mkt, bars, trend, ins_free=False):
    a = atr(bars, 14).to_numpy()
    h1 = R.htf_trend(bars, "15min", "1h"); h4 = R.htf_trend(bars, "15min", "4h")
    out = []
    for s in detect_gfvg(bars, a):
        if not final_mask(bars.index[[s.signal_index]])[0]:
            continue
        want = "UP" if s.direction == "LONG" else "DOWN"
        if trend and not (h1[s.signal_index] == want and h4[s.signal_index] == want):
            continue
        p = make_gfvg_plan(s, bars, a, VALID, mkt, entry_frac=ENTRY)
        if p is not None and np.isfinite(p.atr):
            out.append(replace(p, max_cost_r=None) if ins_free else p)
    return out


def free(ins):
    return replace(ins, min_spread=0.0, slip=0.0, commission=0.0, swap=0.0, swap_short=0.0,
                   rollover_min_spread=0.0, point=0.0)


def report(name, tr):
    s = summarize(tr)
    g = tr[tr.status == "gesloten"]
    y = g.groupby(g.entry_time.dt.year).r_net.agg(["mean", "size"])
    s["r_2025"] = y["mean"].get(2025, np.nan); s["r_2026"] = y["mean"].get(2026, np.nan)
    s["poort"] = bool(s["trades"] >= 100 and s["gem_r"] >= 0.10 and s["t"] >= 2.0 and s["r_2025"] > 0 and s["r_2026"] > 0)
    print(f"{name}: n={s['trades']} win={s['winrate']:.2f} netto={s['gem_r']:+.3f} t={s['t']:.2f} totaal={s['totaal_r']:+.1f}R "
          f"maxDD={s['max_dd']:.1f}R 2025={s['r_2025']:+.3f} ({int(y['size'].get(2025, 0))}) "
          f"2026={s['r_2026']:+.3f} ({int(y['size'].get(2026, 0))}) poort={s['poort']}", flush=True)
    return {"naam": name, **{k: v for k, v in s.items() if k != "statussen"}}


def main(folder, outdir):
    os.makedirs(outdir, exist_ok=True)
    bars = {m: load_full(folder, m) for m in INS}
    rows = []
    # ---- HOOFDTEST (de enige die telt) ----
    plans = sum((plans_for(m, bars[m], trend=False) for m in INS), [])
    tr = run_portfolio(plans, {m: M1(bars[m], INS[m]) for m in INS}, INS)
    tr.to_pickle(os.path.join(outdir, "eindtest_hoofd.pkl"))
    rows.append(report("HOOFDTEST portefeuille 38,2% zonder trend", tr))
    # ---- ter info ----
    for m in INS:
        rows.append(report(f"info {m}", tr[tr.market == m]))
    plans_t = sum((plans_for(m, bars[m], trend=True) for m in INS), [])
    rows.append(report("info met trendspotter", run_portfolio(plans_t, {m: M1(bars[m], INS[m]) for m in INS}, INS)))
    fi = {m: free(INS[m]) for m in INS}
    plans_f = sum((plans_for(m, bars[m], trend=False, ins_free=True) for m in INS), [])
    rows.append(report("info zonder kosten", run_portfolio(plans_f, {m: M1(bars[m], fi[m]) for m in INS}, fi)))
    pd.DataFrame(rows).to_csv("research/register_eindtest_gfvg.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main(*sys.argv[1:3])
