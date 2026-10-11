"""
10 willekeurige Gitchi-FVG's (spec v0.4) uit de verkenningsdata, als grafiek, ter controle door Gitchi.
Versie 2 (na Gitchi's feedback): middelste candle breekt, gat >= 0,5 ATR, candle 3 geen wick, entry op 61,8%
in het gat, TP = oude high/low met een plafond van 2R. Zonder trendvoorwaarde (H1/H4 staat in de titel),
order geldig tot ongeldig.
Uitvoering met de echte regels op M15 (kosten, buffer, minimum-SL, kostenplafond, annulering, max. looptijd).
Gekozen met een vaste toevalsgenerator uit de setups die een gesloten trade gaven; NIET uitgezocht op resultaat.

Gebruik: python -m scripts.gfvg_voorbeelden <htf-map> <uit.pdf>
"""
import sys
from dataclasses import replace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle

from katsu import research as R
from katsu.execution import EURUSD, M1, XAUUSD, simulate
from katsu.gfvg import detect_gfvg, make_gfvg_plan
from katsu.plotting import plot_position
from katsu.structure import atr
from scripts.laag2_h4 import GBPUSD
from scripts.ronde1 import load

INS = {m: replace(i, max_hold_days=14) for m, i in (("EURUSD", EURUSD), ("GBPUSD", GBPUSD), ("XAUUSD", XAUUSD))}
N_PER_MARKET = {"EURUSD": 4, "GBPUSD": 3, "XAUUSD": 3}
INTRO = """KATSU — 10 nieuwe willekeurige FVG's volgens jouw regels, versie 2 (M15, verkenningsdata vóór 2025)

Nieuw na jouw feedback:
  • de MIDDELSTE candle van de FVG sluit voorbij de vorige swing high/low
  • het gat is minstens 0,5 ATR groot (niet krap)      • candle 3 is een volle candle (body ≥ 25%), geen wick
  • entry op 61,8% in het gat                          • TP = oude high/low, maar nooit verder dan 2R
SL = onder het order block / de laatste low (+ kleine buffer). Geen trendvoorwaarde (H1/H4 staat in de titel).

  paarse stippellijn = de doorbroken swing high/low        oranje kader = order block (basis voor de SL)
  blauw vlak = de FVG          groen vlak = winstzone (entry → TP)       rood vlak = verlieszone (entry → SL)
  zwarte ster = instap         ruit = uitstap (groen = TP, rood = SL, grijs = maximale looptijd)
  Tijden in Belgische tijd (server − 1 uur).

Gekozen met een vaste toevalsgenerator uit alle setups die een trade gaven, NIET uitgezocht op resultaat.
Vraag aan jou: zou je elk van deze trades nemen? Zo nee: waarom niet?"""


def examples(folder, mkt, n, rng):
    bars = load(folder, mkt, "M15")
    a = atr(bars, 14)
    h1 = R.htf_trend(bars, "15min", "1h"); h4 = R.htf_trend(bars, "15min", "4h")
    S = [s for s in detect_gfvg(bars, a.to_numpy()) if R.explore_mask(bars.index[[s.signal_index]])[0]]
    d = M1(bars, INS[mkt])
    out = []
    for i in rng.permutation(len(S)):
        s = S[i]
        p = make_gfvg_plan(s, bars, a, "ongeldig", mkt)
        if p is None:
            continue
        tr = simulate(p, d, INS[mkt])
        if tr.status != "gesloten":
            continue
        out.append((bars, s, tr, h1[s.signal_index], h4[s.signal_index]))
        if len(out) == n:
            break
    return out


def draw(ax, bars, s, tr, mkt, t1, t4, nr):
    dsign = 1 if s.direction == "LONG" else -1
    k = s.fvg_index
    ei = bars.index.get_loc(tr.entry_time); xi = bars.index.get_loc(tr.exit_time)
    before = min(k - min(s.origin_index, s.swing_index) + 12, 120)
    after = 8
    gap = tuple(sorted((s.edge, s.gap_far)))
    tp_kind = "oude high/low" if abs(tr.tp - s.tp) < 1e-9 else "2R-plafond"
    rr_plan = abs(tr.tp - tr.fill) / tr.risk
    t_be = bars.index[s.signal_index] - pd.Timedelta(hours=1)
    title = (f"#{nr}  {mkt} M15  {'LONG' if dsign > 0 else 'SHORT'}  ·  signaal {t_be:%a %d/%m/%Y %H:%M}  ·  "
             f"H1 {t1} / H4 {t4}\nrisico {tr.risk / float(atr(bars.iloc[max(k - 30, 0):k + 1], 14).iloc[-1]):.1f} ATR  ·  "
             f"TP {tp_kind} (RR {rr_plan:.2f})  ·  uitkomst {tr.exit_reason} ({tr.r_net:+.2f}R netto)  ·  "
             f"retest na {ei - s.signal_index} candles, trade {xi - ei + 1} candles")
    plot_position(ax, bars, k, dsign, ei, tr.fill, tr.sl, tr.tp, xi, tr.exit_price, tr.exit_reason, title,
                  gap=gap, before=before, after=after)
    a0 = max(k - before, 0)
    ax.hlines(s.broken_level, max(s.swing_index - a0, 0) - 0.4, s.break_index - a0 + 0.5, colors="#6a1b9a",
              linestyles="--", linewidth=1.4, label="doorbroken swing")
    w = bars.iloc[s.ob_index]
    ax.add_patch(Rectangle((s.ob_index - a0 - 0.5, w.low), 1.0, w.high - w.low, fill=False,
                           edgecolor="#ef6c00", linewidth=2, label="order block"))


def main(folder, out):
    rng = np.random.default_rng(202610112)
    rows = []
    for mkt, n in N_PER_MARKET.items():
        rows += [(mkt, *e) for e in examples(folder, mkt, n, rng)]
    order = rng.permutation(len(rows))
    with PdfPages(out) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3))
        fig.text(0.05, 0.95, INTRO, va="top", fontsize=10, family="monospace")
        pdf.savefig(fig); plt.close(fig)
        for nr, i in enumerate(order, 1):
            mkt, bars, s, tr, t1, t4 = rows[i]
            fig, ax = plt.subplots(figsize=(11.7, 6.8))
            draw(ax, bars, s, tr, mkt, t1, t4, nr)
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), fontsize=7, ncol=9, frameon=False)
            fig.tight_layout(); pdf.savefig(fig); plt.close(fig)
            print(nr, mkt, s.direction, bars.index[s.signal_index], tr.exit_reason, round(tr.r_net, 2))


if __name__ == "__main__":
    main(*sys.argv[1:3])
