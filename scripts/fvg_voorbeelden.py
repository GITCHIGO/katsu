"""
10 willekeurige FVG's (GBPUSD H4, alle bullish en bearish FVG's, verkenningsdata), gemeten zoals in ronde 1:
instap op de open van de candle na de FVG, SL 1 ATR, TP 1,5 ATR (1,5R), hoogstens 48 candles, SL eerst
bij twijfel. Willekeurig gekozen (vaste toevalsgenerator), niet uitgezocht op resultaat.
Gebruik: python -m scripts.fvg_voorbeelden <htf-map> <uit.pdf>
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

from katsu import research as R
from katsu.plotting import plot_position
from katsu.structure import atr
from scripts.ronde1 import load

RR, MAXB = 1.5, 48
INTRO = """KATSU — 10 willekeurige FVG's op GBPUSD H4 (bullish en bearish, verkenningsdata)

Zelfde meting als in het onderzoek: instap op de open van de candle na de FVG,
SL op 1 ATR, TP op 1,5 ATR (= 1,5R), hoogstens 48 candles (8 dagen), SL eerst bij twijfel.
Gekozen met een vaste toevalsgenerator, NIET uitgezocht op resultaat.

  blauw vlak    = de FVG            oranje cirkel = de derde candle van de FVG (signaal)
  groen vlak    = winstzone (entry → TP)        rood vlak = verlieszone (entry → SL)
  zwarte ster   = instap            ruit = uitstap (groen = TP, rood = SL, grijs = einde 48 candles)

Ter vergelijking, alle 4.012 FVG's van deze soort samen: winrate 41,0% bij 1,5R
(quitte zonder kosten = 40%), gemiddeld +0,03R; willekeurige momenten: 0,00R."""


def trade(o, h, lo, c, k, d, at):
    e = k + 1; ep = o[e]; sl = ep - d * at; tp = ep + d * RR * at
    for j in range(e, min(e + MAXB, len(c))):
        adv = lo[j] if d > 0 else h[j]; fav = h[j] if d > 0 else lo[j]
        if d * (adv - sl) <= 0:
            return e, ep, sl, tp, j, sl, "SL"
        if d * (fav - tp) >= 0:
            return e, ep, sl, tp, j, tp, "TP"
    j = min(e + MAXB, len(c)) - 1
    return e, ep, sl, tp, j, c[j], "tijd"


def main(folder, out):
    bars = load(folder, "GBPUSD", "H4")
    a = atr(bars, 14).to_numpy()
    o, h, lo, c = (bars[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    ev = R.fvg_events(bars)["vorming"]
    ev = ev[R.explore_mask(bars.index[ev.k.to_numpy(int)]) & (ev.k + MAXB + 2 < len(bars))]
    rng = np.random.default_rng(20261011)
    pick = ev.iloc[np.sort(rng.choice(len(ev), 10, replace=False))]
    with PdfPages(out) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3)); fig.text(0.06, 0.94, INTRO, va="top", fontsize=11, family="monospace")
        pdf.savefig(fig); plt.close(fig)
        wins = 0
        for n, r in enumerate(pick.itertuples(), 1):
            k, d = int(r.k), int(r.d)
            e, ep, sl, tp, xi, xp, res = trade(o, h, lo, c, k, d, a[k])
            R_ = d * (xp - ep) / a[k]
            wins += res == "TP"
            gap = (h[k - 2], lo[k]) if d > 0 else (h[k], lo[k - 2])
            t_be = bars.index[k] - pd.Timedelta(hours=1)
            title = (f"#{n}  GBPUSD H4  {'LONG (bullish FVG)' if d > 0 else 'SHORT (bearish FVG)'}  ·  {t_be:%d/%m/%Y %H:%M}"
                     f"  ·  uitkomst: {res} ({R_:+.2f}R)  ·  {xi - e + 1} candles")
            fig, ax = plt.subplots(figsize=(11.7, 6.5))
            plot_position(ax, bars, k, d, e, ep, sl, tp, xi, xp, res, title, gap=gap)
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), fontsize=7, ncol=8, frameon=False)
            fig.tight_layout(); pdf.savefig(fig); plt.close(fig)
            print(n, t_be, d, res, round(R_, 2))
        print("winnaars:", wins, "van 10")


if __name__ == "__main__":
    main(*sys.argv[1:3])
