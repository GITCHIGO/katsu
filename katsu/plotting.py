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
        x1 = max(x1, X(e) + 1)    # entry en exit in dezelfde candle: toch zichtbaar
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
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), fontsize=7, ncol=8, frameon=False)
            fig.tight_layout(); pdf.savefig(fig); plt.close(fig)


# ---------------- Bouwsteen 2: BOS-continuatie ----------------

def _candles(ax, w):
    x = np.arange(len(w))
    for xi, (o, h, l, c) in zip(x, w[["open", "high", "low", "close"]].to_numpy()):
        col = UP_C if c >= o else DN_C
        ax.vlines(xi, l, h, color=col, linewidth=0.8)
        ax.add_patch(Rectangle((xi - 0.3, min(o, c)), 0.6, max(abs(c - o), 1e-9), color=col))
    return x


def plot_bos_setup(ax, setup, bars: pd.DataFrame, trade: dict | None, title: str,
                   server_offset_h: int = 1, before: int = 12, after: int = 30) -> None:
    a = max(min(setup.level_index, setup.hl_index) - before, 0)
    b = min(setup.bos_index + after, len(bars) - 1)
    if trade and trade.get("exit_time") is not None:
        ex = int(bars.index.searchsorted(trade["exit_time"], side="right")) - 1
        b = min(max(b, ex + 5), len(bars) - 1)
    w = bars.iloc[a:b + 1]
    x = _candles(ax, w)

    def X(i): return i - a

    ax.hlines(setup.level, X(setup.level_index), X(setup.bos_index) + 12, colors="#ef6c00",
              linestyles="--", linewidth=1.2, label="gebroken niveau (swing)")
    ax.scatter([X(setup.bos_index)], [w["close"].iloc[X(setup.bos_index)]], marker="o", s=70,
               facecolors="none", edgecolors="#ef6c00", linewidths=2, zorder=5, label="BOS-close")
    ax.hlines(setup.hl_price, X(setup.hl_index), X(setup.bos_index) + 1, colors="#1565c0",
              linestyles="--", linewidth=1.2, label="higher/lower low (SL-basis)")
    if trade and trade.get("fill") is not None:
        e = int(bars.index.searchsorted(trade["entry_time"], side="right")) - 1
        x1 = X(int(bars.index.searchsorted(trade["exit_time"], side="right")) - 1) \
            if trade.get("exit_time") is not None else X(b)
        x1 = max(x1, X(e) + 1)    # entry en exit in dezelfde candle: toch zichtbaar
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


def save_bos_pdf(items: list, path: str, intro: str) -> None:
    """items = lijst van (setup, bars, trade_dict, titel)."""
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(path) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3)); fig.text(0.06, 0.94, intro, va="top", fontsize=11, family="monospace")
        pdf.savefig(fig); plt.close(fig)
        for setup, bars, trade, title in items:
            fig, ax = plt.subplots(figsize=(11.7, 6.5))
            plot_bos_setup(ax, setup, bars, trade, title)
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), fontsize=7, ncol=8, frameon=False)
            fig.tight_layout(); pdf.savefig(fig); plt.close(fig)


# ---------------- Bouwsteen 3: FVG-retest ----------------

def plot_fvg_setup(ax, setup, bars: pd.DataFrame, trade: dict | None, title: str,
                   server_offset_h: int = 1, before: int = 20, after: int = 30) -> None:
    a = max(setup.index - 2 - before, 0)
    b = min(setup.index + after, len(bars) - 1)
    if trade and trade.get("exit_time") is not None:
        ex = int(bars.index.searchsorted(trade["exit_time"], side="right")) - 1
        b = min(max(b, ex + 5), len(bars) - 1, a + 400)     # lange trades: venster begrenzen
    w = bars.iloc[a:b + 1]
    x = _candles(ax, w)

    def X(i): return i - a

    ax.add_patch(Rectangle((X(setup.index - 2) - 0.4, setup.bottom), 12 + 2.8, setup.top - setup.bottom,
                           color="#1565c0", alpha=0.18, label="FVG (gap)"))
    ax.hlines(setup.anchor, X(setup.index - 2), X(setup.index) + 1, colors="#ef6c00", linestyles="--",
              linewidth=1.2, label="laagste low / hoogste high van de FVG (SL-basis)")
    if trade and trade.get("fill") is not None:
        e = int(bars.index.searchsorted(trade["entry_time"], side="right")) - 1
        x1 = X(int(bars.index.searchsorted(trade["exit_time"], side="right")) - 1) \
            if trade.get("exit_time") is not None else X(b)
        x1 = min(max(x1, X(e) + 1), X(b))
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


def save_fvg_pdf(items: list, path: str, intro: str) -> None:
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(path) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3)); fig.text(0.06, 0.94, intro, va="top", fontsize=11, family="monospace")
        pdf.savefig(fig); plt.close(fig)
        for setup, bars, trade, title in items:
            fig, ax = plt.subplots(figsize=(11.7, 6.5))
            plot_fvg_setup(ax, setup, bars, trade, title)
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), fontsize=7, ncol=6, frameon=False)
            fig.tight_layout(); pdf.savefig(fig); plt.close(fig)


# ---------------- Voorbeeldtrade met structuur (laag 2) ----------------

