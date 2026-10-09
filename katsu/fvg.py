"""
Bouwsteen 3: FVG-retest met de hogere timeframes mee (docs/spec_v0.3.md §3–6).

Werking voor LONG (SHORT is exact gespiegeld):
1. Bullish FVG: drie gesloten candles op de setup-timeframe met low(candle 3) > high(candle 1).
   Gap = van high candle 1 (onderkant) tot low candle 3 (bovenkant). Signaal op het einde van candle 3.
2. Trendfilter op dat moment (alleen gesloten candles, trendspotter):
   - "T0": H1 UP
   - "T+": de twee timeframes direct boven de setup UP (M5: M15 + H1, M15: H1 + H4)
3. Entry: limiet op de bovenkant van de gap (variant A) of het midden (variant B), 12 candles geldig.
4. SL-basis: laagste low van de drie FVG-candles (buffer, minimum-SL en kostenplafond doet execution).
Elke FVG geeft maar één order.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from katsu.execution import Instrument, OrderPlan
from katsu.signals import LONG, SHORT
from katsu.structure import DOWN, UP

RETEST_VALID_BARS = 12
MAX_COST_R = 0.2
FILTER_TFS = {  # welke timeframes moeten mee zijn, per setup-timeframe en filter
    ("5min", "T0"): ("H1",), ("15min", "T0"): ("H1",),
    ("5min", "T+"): ("M15", "H1"), ("15min", "T+"): ("H1", "H4"),
}


@dataclass(frozen=True)
class FvgSetup:
    direction: str
    index: int              # candle 3 van het patroon
    top: float              # bovenkant van de gap
    bottom: float           # onderkant van de gap
    anchor: float           # laagste low (LONG) / hoogste high (SHORT) van de drie candles
    signal_time: pd.Timestamp


def detect_fvg(bars: pd.DataFrame, tf: str, trends_at: Callable[[pd.Timestamp], dict],
               filt: str = "T+") -> list[FvgSetup]:
    """Alle FVG's die de trendfilter halen, gesorteerd op signaaltijd. `trends_at(t)` geeft
    {"M15": .., "H1": .., "H4": .., "D1": ..} met alleen gesloten candles (multi_tf_trend)."""
    need = FILTER_TFS[(tf, filt)]
    h = bars["high"].to_numpy(float); lo = bars["low"].to_numpy(float)
    times = bars.index; step = pd.Timedelta(tf)
    out = []
    bull = np.where(lo[2:] > h[:-2])[0] + 2
    bear = np.where(h[2:] < lo[:-2])[0] + 2
    for direction, idx, want in ((LONG, bull, UP), (SHORT, bear, DOWN)):
        for k in idx:
            t = times[k] + step
            tr = trends_at(t)
            if any(tr[x] != want for x in need):
                continue
            if direction == LONG:
                out.append(FvgSetup(LONG, int(k), float(lo[k]), float(h[k - 2]),
                                    float(lo[k - 2:k + 1].min()), t))
            else:
                out.append(FvgSetup(SHORT, int(k), float(lo[k - 2]), float(h[k]),
                                    float(h[k - 2:k + 1].max()), t))
    return sorted(out, key=lambda s: (s.signal_time, s.direction))


def entry_price(setup: FvgSetup, variant: str) -> float:
    """A = eerste aanraking (LONG: bovenkant, SHORT: onderkant); B = midden van de gap."""
    if variant == "B":
        return (setup.top + setup.bottom) / 2
    return setup.top if setup.direction == LONG else setup.bottom


def make_fvg_plan(setup: FvgSetup, tf: str, atr_series: pd.Series, variant: str,
                  ins: Instrument) -> OrderPlan:
    atr = float(atr_series.iloc[setup.index])
    valid = setup.signal_time + RETEST_VALID_BARS * pd.Timedelta(tf)
    return OrderPlan(setup.direction, setup.signal_time, "limit", setup.anchor, atr,
                     entry_price(setup, variant), valid, market=ins.name, max_cost_r=MAX_COST_R)
