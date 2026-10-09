"""
Bouwsteen 2: BOS-continuatie (docs/spec_v0.2.md §3–4).

Werking voor LONG (SHORT is exact gespiegeld):
1. H1-trend is UP (zelfde filter als bouwsteen 1, H1 met L = 3).
2. Op de setup-timeframe is de structuur óók mee: laatste twee bevestigde swing highs stijgend
   en laatste twee swing lows stijgend (HH + HL), gemeten vóór de BOS-candle.
3. Niveau = de laatste bevestigde swing high, nog intact (sinds zijn ontstaan geen close erboven).
4. BOS = een candle sluit met de body boven dat niveau (een wick telt niet).
5. HL = de laatste bevestigde swing low vóór de BOS-candle -> basis voor de SL.

Alleen swings die bevestigd zijn vóór de BOS-candle tellen (geen vooruitkijken).
Het signaal bestaat pas op het einde van de BOS-candle.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from katsu.execution import Instrument, OrderPlan
from katsu.signals import LONG, SHORT
from katsu.structure import DOWN, UP, Swing, find_swings

RETEST_VALID_BARS = 12   # spec v0.2 §4: retest-limiet 12 candles geldig


@dataclass(frozen=True)
class BosSetup:
    direction: str
    level: float            # gebroken swing high (LONG) / swing low (SHORT)
    level_index: int
    bos_index: int          # candle die met de body voorbij het niveau sloot
    hl_price: float         # higher low (LONG) / lower high (SHORT) -> basis voor de SL
    hl_index: int
    signal_time: pd.Timestamp


def _last_two_rising(conf: list, price: list, n: int) -> bool:
    """Zijn de laatste twee swings die bevestigd zijn op of vóór candle n stijgend?"""
    k = bisect_right(conf, n)
    return k >= 2 and price[k - 1] > price[k - 2]


def _scan_long(h, lo, c, times, tf_delta, highs: list[Swing], lows: list[Swing],
               trend_at_time, want: str) -> list[tuple]:
    """LONG-logica. Geeft (level, level_index, bos_index, hl, hl_index, signal_time)."""
    highs = sorted(highs, key=lambda s: s.confirmed_at)
    lows = sorted(lows, key=lambda s: s.confirmed_at)
    hc = [s.confirmed_at for s in highs]; hp = [s.price for s in highs]
    lc = [s.confirmed_at for s in lows]; lp = [s.price for s in lows]
    out = []
    for j in range(1, len(c)):
        kh = bisect_right(hc, j - 1)                   # swing highs bevestigd vóór candle j
        if kh == 0 or c[j] <= hp[kh - 1]:
            continue
        sw = highs[kh - 1]
        if np.any(c[sw.index + 1:j] > sw.price):      # niet meer intact: al eerder doorbroken
            continue
        if not (_last_two_rising(hc, hp, j - 1) and _last_two_rising(lc, lp, j - 1)):
            continue                                   # setup-timeframe niet in HH + HL
        kl = bisect_right(lc, j - 1)
        hl = lows[kl - 1]
        t_sig = times[j] + tf_delta
        if trend_at_time(t_sig) != want:
            continue
        out.append((sw.price, sw.index, j, hl.price, hl.index, t_sig))
    return out


def detect_bos(bars: pd.DataFrame, tf: str, trend_at_time: Callable[[pd.Timestamp], str],
               L: int = 3) -> list[BosSetup]:
    """Alle LONG- en SHORT-BOS-setups, gesorteerd op signaaltijd."""
    h = bars["high"].to_numpy(float); lo = bars["low"].to_numpy(float); c = bars["close"].to_numpy(float)
    times = bars.index; tf_delta = pd.Timedelta(tf)
    swings = find_swings(bars, L)
    sh = [s for s in swings if s.kind == "HIGH"]; sl = [s for s in swings if s.kind == "LOW"]
    longs = [BosSetup(LONG, *r) for r in _scan_long(h, lo, c, times, tf_delta, sh, sl, trend_at_time, UP)]
    # SHORT = gespiegelde LONG: prijzen omkeren, lows worden highs.
    msh = [Swing(s.index, s.confirmed_at, -s.price, "HIGH") for s in sl]
    msl = [Swing(s.index, s.confirmed_at, -s.price, "LOW") for s in sh]
    shorts = [BosSetup(SHORT, -lv, li, bi, -hl, hi, t)
              for lv, li, bi, hl, hi, t in _scan_long(-lo, -h, -c, times, tf_delta, msh, msl,
                                                       trend_at_time, DOWN)]
    return sorted(longs + shorts, key=lambda s: (s.signal_time, s.direction))


def make_bos_plan(setup: BosSetup, tf: str, atr_series: pd.Series, variant: str,
                  ins: Instrument) -> OrderPlan:
    """
    Variant A: limiet op het gebroken niveau, 12 candles geldig.
    Variant B: marktorder op de open van de candle na de BOS.
    SL-basis (anchor) is in beide gevallen de HL; buffer en minimum-SL doet execution.simulate.
    """
    atr = float(atr_series.iloc[setup.bos_index])
    if variant == "A":
        valid = setup.signal_time + RETEST_VALID_BARS * pd.Timedelta(tf)
        return OrderPlan(setup.direction, setup.signal_time, "limit", setup.hl_price, atr,
                         setup.level, valid, market=ins.name)
    return OrderPlan(setup.direction, setup.signal_time, "market", setup.hl_price, atr, market=ins.name)
