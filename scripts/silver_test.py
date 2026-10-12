"""
Silver Bullet (docs/spec_v0.5.md), alleen de VERKENNINGSHELFT. 45 combinaties.
Gebruik: python -m scripts.silver_test <htf-map> <uitmap>
"""
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

from katsu import research as R
from katsu.data import resample
from katsu.execution import M1, run_portfolio
from katsu.silver import WINDOWS, make_sb_plan, sb_setups
from katsu.structure import atr
from scripts.gfvg_test import INS
from scripts.laag2_h4 import summarize
from scripts.ronde1 import load

M1_FILES = {"EURUSD": "/home/claude/katsu_research/eur_m1_full.pkl", "XAUUSD": "/home/claude/katsu_research/xau_m1_full.pkl"}
END = pd.Timestamp("2025-01-01")
MODES = ("alle", "sweep", "bias")


def free(ins):
    return replace(ins, min_spread=0.0, slip=0.0, commission=0.0, swap=0.0, swap_short=0.0,
                   rollover_min_spread=0.0, point=0.0)


def run(mkt, tf, bars, exec_bars, rows, alltr):
    a = atr(bars, 14).to_numpy()
    h1 = R.htf_trend(bars, tf, "1h")
    ins = INS[mkt]
    assert ins.rr == 2.0                       # TP zonder oude high = 2R
    d, dfree = M1(exec_bars, ins), M1(exec_bars, free(ins))
    for w in WINDOWS:
        for mode in MODES:
            S = [s for s in sb_setups(bars, tf, mode, trend=h1, windows=[w])
                 if R.explore_mask(bars.index[[s.k]])[0] and np.isfinite(a[s.k])]
            plans = [make_sb_plan(s, bars, a, mkt, tf) for s in S]
            tr = run_portfolio(plans, {mkt: d}, {mkt: ins})
            trf = run_portfolio([replace(p, max_cost_r=None) for p in plans], {mkt: dfree}, {mkt: free(ins)})
            tfn = "M5" if tf == "5min" else "M15"
            name = f"{mkt} {tfn} {w} {mode}"
            tr["combo"] = name; alltr.append(tr)
            s = summarize(tr)
            g = tr[tr.status == "gesloten"]
            y = g.entry_time.dt.year
            if tfn == "M5":
                h1_, h2_ = g[y <= 2022].r_net.mean(), g[y >= 2023].r_net.mean()
            else:
                h1_, h2_ = s["voor_2020"], s["2020_24"]
            st = tr.status.value_counts()
            gf = trf[trf.status == "gesloten"]
            s.update({"combo": name, "markt": mkt, "tf": tfn, "venster": w, "filter": mode, "setups": len(plans),
                      "helft1": h1_, "helft2": h2_, "zonder_kosten": gf.r_net.mean(), "n_zonder_kosten": len(gf),
                      "vulgraad": len(g) / max(len(g) + st.get("niet_gevuld", 0) + st.get("geannuleerd", 0), 1)})
            s["poort"] = bool(s["trades"] >= 100 and s["gem_r"] >= 0.10 and s["t"] >= 2.0 and h1_ > 0 and h2_ > 0
                              and s["jaren_positief"] > 0.5)
            rows.append({k: v for k, v in s.items() if k != "statussen"})
            print(f"{name}: setups={len(plans)} n={s['trades']} vul={s['vulgraad']:.2f} win={s['winrate']:.2f} "
                  f"netto={s['gem_r']:+.3f} t={s['t']:.2f} helften={h1_:+.3f}/{h2_:+.3f} "
                  f"zonder_kosten={s['zonder_kosten']:+.3f} (n {len(gf)}) poort={s['poort']}", flush=True)


def main(folder, outdir):
    os.makedirs(outdir, exist_ok=True)
    rows, alltr = [], []
    for mkt in ("EURUSD", "GBPUSD", "XAUUSD"):
        b = load(folder, mkt, "M15")
        run(mkt, "15min", b, b, rows, alltr)
    for mkt, f in M1_FILES.items():
        m1 = pd.read_pickle(f)
        m1 = m1[m1.index < END]
        run(mkt, "5min", resample(m1, "5min"), m1, rows, alltr)
    pd.concat(alltr).to_pickle(os.path.join(outdir, "silver_trades.pkl"))
    reg = pd.DataFrame(rows)
    reg.to_csv("research/register_silver_bullet.csv", index=False, float_format="%.4f")
    print(f"\n{len(reg)} combinaties, {int(reg.poort.sum())} door de poort")


if __name__ == "__main__":
    main(*sys.argv[1:3])
