"""
Marktstructuur: swings en trend.

Definities (docs/spec_v0.1.md §3):
- Swing high: high van candle i is STRIKT hoger dan de L candles ervoor en de L erna.
  Swing low: idem met de low, strikt lager.
- Een swing is pas BEVESTIGD na sluiting van candle i+L. Vóór dat moment bestaat hij niet.
- Gelijke highs/lows zijn geen swing (dat is een liquiditeitsniveau).
- Trend: laatste twee bevestigde swing highs én lows allebei stijgend = UP,
  allebei dalend = DOWN, anders NEUTRAL.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

UP, DOWN, NEUTRAL = "UP", "DOWN", "NEUTRAL"


@dataclass(frozen=True)
class Swing:
    index: int          # positie van de swing-candle
    confirmed_at: int   # eerste candle-index waarop de swing gebruikt mag worden (= index + L)
    price: float
    kind: str           # "HIGH" of "LOW"


def find_swings(bars: pd.DataFrame, L: int) -> list[Swing]:
    """Alle swings in de reeks, elk met het moment waarop ze bevestigd zijn."""
    if L < 1:
        raise ValueError("L moet minstens 1 zijn")
    h = bars["high"].to_numpy()
    lo = bars["low"].to_numpy()
    out: list[Swing] = []
    for i in range(L, len(bars) - L):
        left_h, right_h = h[i - L:i], h[i + 1:i + L + 1]
        if h[i] > left_h.max() and h[i] > right_h.max():
            out.append(Swing(i, i + L, float(h[i]), "HIGH"))
        left_l, right_l = lo[i - L:i], lo[i + 1:i + L + 1]
        if lo[i] < left_l.min() and lo[i] < right_l.min():
            out.append(Swing(i, i + L, float(lo[i]), "LOW"))
    return out


def confirmed_until(swings: list[Swing], n: int, kind: str) -> list[Swing]:
    """Swings van één soort die bevestigd zijn op of vóór candle n (geen vooruitkijken)."""
    return [s for s in swings if s.kind == kind and s.confirmed_at <= n]


def trend_at(swings: list[Swing], n: int) -> str:
    """Trend op basis van de laatste twee bevestigde swing highs en lows op candle n."""
    highs = confirmed_until(swings, n, "HIGH")[-2:]
    lows = confirmed_until(swings, n, "LOW")[-2:]
    if len(highs) < 2 or len(lows) < 2:
        return NEUTRAL
    hh = highs[1].price > highs[0].price
    hl = lows[1].price > lows[0].price
    lh = highs[1].price < highs[0].price
    ll = lows[1].price < lows[0].price
    if hh and hl:
        return UP
    if lh and ll:
        return DOWN
    return NEUTRAL


def atr(bars: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range (eenvoudig voortschrijdend gemiddelde van de true range)."""
    prev_close = bars["close"].shift()
    tr = pd.concat([bars["high"] - bars["low"],
                    (bars["high"] - prev_close).abs(),
                    (bars["low"] - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()
