"""
Drie voorbeeldtrades uit laag 2 (echte regels: SL op de structuur, 1,5R, kosten): CHoCH, BOS en FVG op H4.
Gebruik: python -m scripts.voorbeeld_trades <htf-map> <laag2_h4_trades.pkl> <uit.pdf>
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

from katsu import research as R
from katsu.bos import detect_bos
from katsu.plotting import plot_example_trade
from scripts.ronde1 import load

PICK = [("EURUSD CHoCH L3 alle", "EURUSD", "CHoCH"), ("GBPUSD BOS L1 TF+1 mee", "GBPUSD", "BOS"),
        ("GBPUSD FVG_vorming L- TF+1 mee", "GBPUSD", "FVG")]
INTRO = """KATSU — 3 voorbeeldtrades met de echte regels (laag 2, H4, verkenningsdata)

Elke pagina: één willekeurig gekozen trade (vaste toevalsgenerator, niet uitgezocht op resultaat).
Regels: instap op de open van de volgende H4-candle · SL op de structuur − buffer · TP 1,5R ·
kosten incl. swap · trade loopt tot SL of TP. Tijden ≈ Belgische tijd.
  oranje cirkel        = signaalcandle (de BOS-, CHoCH- of FVG-candle)
  oranje stippellijn   = het gebroken niveau (BOS/CHoCH)
  blauwe stippellijn   = SL-basis op de structuur · blauw vlak = de FVG
  zwart / paars / turquoise = entry / SL / TP

Ter info, over alle trades van deze 3 setups samen (verkenningsdata):
winrate 38–42%, gemiddeld −0,01 tot −0,08R per trade na kosten."""


def main(folder, trades_path, out):
    tr = pd.read_pickle(trades_path)
    tr = tr[(tr.status == "gesloten") & (tr.rr == 1.5)]
    rng = np.random.default_rng(20261011)
    with PdfPages(out) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3)); fig.text(0.06, 0.94, INTRO, va="top", fontsize=11, family="monospace")
        pdf.savefig(fig); plt.close(fig)
        for cand, mkt, fam in PICK:
            g = tr[tr.kandidaat == cand]
            t = g.iloc[int(rng.integers(len(g)))].to_dict()
            bars = load(folder, mkt, "H4")
            k = int(bars.index.searchsorted(t["signal_time"] - pd.Timedelta("4h")))
            marks = {}
            if fam == "BOS":
                s = [x for x in detect_bos(bars, "4h", lambda q: R.ANY, L=1) if x.bos_index == k][0]
                marks = {"level": (s.level, s.level_index), "anchor": (s.hl_price, s.hl_index)}
            elif fam == "CHoCH":
                ev = R.choch_events(bars, 3); r = ev[ev.k == k].iloc[0]
                anc = R.structural_anchor(bars, "CHoCH", ev[ev.k == k])[0]
                ai = int(r.level_index) + int(np.argmin(bars.low.to_numpy()[int(r.level_index):k + 1])) \
                    if r.d > 0 else int(r.level_index) + int(np.argmax(bars.high.to_numpy()[int(r.level_index):k + 1]))
                marks = {"level": (r.level, int(r.level_index)), "anchor": (anc, ai)}
            else:
                h, lo = bars.high.to_numpy(), bars.low.to_numpy()
                gap = (h[k - 2], lo[k]) if t["direction"] == "LONG" else (h[k], lo[k - 2])
                marks = {"gap": (gap[0], gap[1], k)}
            res = f"{t['exit_reason']} · {t['r_net']:+.2f}R netto · {int(t['nights'])} nachten"
            title = f"{fam} · {mkt} H4 · {t['direction']} · signaal {(t['signal_time'] - pd.Timedelta(hours=1)):%d/%m/%Y %H:%M} · {res}"
            fig, ax = plt.subplots(figsize=(11.7, 6.5))
            plot_example_trade(ax, bars, k, t, title, marks)
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), fontsize=7, ncol=7, frameon=False)
            fig.tight_layout(); pdf.savefig(fig); plt.close(fig)
            print(cand, t["signal_time"], res)


if __name__ == "__main__":
    main(*sys.argv[1:4])
