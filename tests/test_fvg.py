"""
Handberekende scenario's voor FVG-retest (spec v0.3 §4–5).

Basisscenario LONG (M5-candles vanaf 10:00):
  idx  high   low    open   close
   0   101    99     100    100.5
   1   104   100.5   100.5  103.8
   2   105   102     103.8  104.5   <- bullish FVG: low 102 (candle 2) > high 101 (candle 0)
   3   105.5 101.8   104.5  102
   4   103   101.5   102    102.5

  gap      = 101 (onderkant) tot 102 (bovenkant)
  SL-basis = laagste low van candles 0–2 = 99
  signaal  = einde candle 2 = 10:15
  geen andere FVG's: (1,3) 101,8 > 104? nee · (2,4) 101,5 > 105? nee · geen bearish gaps
Orderplan:
  A: buy limit 102 (bovenkant)   B: buy limit 101,5 (midden)   geldig tot 10:15 + 12 × 5 min = 11:15
"""
import pandas as pd
import pytest

from katsu.execution import Instrument
from katsu.fvg import detect_fvg, make_fvg_plan

BASE = [  # high, low, open, close
    (101, 99, 100, 100.5),
    (104, 100.5, 100.5, 103.8),
    (105, 102, 103.8, 104.5),
    (105.5, 101.8, 104.5, 102),
    (103, 101.5, 102, 102.5),
]
ALL_UP = {"M15": "UP", "H1": "UP", "H4": "UP", "D1": "UP"}
ALL_DOWN = {k: "DOWN" for k in ALL_UP}


def make(rows, freq="5min"):
    idx = pd.date_range("2025-01-06 10:00", periods=len(rows), freq=freq)
    h, l, o, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)


def mirror(rows, axis=300):
    return [(axis - l, axis - h, axis - o, axis - c) for h, l, o, c in rows]


def test_geldige_bullish_fvg():
    sig = detect_fvg(make(BASE), "5min", lambda t: ALL_UP, "T+")
    assert len(sig) == 1
    s = sig[0]
    assert (s.direction, s.index, s.top, s.bottom, s.anchor) == ("LONG", 2, 102, 101, 99)
    assert s.signal_time == pd.Timestamp("2025-01-06 10:15")


def test_bearish_gespiegeld():
    sig = detect_fvg(make(mirror(BASE)), "5min", lambda t: ALL_DOWN, "T+")
    assert len(sig) == 1
    s = sig[0]
    assert (s.direction, s.top, s.bottom, s.anchor) == ("SHORT", 300 - 101, 300 - 102, 300 - 99)


def test_trendfilter_t0_en_t_plus():
    m15_neutraal = {"M15": "NEUTRAL", "H1": "UP", "H4": "UP", "D1": "UP"}
    assert len(detect_fvg(make(BASE), "5min", lambda t: m15_neutraal, "T0")) == 1   # alleen H1 nodig
    assert detect_fvg(make(BASE), "5min", lambda t: m15_neutraal, "T+") == []       # M5: M15 + H1 nodig
    h4_down = {"M15": "UP", "H1": "UP", "H4": "DOWN", "D1": "UP"}
    bars15 = make(BASE, "15min")
    assert detect_fvg(bars15, "15min", lambda t: h4_down, "T+") == []               # M15: H1 + H4 nodig
    assert len(detect_fvg(bars15, "15min", lambda t: h4_down, "T0")) == 1
    # D1 speelt nooit mee
    d1_down = {"M15": "UP", "H1": "UP", "H4": "UP", "D1": "DOWN"}
    assert len(detect_fvg(make(BASE), "5min", lambda t: d1_down, "T+")) == 1


def test_trend_gemeten_op_einde_van_candle_3():
    gezien = []
    detect_fvg(make(BASE), "5min", lambda t: gezien.append(t) or ALL_UP, "T+")
    assert pd.Timestamp("2025-01-06 10:15") in gezien


def test_raken_is_geen_gap():
    rows = list(BASE)
    rows[2] = (105, 101, 103.8, 104.5)      # low 101 = high candle 0: geen gat
    assert detect_fvg(make(rows), "5min", lambda t: ALL_UP, "T+") == []


def test_geen_long_tegen_de_trend():
    assert detect_fvg(make(BASE), "5min", lambda t: ALL_DOWN, "T0") == []


def test_orderplan_rand_en_midden():
    s = detect_fvg(make(BASE), "5min", lambda t: ALL_UP, "T+")[0]
    atr = pd.Series([1.0] * len(BASE))
    a = make_fvg_plan(s, "5min", atr, "A", Instrument("XAUUSD"))
    b = make_fvg_plan(s, "5min", atr, "B", Instrument("XAUUSD"))
    assert (a.kind, a.limit_price, a.anchor) == ("limit", 102, 99)
    assert b.limit_price == pytest.approx(101.5)
    assert a.valid_until == pd.Timestamp("2025-01-06 11:15")
    assert a.max_cost_r == b.max_cost_r == 0.2


def test_short_entry_a_is_onderkant():
    s = detect_fvg(make(mirror(BASE)), "5min", lambda t: ALL_DOWN, "T+")[0]
    p = make_fvg_plan(s, "5min", pd.Series([1.0] * 5), "A", Instrument("XAUUSD"))
    assert p.limit_price == 300 - 102 and p.direction == "SHORT"
