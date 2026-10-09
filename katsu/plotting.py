"""
Controlegrafieken: één setup op de setup-timeframe, met alle onderdelen gemarkeerd.
Alleen bedoeld om met het oog te controleren of de detectie doet wat de spec zegt.
Tijden op de as in Brusselse tijd (servertijd − 1 uur).
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

from katsu.signals import LONG, Setup

UP_C, DN_C = "#2e7d32", "#c62828"


def _choch_swing_index(setup: Setup, bars: pd.DataFrame) -> int:
    """Positie van de swing die de CHoCH brak (laatste candle vóór de sweep met dat exacte niveau)."""
    col = "high" if setup.direction == LONG else "low"
    vals = bars[col].to_numpy(float)
    for i in range(setup.sweep_index - 1, -1, -1):
        if vals[i] == setup.choch_level:
            return i
    return max(setup.sweep_index - 5, 0)


def plot_setup(ax, setup: Setup, bars: pd.DataFrame, trade: dict | None, title: str,
               server_offset_h: int = 1, before: int = 12, after: int = 30) -> None:
    ci = _choch_swing_index(setup, bars)
    a = max(min(setup.swing_index, ci) - before, 0)
    b = min(setup.choch_index + after, len(bars) - 1)
    if trade and trade.get("exit_time") is not None:
        ex = int(bars.index.searchsorted(trade["exit_time"], side="right")) - 1
        b = min(max(b, ex + 5), len(bars) - 1)
    w = bars.iloc[a:b + 1]
    x = np.arange(len(w))
    for xi, (o, h, l, c) in zip(x, w[["open", "high", "low", "close"]].to_numpy()):
        col = UP_C if c >= o else DN_C
        ax.vlines(xi, l, h, color=col, linewidth=0.8)
        ax.add_patch(Rectangle((xi - 0.3, min(o, c)), 0.6, max(abs(c - o), 1e-9), color=col))

    def X(i): return i - a

    # geveegd niveau
    ax.hlines(setup.swept_level, X(setup.swing_index), X(setup.sweep_index) + 1, colors="#1565c0",
              linestyles="--", linewidth=1.2, label="geveegd niveau (swing)")
    ax.scatter([X(setup.sweep_index)], [setup.sweep_extreme], marker="v" if setup.direction != LONG else "^",
               s=90, color="#1565c0", zorder=5, label="sweep-candle")
    # CHoCH
    ax.hlines(setup.choch_level, X(ci), X(setup.choch_index) + 1, colors="#ef6c00", linestyles="--",
              linewidth=1.2, label="CHoCH-niveau")
    ax.scatter([X(setup.choch_index)], [w["close"].iloc[X(setup.choch_index)]], marker="o", s=70,
               facecolors="none", edgecolors="#ef6c00", linewidths=2, zorder=5, label="CHoCH-close")
    # trade
    if trade and trade.get("fill") is not None:
        e = int(bars.index.searchsorted(trade["entry_time"], side="right")) - 1
        x1 = X(int(bars.index.searchsorted(trade["exit_time"], side="right")) - 1) if trade.get("exit_time") is not None else X(b)
        ax.hlines(trade["fill"], X(e), x1, colors="black", linewidth=2.0, label="entry")
        if trade.get("sl") is not None:
            ax.hlines(trade["sl"], X(e), x1, colors="#8e24aa", linewidth=2.2, label="SL")
        if trade.get("tp") is not None:
            ax.hlines(trade["tp"], X(e), x1, colors="#00838f", linewidth=2.2, linestyles="-.", label="TP")
    step = max(len(x) // 8, 1)
    lab = (w.index - pd.Timedelta(hours=server_offset_h)).strftime("%d/%m %H:%M")
    ax.set_xticks(x[::step]); ax.set_xticklabels(lab[::step], rotation=30, fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_title(title, fontsize=9)
    ax.grid(alpha=0.2)


def save_setups_pdf(items: list, path: str, intro: str) -> None:
    """items = lijst van (setup, bars, trade_dict, titel)."""
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(path) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3)); fig.text(0.06, 0.94, intro, va="top", fontsize=11, family="monospace")
        pdf.savefig(fig); plt.close(fig)
        for setup, bars, trade, title in items:
            fig, ax = plt.subplots(figsize=(11.7, 6.5))
            plot_setup(ax, setup, bars, trade, title)
            ax.legend(loc="upper left", fontsize=7, ncol=4)
            fig.tight_layout(); pdf.savefig(fig); plt.close(fig)
