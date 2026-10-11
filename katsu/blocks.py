"""
Ronde 3: de resterende bouwstenen (docs/onderzoeksplan_edge.md §12).

Order block, Fibonacci 61,8–78,6% (OTE), RSI-divergentie, BPR, exhaustion-FVG en equal highs/lows.
Elke detector geeft een DataFrame met minstens k (signaalcandle) en d (+1/−1); bij een limiet-instap ook
entry_bar en entry_price. Alleen gesloten candles, swings pas na bevestiging.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from katsu.bos import detect_bos
from katsu.research import ANY, _arrays
from katsu.structure import find_swings
from katsu.trend import rsi


def _bos(bars, tf, L):
    return detect_bos(bars, tf, lambda t: ANY, L=L)


def ob_events(bars: pd.DataFrame, tf: str, L: int, window: int = 24) -> pd.DataFrame:
    """
    Order block na een BOS: de laatste candle tegen de richting tussen de higher low en de BOS-candle.
    Gebeurtenis = eerste terugkeer in het OB binnen `window` candles; instap op de OB-rand (limiet,
    of een betere open). Kolom fvg: zit er een FVG in de impuls tussen OB en BOS-candle?
    """
    o, h, lo, c = _arrays(bars)
    n = len(c)
    out = []
    for s in _bos(bars, tf, L):
        d = 1 if s.direction == "LONG" else -1
        k = s.bos_index
        cand = [i for i in range(s.hl_index, k) if (d > 0 and c[i] < o[i]) or (d < 0 and c[i] > o[i])]
        if not cand:
            continue
        ob = cand[-1]
        edge = h[ob] if d > 0 else lo[ob]
        fvg = any((d > 0 and lo[j] > h[j - 2]) or (d < 0 and h[j] < lo[j - 2]) for j in range(ob + 2, k + 1))
        for m in range(k + 1, min(k + 1 + window, n)):
            if (d > 0 and lo[m] <= edge) or (d < 0 and h[m] >= edge):
                ep = min(edge, o[m]) if d > 0 else max(edge, o[m])
                out.append((k, d, m, ep, ob, fvg)); break
    return pd.DataFrame(out, columns=["k", "d", "entry_bar", "entry_price", "ob_index", "fvg"])


def fib_events(bars: pd.DataFrame, tf: str, L: int, level: float, window: int = 24) -> pd.DataFrame:
    """
    Fibonacci-terugloop na een BOS: been = higher low -> hoogste high t/m de BOS-candle (LONG).
    Niveau = high − level × been. Gebeurtenis = eerste candle binnen `window` die het niveau raakt,
    zolang er nog geen nieuwe high boven het been kwam (raakt dezelfde candle beide, dan telt de aanraking).
    """
    o, h, lo, c = _arrays(bars)
    n = len(c)
    out = []
    for s in _bos(bars, tf, L):
        d = 1 if s.direction == "LONG" else -1
        k = s.bos_index
        if d > 0:
            top = h[s.hl_index:k + 1].max(); bot = s.hl_price
            lvl = top - level * (top - bot)
        else:
            bot = lo[s.hl_index:k + 1].min(); top = s.hl_price
            lvl = bot + level * (top - bot)
        for m in range(k + 1, min(k + 1 + window, n)):
            if (d > 0 and lo[m] <= lvl) or (d < 0 and h[m] >= lvl):
                ep = min(lvl, o[m]) if d > 0 else max(lvl, o[m])
                out.append((k, d, m, ep, lvl, top, bot)); break
            if (d > 0 and h[m] > top) or (d < 0 and lo[m] < bot):
                break
    return pd.DataFrame(out, columns=["k", "d", "entry_bar", "entry_price", "level", "top", "bot"])


def rsi_div_events(bars: pd.DataFrame, L: int, n_rsi: int = 14) -> pd.DataFrame:
    """
    Klassieke RSI-divergentie: twee opeenvolgende swing lows, de tweede lager in prijs maar met hogere RSI
    -> LONG op het moment dat de tweede low bevestigd is (k = confirmed_at). Spiegel voor highs -> SHORT.
    Kolom rsi2 = RSI op de tweede swing.
    """
    r = rsi(bars["close"], n_rsi)
    sw = find_swings(bars, L)
    out = []
    for kind, d in (("LOW", 1), ("HIGH", -1)):
        ss = [s for s in sw if s.kind == kind]
        for a, b in zip(ss, ss[1:]):
            lower = b.price < a.price if d > 0 else b.price > a.price
            div = r[b.index] > r[a.index] if d > 0 else r[b.index] < r[a.index]
            if lower and div and b.confirmed_at < len(bars):
                out.append((b.confirmed_at, d, r[b.index]))
    return pd.DataFrame(out, columns=["k", "d", "rsi2"]).sort_values("k").reset_index(drop=True)


def _fvgs(bars):
    o, h, lo, c = _arrays(bars)
    out = []
    for k in range(2, len(c)):
        if lo[k] > h[k - 2]:
            out.append((k, 1, h[k - 2], lo[k]))
        elif h[k] < lo[k - 2]:
            out.append((k, -1, h[k], lo[k - 2]))
    return out                                    # (k, d, onderkant, bovenkant)


def bpr_events(bars: pd.DataFrame, lookback: int = 10) -> pd.DataFrame:
    """BPR: een FVG die overlapt met een tegengestelde FVG van de laatste `lookback` candles -> richting nieuwste."""
    f = _fvgs(bars)
    out = []
    for i, (k, d, lo_, hi_) in enumerate(f):
        for (k2, d2, lo2, hi2) in reversed(f[:i]):
            if k - k2 > lookback:
                break
            if d2 == -d and lo_ < hi2 and lo2 < hi_:
                out.append((k, d)); break
    return pd.DataFrame(out, columns=["k", "d"])


def exhaustion_events(bars: pd.DataFrame, a: np.ndarray, move_atr: float = 4.0, n: int = 12) -> pd.DataFrame:
    """FVG na een beweging van ≥ move_atr × ATR over n candles in dezelfde richting -> ommekeer (tegenrichting)."""
    c = bars["close"].to_numpy(float)
    out = []
    for k, d, lo_, hi_ in _fvgs(bars):
        if k >= n and np.isfinite(a[k]) and d * (c[k] - c[k - n]) >= move_atr * a[k]:
            out.append((k, -d))
    return pd.DataFrame(out, columns=["k", "d"])


def equal_sweep_events(bars: pd.DataFrame, a: np.ndarray, L: int = 3, tol: float = 0.1,
                       max_gap: int = 48) -> pd.DataFrame:
    """
    Equal highs: de laatste twee bevestigde swing highs liggen binnen tol × ATR van elkaar en binnen max_gap
    candles; zolang niemand erboven sloot, prikt een candle erboven en sluit eronder -> SHORT (spiegel LONG).
    """
    o, h, lo, c = _arrays(bars)
    sw = find_swings(bars, L)
    out = []
    for kind, d in (("HIGH", -1), ("LOW", 1)):
        ss = [s for s in sw if s.kind == kind]
        conf = np.array([s.confirmed_at for s in ss])
        used = set()
        for j in range(1, len(c)):
            m = np.searchsorted(conf, j - 1, side="right")
            if m < 2:
                continue
            s1, s2 = ss[m - 2], ss[m - 1]
            if (s1.index, s2.index) in used or s2.index - s1.index > max_gap or not np.isfinite(a[j]):
                continue
            if abs(s1.price - s2.price) > tol * a[j]:
                continue
            lvl = max(s1.price, s2.price) if d < 0 else min(s1.price, s2.price)
            seg = c[s1.index + 1:j]
            if (d < 0 and np.any(seg > lvl)) or (d > 0 and np.any(seg < lvl)):
                used.add((s1.index, s2.index)); continue
            if (d < 0 and h[j] > lvl and c[j] < lvl) or (d > 0 and lo[j] < lvl and c[j] > lvl):
                out.append((j, d)); used.add((s1.index, s2.index))
    return pd.DataFrame(out, columns=["k", "d"]).sort_values("k").reset_index(drop=True)
