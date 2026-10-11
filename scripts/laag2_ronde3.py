"""
Laag 2 voor de kandidaten die in ronde 3 door de poort kwamen (plan §12), alleen op de VERKENNINGSHELFT.
Beide kandidaten zijn 'omgekeerd': koop op 70,5% na een bullish BOS werkt slecht, dus de test is de
tegengestelde trade: sell-stop op het 70,5%-niveau (spiegel voor bearish BOS), SL boven de top van het been
(de structuur die het idee ongeldig maakt), TP 1,5R, alle kosten, maximale looptijd.

Gebruik: python -m scripts.laag2_ronde3 <htf-map> <uitmap>
"""
import os
import sys

import numpy as np
import pandas as pd

from katsu import research as R
from katsu.blocks import fib_events
from katsu.execution import M1, Instrument, OrderPlan, run_portfolio
from katsu.structure import atr
from scripts.laag2_h4 import summarize
from scripts.ronde1 import load

US500 = Instrument("US500", tick=0.01, point=0.01, min_spread=0.30, slip=0.25, commission=0.0, rr=1.5,
                   swap_pct_long=0.03, swap_pct_short=0.03, rollover_min_spread=1.0)
CANDIDATES = [("US500", "H1", "1h", 3, 5), ("US500", "H4", "4h", 1, 15)]   # markt, tf, regel, L, max dagen


def run(folder, mkt, tfn, tf, L, max_days):
    bars = load(folder, mkt, tfn)
    a = atr(bars, 14).to_numpy()
    ev = fib_events(bars, tf, L, 0.705)
    ev = ev[R.explore_mask(bars.index[ev.k.to_numpy(int)])].reset_index(drop=True)
    from dataclasses import replace
    ins = replace(US500, max_hold_days=max_days)
    step = pd.Timedelta(tf)
    plans = []
    for r in ev.itertuples():
        d = -int(r.d)                                     # omgekeerde trade
        m = int(r.entry_bar)
        anchor = r.top if d < 0 else r.bot                # SL voorbij de top (short) / bodem (long) van het been
        plans.append(OrderPlan("LONG" if d > 0 else "SHORT", bars.index[m], "stop", float(anchor),
                               float(a[int(r.k)]), float(r.level), bars.index[m] + step, market=mkt,
                               max_cost_r=0.2))
    m15 = load(folder, mkt, "M15")
    out = run_portfolio(plans, {mkt: M1(m15, ins)}, {mkt: ins})
    out["kandidaat"] = f"{mkt} {tfn} Fib 70,5 L{L} omgekeerd"
    return out


def main(folder, outdir):
    os.makedirs(outdir, exist_ok=True)
    rows, alltr = [], []
    for mkt, tfn, tf, L, md in CANDIDATES:
        tr = run(folder, mkt, tfn, tf, L, md)
        alltr.append(tr)
        s = summarize(tr)
        s["kandidaat"] = tr.kandidaat.iloc[0]
        s["poort"] = bool(s["trades"] >= 100 and s["gem_r"] >= 0.10 and s["t"] >= 2.0 and s["voor_2020"] > 0
                          and s["2020_24"] > 0 and s["jaren_positief"] > 0.5)
        rows.append(s)
        print(f"{s['kandidaat']}: n={s['trades']} win={s['winrate']:.2f} gem={s['gem_r']:+.3f} t={s['t']:.2f} "
              f"<2020={s['voor_2020']:+.3f} 2020+={s['2020_24']:+.3f} jaren+={s['jaren_positief']:.2f} "
              f"maxDD={s['max_dd']:.1f} statussen={s['statussen']} poort={s['poort']}")
    pd.concat(alltr).to_pickle(os.path.join(outdir, "laag2_ronde3_trades.pkl"))
    pd.DataFrame(rows).to_csv("research/register_laag2_ronde3.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main(*sys.argv[1:3])
