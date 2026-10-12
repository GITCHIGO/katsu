"""
10 winnende en 10 verliezende trades uit de eindtest 2025–2026 (Gitchi-FVG, hoofdtest), als grafiek.
Willekeurig gekozen (vaste toevalsgenerator) binnen de TP's en binnen de SL's; niet uitgezocht.

Gebruik: python -m scripts.eindtest_voorbeelden <htf-map> <uit.pdf>
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

from katsu import research as R
from katsu.gfvg import detect_gfvg
from katsu.structure import atr
from scripts.eindtest_gfvg import load_full
from scripts.gfvg_test import INS
from scripts.gfvg_voorbeelden import draw

INTRO = """KATSU — eindtest 2025–2026 (Gitchi-FVG, entry 38,2% diep, zonder trend): 10 winnaars en 10 verliezers

Willekeurig gekozen uit alle TP-trades (pagina 2–11) en alle SL-trades (pagina 12–21), niet uitgezocht.
Totaal in de eindtest: 649 trades, 36% winnaars, gemiddeld −0,21R per trade.

  paarse stippellijn = doorbroken swing high/low       oranje kader = order block (basis voor de SL)
  blauw vlak = de FVG          groen vlak = winstzone (entry → TP)       rood vlak = verlieszone (entry → SL)
  zwarte ster = instap         ruit = uitstap          Tijden in Belgische tijd (server − 1 uur).

Let op bij het vergelijken: een verschil dat je ziet tussen 10 winnaars en 10 verliezers is een idee, geen bewijs.
Een filter dat daaruit komt, moet getest worden op data die nog niet bekeken is (bevestigingshelft of demo)."""


def main(folder, out):
    tr = pd.read_pickle("/home/claude/katsu_research/eindtest/eindtest_hoofd.pkl")
    g = tr[tr.status == "gesloten"]
    rng = np.random.default_rng(20261012)
    win = g[g.exit_reason == "TP"]; los = g[g.exit_reason == "SL"]
    pick = pd.concat([win.iloc[np.sort(rng.choice(len(win), 10, replace=False))],
                      los.iloc[np.sort(rng.choice(len(los), 10, replace=False))]])
    cache = {}
    with PdfPages(out) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3)); fig.text(0.05, 0.95, INTRO, va="top", fontsize=10, family="monospace")
        pdf.savefig(fig); plt.close(fig)
        for nr, t in enumerate(pick.itertuples(), 1):
            m = t.market
            if m not in cache:
                bars = load_full(folder, m)
                a = atr(bars, 14).to_numpy()
                S = {(bars.index[s.signal_index] + pd.Timedelta("15min"), s.direction): s for s in detect_gfvg(bars, a)}
                cache[m] = (bars, S, R.htf_trend(bars, "15min", "1h"), R.htf_trend(bars, "15min", "4h"))
            bars, S, h1, h4 = cache[m]
            s = S[(t.signal_time, t.direction)]
            fig, ax = plt.subplots(figsize=(11.7, 6.8))
            draw(ax, bars, s, t, m, h1[s.signal_index], h4[s.signal_index], f"{nr} ({'WINST' if nr <= 10 else 'VERLIES'})")
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), fontsize=7, ncol=9, frameon=False)
            fig.tight_layout(); pdf.savefig(fig); plt.close(fig)
            print(nr, m, t.direction, t.signal_time, t.exit_reason, round(t.r_net, 2))


if __name__ == "__main__":
    main(*sys.argv[1:3])
