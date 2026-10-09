"""
Setup-detectie: liquidity sweep + CHoCH met de trend (spec §3).

Werking voor LONG (SHORT is exact gespiegeld):
0. Tegenbeweging: op de setup-timeframe zit de koers vóór de sweep in een structuur TEGEN de
   grote trend (LONG: laatste twee swing highs dalend én laatste twee swing lows dalend = LH/LL).
   Alleen dan is de doorbraak erna een echte CHoCH (breuk van de bestaande trend).
1. Niveau: de laatste bevestigde swing low die
   - bevestigd is vóór de huidige candle (geen vooruitkijken),
   - niet ouder is dan `sweep_lookback` candles,
   - nog "intact" is: geen enkele candle heeft er sindsdien ONDER gesloten.
2. Sweep: een candle prikt met de low onder dat niveau en sluit erboven.
   Sweep-low = de low van die candle.
3. Daarna, binnen `choch_window` candles:
   - sluit een candle onder het niveau  -> run, setup vervalt;
   - zakt een candle onder de sweep-low -> setup vervalt (die candle kan zelf een nieuwe sweep zijn);
   - sluit een candle BOVEN de laatste bevestigde swing high van vóór de sweep (= de laatste lower high)
     -> CHoCH = signaal.
4. Alleen als de H1-trend op het moment van het signaal UP is (SHORT: DOWN).

Het signaal bestaat pas op het einde van de CHoCH-candle (`signal_time`).
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from katsu.structure import DOWN, UP, find_swings

LONG, SHORT = "LONG", "SHORT"


@dataclass(frozen=True)
class Setup:
    direction: str
    swept_level: float      # het geveegde swing-niveau
    swing_index: int        # positie van die swing
    sweep_index: int        # candle die de sweep maakte
    sweep_extreme: float    # sweep-low (LONG) / sweep-high (SHORT) -> basis voor de SL
    sweep_body_pct: float   # body van de sweep-candle als deel van zijn range (gelogd)
    choch_index: int
    choch_level: float
    signal_time: pd.Timestamp  # einde van de CHoCH-candle


def _local_down(lc, lp, hc, hp, n):
    """Is de structuur bij candle n dalend (laatste 2 bevestigde highs én lows dalend)?"""
    a = bisect_right(lc, n); b = bisect_right(hc, n)
    if a < 2 or b < 2:
        return False
    return lp[a - 1] < lp[a - 2] and hp[b - 1] < hp[b - 2]


def _scan(o, h, lo, c, times, tf_delta, swings_low, swings_high, trend_at_time,
          direction, sweep_lookback, choch_window, require_counter=True):
    """Scant één richting. Werkt met 'LONG-logica'; voor SHORT worden de reeksen vooraf gespiegeld."""
    n = len(c)
    out: list[Setup] = []
    want = UP if direction == LONG else DOWN
    lows_sorted = sorted(swings_low, key=lambda s: s.confirmed_at)
    highs = sorted(swings_high, key=lambda s: s.index)
    high_idx = [s.index for s in highs]
    high_conf = [s.confirmed_at for s in highs]
    lbc = sorted(swings_low, key=lambda s: s.confirmed_at); hbc = sorted(swings_high, key=lambda s: s.confirmed_at)
    lc = [s.confirmed_at for s in lbc]; lp = [s.price for s in lbc]
    hc = [s.confirmed_at for s in hbc]; hp = [s.price for s in hbc]
    li = 0
    known_lows: list = []   # swing lows bevestigd tot nu toe
    active = None           # lopende setup: (swing, sweep_index, sweep_extreme)
    for j in range(n):
        # Swings die bevestigd zijn ná candle j-1 mogen vanaf candle j gebruikt worden.
        while li < len(lows_sorted) and lows_sorted[li].confirmed_at <= j - 1:
            known_lows.append(lows_sorted[li]); li += 1

        # 1) Lopende setup bijwerken met candle j.
        if active is not None:
            sw, sj, sx, sbody = active
            if j - sj > choch_window or c[j] < sw.price or lo[j] < sx:
                active = None   # venster voorbij, run, of onder de sweep-low
            else:
                # laatste swing high met index < sweep-candle die bevestigd is vóór candle j
                k = bisect_left(high_idx, sj) - 1
                while k >= 0 and high_conf[k] > j - 1:
                    k -= 1
                cand = [highs[k]] if k >= 0 else []
                if cand and c[j] > cand[-1].price:
                    t_sig = times[j] + tf_delta
                    if trend_at_time(t_sig) == want:
                        out.append(Setup(direction, sw.price, sw.index, sj, sx, sbody,
                                         j, cand[-1].price, t_sig))
                    active = None
                    continue

        # 2) Nieuwe sweep op candle j?
        if active is None and known_lows:
            sw = known_lows[-1]
            if j - sw.index <= sweep_lookback:
                intact = not np.any(c[sw.index + 1:j] < sw.price)
                counter_ok = (not require_counter) or _local_down(lc, lp, hc, hp, j - 1)
                if intact and counter_ok and lo[j] < sw.price and c[j] > sw.price:
                    rng = h[j] - lo[j]
                    body = abs(c[j] - o[j]) / rng if rng > 0 else 0.0
                    active = (sw, j, lo[j], body)
    return out


def detect_setups(bars: pd.DataFrame, tf: str, trend_at_time: Callable[[pd.Timestamp], str],
                  L: int = 3, sweep_lookback: int = 24, choch_window: int = 12,
                  require_counter: bool = True) -> list[Setup]:
    """Alle LONG- en SHORT-setups in `bars` (bv. M5), gesorteerd op signaaltijd."""
    o = bars["open"].to_numpy(float); h = bars["high"].to_numpy(float)
    lo = bars["low"].to_numpy(float); c = bars["close"].to_numpy(float)
    times = bars.index; tf_delta = pd.Timedelta(tf)
    swings = find_swings(bars, L)
    sl = [s for s in swings if s.kind == "LOW"]; sh = [s for s in swings if s.kind == "HIGH"]
    longs = _scan(o, h, lo, c, times, tf_delta, sl, sh, trend_at_time, LONG,
                  sweep_lookback, choch_window, require_counter)
    # SHORT = gespiegelde LONG: prijzen omkeren, highs worden lows.
    mo, mh, ml, mc = -o, -lo, -h, -c
    msl = [s.__class__(s.index, s.confirmed_at, -s.price, "LOW") for s in sh]
    msh = [s.__class__(s.index, s.confirmed_at, -s.price, "HIGH") for s in sl]
    shorts_m = _scan(mo, mh, ml, mc, times, tf_delta, msl, msh, trend_at_time, SHORT,
                     sweep_lookback, choch_window, require_counter)
    shorts = [Setup(SHORT, -s.swept_level, s.swing_index, s.sweep_index, -s.sweep_extreme,
                    s.sweep_body_pct, s.choch_index, -s.choch_level, s.signal_time)
              for s in shorts_m]
    return sorted(longs + shorts, key=lambda s: (s.signal_time, s.direction))


def trend_lookup(bars: pd.DataFrame, tf: str, L: int = 3) -> Callable[[pd.Timestamp], str]:
    """
    Geeft een functie trend(t): de trend op deze timeframe op tijdstip t, enkel op basis van
    candles die op t volledig gesloten zijn en swings die toen al bevestigd waren.
    """
    from katsu.structure import trend_series
    swings = find_swings(bars, L)
    ends = bars.index + pd.Timedelta(tf)
    series = trend_series(swings, len(bars))          # trend op elke candle, vooraf berekend

    def trend(t: pd.Timestamp) -> str:
        n = int(ends.searchsorted(t, side="right")) - 1   # laatste candle met einde <= t
        if n < 0:
            return "NEUTRAL"
        return series[n]
    return trend


def h1_trend_lookup(h1: pd.DataFrame, L: int = 3) -> Callable[[pd.Timestamp], str]:
    """De H1-trend die als filter dient (spec §3)."""
    return trend_lookup(h1, "1h", L)


CONTEXT_TFS = {"M15": "15min", "H1": "1h", "H4": "4h", "D1": "1D"}


def multi_tf_trend(m1: pd.DataFrame, L: int = 3) -> Callable[[pd.Timestamp], dict]:
    """
    Trend op M15, H1, H4 en D1 op tijdstip t (spec §7: alleen gelogd, geen filter).
    D1 en H4 volgen de servertijd (daggrens 00:00 server = 23:00 Brussel).
    """
    from katsu.data import resample
    look = {name: trend_lookup(resample(m1, tf), tf, L) for name, tf in CONTEXT_TFS.items()}
    return lambda t: {name: f(t) for name, f in look.items()}
