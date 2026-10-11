"""
Test van de Gitchi-FVG (docs/spec_v0.4.md §10), alleen op de VERKENNINGSHELFT.
8 varianten (entry 38,2/61,8% · trend met/zonder · geldig tot ongeldig/24u) × EURUSD, GBPUSD, XAUUSD.

Gebruik: python -m scripts.gfvg_test <htf-map> <uitmap>
Schrijft: <uitmap>/gfvg_trades.pkl en research/register_gfvg.csv
"""
import itertools
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

from katsu import research as R
from katsu.execution import EURUSD, M1, XAUUSD, run_portfolio
from katsu.gfvg import detect_gfvg, make_gfvg_plan
from katsu.structure import atr
from scripts.laag2_h4 import GBPUSD, summarize
from scripts.ronde1 import load

INS = {m: replace(i, max_hold_days=14) for m, i in (("EURUSD", EURUSD), ("GBPUSD", GBPUSD), ("XAUUSD", XAUUSD))}
VARIANTS = list(itertools.product((0.382, 0.618), ("met", "zonder"), ("ongeldig", "24u")))


def gate(s):
    return bool(s["trades"] >= 100 and s["gem_r"] >= 0.10 and s["t"] >= 2.0 and s["voor_2020"] > 0
                and s["2020_24"] > 0 and s["jaren_positief"] > 0.5)


def main(folder, outdir):
    os.makedirs(outdir, exist_ok=True)
    rows, alltr = [], []
    for mkt in INS:
        bars = load(folder, mkt, "M15")
        a = atr(bars, 14).to_numpy()
        h1 = R.htf_trend(bars, "15min", "1h"); h4 = R.htf_trend(bars, "15min", "4h")
        S = [s for s in detect_gfvg(bars, a) if R.explore_mask(bars.index[[s.signal_index]])[0]]
        d = M1(bars, INS[mkt])
        for frac, trend, valid in VARIANTS:
            plans = []
            for s in S:
                want = "UP" if s.direction == "LONG" else "DOWN"
                if trend == "met" and not (h1[s.signal_index] == want and h4[s.signal_index] == want):
                    continue
                p = make_gfvg_plan(s, bars, a, valid, mkt, entry_frac=frac)
                if p is not None and np.isfinite(p.atr):
                    plans.append(p)
            tr = run_portfolio(plans, {mkt: d}, {mkt: INS[mkt]})
            name = f"entry {frac * 100:.1f}% · trend {trend} · {valid}"
            tr["markt"], tr["variant"] = mkt, name
            alltr.append(tr)
            s = summarize(tr)
            g = tr[tr.status == "gesloten"]
            st = tr.status.value_counts()
            s.update({"markt": mkt, "variant": name, "entry": frac, "trend": trend, "geldig": valid,
                      "setups": len(plans), "bruto_r": g.r_gross.mean(), "kosten_r": g.cost_r.mean(),
                      "vulgraad": len(g) / max(len(g) + st.get("niet_gevuld", 0) + st.get("geannuleerd", 0), 1),
                      "long_r": g[g.direction == "LONG"].r_net.mean(), "short_r": g[g.direction == "SHORT"].r_net.mean(),
                      "gem_rr_tp": ((g.tp - g.fill).abs() / g.risk).mean()})
            s["poort"] = gate(s)
            rows.append(s)
            print(f"{mkt} {name}: setups={len(plans)} n={s['trades']} win={s['winrate']:.2f} netto={s['gem_r']:+.3f} "
                  f"bruto={s['bruto_r']:+.3f} t={s['t']:.2f} <2020={s['voor_2020']:+.3f} 2020+={s['2020_24']:+.3f} "
                  f"jaren+={s['jaren_positief']:.2f} vul={s['vulgraad']:.2f} RRtp={s['gem_rr_tp']:.2f} "
                  f"L={s['long_r']:+.3f} S={s['short_r']:+.3f} poort={s['poort']}", flush=True)
    pd.concat(alltr).to_pickle(os.path.join(outdir, "gfvg_trades.pkl"))
    reg = pd.DataFrame(rows)
    reg.drop(columns=["statussen"]).to_csv("research/register_gfvg.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main(*sys.argv[1:3])
