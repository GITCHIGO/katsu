"""
Handberekende scenario's voor BOS-continuatie (spec v0.2 §3–4).

Basisscenario LONG (L=1, M5-candles vanaf 10:00). De koers stijgt in een zigzag:
  idx  high   low    open   close
   0   100    97     99     98
   1    99    96     98     97     <- swing low 96   (bevestigd na 2)
   2   103    97.5   97    102.5
   3   104   101    102.5  103.5    <- swing high 104 (bevestigd na 4)
   4   103    99    103.5   99.5
   5   101    98     99.5  100.5    <- swing low 98   (bevestigd na 6)  higher low
   6   106   100    100.5  103.8    <- swing high 106 (bevestigd na 7)  higher high; close 103,8 < 104: geen BOS
   7   105   101    103.8  101.5
   8   104   100    101.5  100.5    <- swing low 100  (bevestigd na 9)  higher low
   9   105   101    100.5  104.5       close 104,5: boven de oude 104, maar het niveau is nu 106
  10   108   104    104.5  107      <- BOS: close 107 boven de laatste swing high 106

Op candle 10 (alleen swings bevestigd t/m candle 9):
  highs 104 -> 106 stijgend, lows 98 -> 100 stijgend  => HH + HL
  niveau 106 intact (closes 101,5 · 100,5 · 104,5 allemaal onder 106)
  HL = laatste bevestigde swing low = 100 (candle 8)
  signaal = einde candle 10 = 10:55

Orderplan:
  A: buy limit op 106, SL-basis 100, geldig tot 10:55 + 12 × 5 min = 11:55
  B: marktorder vanaf 10:55, SL-basis 100
"""
import pandas as pd

from katsu.bos import RETEST_VALID_BARS, detect_bos, make_bos_plan
from katsu.execution import Instrument
from katsu.structure import DOWN, NEUTRAL, UP

BASE = [  # high, low, open, close
    (100, 97, 99, 98),
    (99, 96, 98, 97),
    (103, 97.5, 97, 102.5),
    (104, 101, 102.5, 103.5),
    (103, 99, 103.5, 99.5),
    (101, 98, 99.5, 100.5),
    (106, 100, 100.5, 103.8),
    (105, 101, 103.8, 101.5),
    (104, 100, 101.5, 100.5),
    (105, 101, 100.5, 104.5),
    (108, 104, 104.5, 107),
]


def make(rows):
    idx = pd.date_range("2025-01-06 10:00", periods=len(rows), freq="5min")
    h, l, o, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)


def mirror(rows, axis=300):
    return [(axis - l, axis - h, axis - o, axis - c) for h, l, o, c in rows]


def run(rows, trend=UP):
    return detect_bos(make(rows), "5min", lambda t: trend, L=1)


def test_geldige_long_bos():
    sig = run(BASE)
    assert len(sig) == 1
    s = sig[0]
    assert s.direction == "LONG"
    assert (s.level, s.level_index, s.bos_index) == (106, 6, 10)
    assert (s.hl_price, s.hl_index) == (100, 8)
    assert s.signal_time == pd.Timestamp("2025-01-06 10:55")


def test_geldige_short_gespiegeld():
    sig = run(mirror(BASE), trend=DOWN)
    assert len(sig) == 1
    s = sig[0]
    assert s.direction == "SHORT"
    assert (s.level, s.bos_index, s.hl_price) == (300 - 106, 10, 300 - 100)


def test_wick_boven_niveau_is_geen_bos():
    rows = list(BASE)
    rows[10] = (108, 104, 104.5, 105.5)     # high 108, maar close 105,5 onder 106
    assert run(rows) == []


def test_alleen_met_de_h1_trend():
    assert run(BASE, trend=NEUTRAL) == []
    assert run(BASE, trend=DOWN) == []


def test_setup_timeframe_moet_ook_stijgen():
    rows = list(BASE)
    rows[8] = (104, 97, 101.5, 100.5)       # lower low 97 (< 98): lows dalen -> geen HH + HL
    assert run(rows) == []


def test_niveau_geeft_maar_een_keer_een_bos():
    rows = list(BASE) + [(109, 105, 107, 108.5)]   # nog een close boven 106
    assert len(run(rows)) == 1


def test_swing_bevestigd_op_de_bos_candle_telt_niet():
    # Zonder candle 9 zou swing low 8 pas bevestigd zijn OP candle 10 (te laat).
    # Candle 9 weglaten: 10 wordt candle 9 en de laatste bevestigde low is dan 98, niet 100.
    rows = BASE[:9] + [BASE[10]]
    rows[8] = (104, 100, 101.5, 100.5)
    sig = run(rows)
    assert len(sig) == 1 and sig[0].hl_price == 98


def test_orderplan_variant_a_en_b():
    s = run(BASE)[0]
    atr = pd.Series([1.0] * len(BASE))
    ins = Instrument("XAUUSD")
    a = make_bos_plan(s, "5min", atr, "A", ins)
    assert (a.kind, a.limit_price, a.anchor) == ("limit", 106, 100)
    assert RETEST_VALID_BARS == 12
    assert a.valid_until == pd.Timestamp("2025-01-06 11:55")
    b = make_bos_plan(s, "5min", atr, "B", ins)
    assert (b.kind, b.anchor, b.signal_time) == ("market", 100, pd.Timestamp("2025-01-06 10:55"))
