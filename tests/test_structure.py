"""Tests met vooraf met de hand uitgerekende scenario's voor swings en trend."""
import pandas as pd
import pytest

from katsu.structure import (DOWN, NEUTRAL, UP, confirmed_until, find_swings,
                             trend_at)


def bars(highs, lows):
    n = len(highs)
    idx = pd.date_range("2025-01-06 10:00", periods=n, freq="5min")
    mid = [(h + l) / 2 for h, l in zip(highs, lows)]
    return pd.DataFrame({"open": mid, "high": highs, "low": lows, "close": mid}, index=idx)


def test_swing_high_l1_basis():
    #            0  1  2  3  4
    b = bars([1, 3, 2, 4, 3], [0, 0, 0, 0, 0])
    highs = [s for s in find_swings(b, 1) if s.kind == "HIGH"]
    assert [(s.index, s.price, s.confirmed_at) for s in highs] == [(1, 3, 2), (3, 4, 4)]


def test_gelijke_highs_zijn_geen_swing():
    b = bars([1, 3, 3, 1], [0, 0, 0, 0])
    assert [s for s in find_swings(b, 1) if s.kind == "HIGH"] == []


def test_swing_bestaat_niet_voor_bevestiging():
    b = bars([1, 3, 2, 4, 3], [0, 0, 0, 0, 0])
    sw = find_swings(b, 1)
    # Op candle 1 (de swing zelf) is hij nog niet bevestigd: geen vooruitkijken.
    assert confirmed_until(sw, 1, "HIGH") == []
    assert [s.index for s in confirmed_until(sw, 2, "HIGH")] == [1]


def test_swing_low_l3():
    lows = [5, 4, 3, 1, 2, 3, 4, 5]
    b = bars([10] * 8, lows)
    sl = [s for s in find_swings(b, 3) if s.kind == "LOW"]
    assert [(s.index, s.price, s.confirmed_at) for s in sl] == [(3, 1, 6)]


def test_l_nul_niet_toegestaan():
    with pytest.raises(ValueError):
        find_swings(bars([1, 2, 1], [0, 0, 0]), 0)


def zigzag(points):
    """Bouwt candles die exact door de opgegeven swingpunten lopen (L=1)."""
    highs, lows = [], []
    for kind, p in points:
        if kind == "H":
            highs.append(p); lows.append(p - 1)
        else:
            highs.append(p + 1); lows.append(p)
    return bars(highs, lows)


def test_trend_up():
    # L, H, L, H, L met hogere highs en hogere lows
    b = zigzag([("L", 10), ("H", 20), ("L", 12), ("H", 24), ("L", 15), ("H", 30)])
    sw = find_swings(b, 1)
    assert trend_at(sw, len(b) - 1) == UP


def test_trend_down():
    b = zigzag([("H", 30), ("L", 20), ("H", 28), ("L", 16), ("H", 25), ("L", 10)])
    sw = find_swings(b, 1)
    assert trend_at(sw, len(b) - 1) == DOWN


def test_trend_neutraal_bij_gemengd():
    # hogere high maar lagere low
    b = zigzag([("L", 10), ("H", 20), ("L", 8), ("H", 24), ("L", 6), ("H", 30)])
    sw = find_swings(b, 1)
    assert trend_at(sw, len(b) - 1) == NEUTRAL


def test_trend_neutraal_bij_te_weinig_swings():
    b = zigzag([("L", 10), ("H", 20), ("L", 12)])
    assert trend_at(find_swings(b, 1), len(b) - 1) == NEUTRAL