def plot_example_trade(ax, bars: pd.DataFrame, k: int, trade: dict, title: str, marks: dict,
                       server_offset_h: int = 1, before: int = 25, after_exit: int = 6, max_len: int = 90) -> None:
    """
    Eén echte trade op de setup-timeframe. `marks` kan bevatten:
      level=(prijs, index)      -> gebroken niveau (oranje stippellijn)
      anchor=(prijs, index)     -> SL-basis op de structuur (blauwe stippellijn)
      gap=(onder, boven, index) -> FVG (blauw vlak)
    """
    ex = int(bars.index.searchsorted(trade["exit_time"], side="right")) - 1
    a = max(min([k] + [v[1] for key, v in marks.items() if key in ("level", "anchor")] +
                ([marks["gap"][2] - 2] if "gap" in marks else [])) - before, 0)
    b = min(max(ex, k) + after_exit, len(bars) - 1, a + max_len)
    w = bars.iloc[a:b + 1]
    x = _candles(ax, w)

    def X(i): return i - a
    if "level" in marks:
        p, i = marks["level"]
        ax.hlines(p, X(i), X(k) + 1, colors="#ef6c00", linestyles="--", linewidth=1.3, label="gebroken niveau")
    if "anchor" in marks:
        p, i = marks["anchor"]
        ax.hlines(p, X(i), X(k) + 1, colors="#1565c0", linestyles="--", linewidth=1.3, label="SL-basis (structuur)")
    if "gap" in marks:
        lo_, hi_, i = marks["gap"]
        ax.add_patch(Rectangle((X(i - 2) - 0.4, lo_), 3.8, hi_ - lo_, color="#1565c0", alpha=0.25, label="FVG"))
    ax.scatter([X(k)], [w["close"].iloc[X(k)]], marker="o", s=80, facecolors="none", edgecolors="#ef6c00",
               linewidths=2, zorder=5, label="signaalcandle")
    e = int(bars.index.searchsorted(trade["entry_time"], side="right")) - 1
    x1 = min(max(X(ex), X(e) + 1), X(b))
    ax.hlines(trade["fill"], X(e), x1, colors="black", linewidth=2.0, label="entry")
    ax.hlines(trade["sl"], X(e), x1, colors="#8e24aa", linewidth=2.2, label="SL")
    ax.hlines(trade["tp"], X(e), x1, colors="#00838f", linewidth=2.2, linestyles="-.", label="TP (1,5R)")
    step = max(len(x) // 8, 1)
    lab = (w.index - pd.Timedelta(hours=server_offset_h)).strftime("%d/%m/%y %H:%M")
    ax.set_xticks(x[::step]); ax.set_xticklabels(lab[::step], rotation=30, fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_title(title, fontsize=9)
    ax.grid(alpha=0.2)


# ---------------- Positie duidelijk tekenen (zoals de position-tool in TradingView) ----------------

def plot_position(ax, bars: pd.DataFrame, k: int, d: int, entry_i: int, ep: float, sl: float, tp: float,
                  exit_i: int, exit_px: float, result: str, title: str, gap=None,
                  server_offset_h: int = 1, before: int = 20, after: int = 8) -> None:
    """
    Groen vlak = van entry tot TP (winstzone), rood vlak = van entry tot SL (verlieszone), met prijslabels.
    Zwarte ster = instap, ruit = uitstap. `gap` = (onder, boven) van de FVG (blauw vlak op de 3 candles).
    """
    a = max(k - before, 0)
    b = min(exit_i + after, len(bars) - 1)
    w = bars.iloc[a:b + 1]
    x = _candles(ax, w)

    def X(i): return i - a
    if gap is not None:
        ax.add_patch(Rectangle((X(k - 2) - 0.4, gap[0]), 2.8, gap[1] - gap[0], color="#1565c0", alpha=0.30,
                               label="FVG"))
    x0, x1 = X(entry_i) - 0.4, X(exit_i) + 0.4
    ax.add_patch(Rectangle((x0, min(ep, tp)), x1 - x0, abs(tp - ep), color="#2e7d32", alpha=0.18, label="winstzone (TP)"))
    ax.add_patch(Rectangle((x0, min(ep, sl)), x1 - x0, abs(ep - sl), color="#c62828", alpha=0.18, label="verlieszone (SL)"))
    for y, col, txt in ((tp, "#2e7d32", f"TP {tp:.5g}"), (ep, "black", f"entry {ep:.5g}"), (sl, "#c62828", f"SL {sl:.5g}")):
        ax.hlines(y, x0, x1, colors=col, linewidth=1.6)
        ax.text(x1 + 0.3, y, txt, va="center", fontsize=8, color=col, fontweight="bold")
    ax.scatter([X(entry_i)], [ep], marker="*", s=160, color="black", zorder=6, label="instap")
    ax.scatter([X(exit_i)], [exit_px], marker="D", s=70, color="#2e7d32" if result == "TP" else
               ("#c62828" if result == "SL" else "#757575"), zorder=6, label=f"uitstap ({result})")
    ax.scatter([X(k)], [w["close"].iloc[X(k)]], marker="o", s=80, facecolors="none", edgecolors="#ef6c00",
               linewidths=2, zorder=5, label="FVG-candle (signaal)")
    step = max(len(x) // 8, 1)
    lab = (w.index - pd.Timedelta(hours=server_offset_h)).strftime("%d/%m/%y %H:%M")
    ax.set_xticks(x[::step]); ax.set_xticklabels(lab[::step], rotation=30, fontsize=7)
    ax.set_xlim(-1, len(x) + 4)
    ax.tick_params(axis="y", labelsize=7)
    ax.set_title(title, fontsize=10)
    ax.grid(alpha=0.2)
