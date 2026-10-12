"""
Voorbeelden van Silver Bullet-trades (spec v0.5) uit de verkenningsdata: EURUSD M5, NY AM-venster, filter 'sweep'.
Willekeurig gekozen (vaste toevalsgenerator): 2 winnaars en 2 verliezers.
Gebruik: python -m scripts.silver_voorbeelden <uit.pdf>
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

from katsu import research as R
from katsu.data import resample
from katsu.plotting import plot_position
from katsu.silver import WINDOWS, _Side, sb_setups

INTRO = """KATSU — Silver Bullet: 4 voorbeeldtrades (EURUSD M5, NY AM-venster = 16–17u Belgische tijd, filter 'sweep')

Regels: in het venster neemt de koers eerst liquiditeit (onder de laatste swing low / boven de laatste swing high),
daarna ontstaat een FVG in de andere richting. Limietorder op de rand van de FVG, alleen geldig tot het venster sluit.
SL voorbij het uiterste van het venster (+ kleine buffer), TP op de volgende oude high/low, maximaal 2R.
Uitvoering op M1 met alle kosten.

  grijs vlak = het Silver Bullet-venster        paarse stippellijn = de swing low/high die geveegd werd
  blauw vlak = de FVG     groen = winstzone     rood = verlieszone     ster = instap     ruit = uitstap
Twee winnaars (p. 2–3) en twee verliezers (p. 4–5), willekeurig gekozen, niet uitgezocht."""


def main(out):
    m1 = pd.read_pickle("/home/claude/katsu_research/eur_m1_full.pkl")
    m1 = m1[m1.index < "2025-01-01"]
    bars = resample(m1, "5min")
    tr = pd.read_pickle("/home/claude/katsu_research/silver/silver_trades.pkl")
    g = tr[(tr.combo == "EURUSD M5 ny_am sweep") & (tr.status == "gesloten")]
    rng = np.random.default_rng(7)
    w, l = g[g.exit_reason == "TP"], g[g.exit_reason == "SL"]
    pick = pd.concat([w.iloc[np.sort(rng.choice(len(w), 2, replace=False))],
                      l.iloc[np.sort(rng.choice(len(l), 2, replace=False))]])
    S = {(bars.index[s.k] + pd.Timedelta("5min"), s.direction): s for s in sb_setups(bars, "5min", "sweep", windows=["ny_am"])}
    sides = {1: _Side(bars, 1, 3), -1: _Side(bars, -1, 3)}
    with PdfPages(out) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3)); fig.text(0.05, 0.95, INTRO, va="top", fontsize=10, family="monospace")
        pdf.savefig(fig); plt.close(fig)
        for nr, t in enumerate(pick.itertuples(), 1):
            s = S[(t.signal_time, t.direction)]
            d = 1 if s.direction == "LONG" else -1
            ei = int(bars.index.searchsorted(t.entry_time, side="right") - 1)
            xi = int(bars.index.searchsorted(t.exit_time, side="right") - 1)
            k = s.k
            gap = (bars.high.iloc[k - 2], bars.low.iloc[k]) if d > 0 else (bars.high.iloc[k], bars.low.iloc[k - 2])
            be = bars.index[k] - pd.Timedelta(hours=1)
            title = (f"#{nr} {'WINST' if t.exit_reason == 'TP' else 'VERLIES'}  ·  EURUSD M5  {s.direction}  ·  "
                     f"{be:%a %d/%m/%Y}  ·  FVG klaar om {be + pd.Timedelta('5min'):%H:%M} BE\n"
                     f"risico {t.risk / 0.0001:.1f} pips · TP {abs(t.tp - t.fill) / 0.0001:.1f} pips · "
                     f"uitkomst {t.exit_reason} ({t.r_net:+.2f}R netto, ≈ €{t.r_net * t.risk / 0.0001 * 0.88:+.0f} bij 0,1 lot)")
            fig, ax = plt.subplots(figsize=(11.7, 6.8))
            before = k - s.window_start + 30
            plot_position(ax, bars, k, d, ei, t.fill, t.sl, t.tp, xi, t.exit_price, t.exit_reason, title, gap=gap,
                          before=before, after=10)
            a0 = max(k - before, 0)
            ax.axvspan(s.window_start - a0 - 0.5, s.window_start - a0 + 11.5, color="#9e9e9e", alpha=0.15,
                       label="Silver Bullet-venster")
            sd = sides[d]
            q = int(np.searchsorted(sd.l_conf, s.window_start, side="right"))
            ax.axhline(d * sd.l_price[q - 1], color="#6a1b9a", linestyle="--", linewidth=1.2, label="geveegde swing")
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), fontsize=7, ncol=9, frameon=False)
            fig.tight_layout(); pdf.savefig(fig); plt.close(fig)
            print(nr, s.direction, bars.index[k], t.exit_reason, round(t.r_net, 2))


if __name__ == "__main__":
    main(sys.argv[1])
