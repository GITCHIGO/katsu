"""
Silver Bullet (spec v0.5), met de hand uitgerekend. M15, L = 1, venster NY AM = 17:00–18:00 servertijd.

 idx tijd   open  high  low   close
 0  15:30   100   101   99    100
 1  15:45   100   100,5 98    99      swing low 98 (bevestigd op 2) = liquiditeit onder de markt
 2  16:00   99    103   99,5  102,5
 3  16:15   102,5 104   101   103,5   swing high 104 (bevestigd op 4) = oude high, later TP
 4  16:30   103,5 103,5 101   101,5
 5  16:45   101,5 102   100   100,5
 6  17:00   100,5 100,8 97,5  98      begin venster; low 97,5 < 98 -> sweep van de swing low
 7  17:15   98    99    97,8  98,8    bearish FVG (high 99 < low(5) 100) -> eerste FVG in het venster (SHORT)
 8  17:30   98,8  101,5 98,7  101,2
 9  17:45   101,2 102,5 99,6  102,2   bullish FVG (low 99,6 > high(7) 99), sluit om 18:00 = einde venster
10  18:00   102,2 102,4 100   100,5
'alle'  -> SHORT op 7 (eerste FVG); 'sweep' -> de short heeft geen sweep (104 niet geraakt) -> LONG op 9.
LONG op 9: entry 99,6 · SL-basis = laagste low 6..9 = 97,5 · TP = 104 (boven de top van de beweging 102,5).
SHORT op 7: entry 99 (onderkant gat) · SL-basis = hoogste high 6..7 = 100,8 · geen oude low onder 97,5 -> TP None (2R).
"""
import pandas as pd
import pytest

from katsu.silver import make_sb_plan, sb_setups

ROWS = [(100, 101, 99, 100), (100, 100.5, 98, 99), (99, 103, 99.5, 102.5), (102.5, 104, 101, 103.5),
        (103.5, 103.5, 101, 101.5), (101.5, 102, 100, 100.5), (100.5, 100.8, 97.5, 98), (98, 99, 97.8, 98.8),
        (98.8, 101.5, 98.7, 101.2), (101.2, 102.5, 99.6, 102.2), (102.2, 102.4, 100, 100.5)]


def bars():
    idx = pd.date_range("2018-03-05 15:30", periods=len(ROWS), freq="15min")
    o, h, l, c = zip(*ROWS)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "spread": 0}, index=idx)


def test_alle_neemt_de_eerste_fvg():
    (s,) = sb_setups(bars(), "15min", "alle", windows=["ny_am"], L=1)
    assert (s.direction, s.k, s.window_start) == ("SHORT", 7, 6)
    assert (s.entry, s.anchor, s.tp, s.swept) == (99, 100.8, None, False)


def test_sweep_vereist_liquiditeit_genomen_in_het_venster():
    (s,) = sb_setups(bars(), "15min", "sweep", windows=["ny_am"], L=1)
    assert (s.direction, s.k, s.entry, s.anchor, s.tp, s.swept) == ("LONG", 9, 99.6, 97.5, 104, True)
    assert s.window_end == pd.Timestamp("2018-03-05 18:00")


def test_bias_filtert_op_h1_trend():
    b = bars()
    up = ["UP"] * len(b)
    (s,) = sb_setups(b, "15min", "bias", trend=up, windows=["ny_am"], L=1)
    assert (s.direction, s.k) == ("LONG", 9)
    assert sb_setups(b, "15min", "bias", trend=["NEUTRAL"] * len(b), windows=["ny_am"], L=1) == []


def test_buiten_het_venster_niets():
    assert sb_setups(bars(), "15min", "alle", windows=["london", "ny_pm"], L=1) == []


def test_orderplan_long_en_short():
    b = bars()
    a = [1.0] * len(b)
    (lg,) = sb_setups(b, "15min", "sweep", windows=["ny_am"], L=1)
    p = make_sb_plan(lg, b, a, "EURUSD", "15min")
    # geplande SL 97,4 · risico 2,2 · 2R = 99,6 + 4,4 = 104,0 -> oude high 104 is even ver: cancel 104
    assert p.limit_price == 99.6 and p.anchor == 97.5 and p.tp_price == 104 and p.max_rr == 2.0
    assert p.cancel_price == pytest.approx(104.0)
    assert p.signal_time == pd.Timestamp("2018-03-05 18:00") and p.valid_until == p.signal_time  # venster voorbij
    (sh,) = sb_setups(b, "15min", "alle", windows=["ny_am"], L=1)
    q = make_sb_plan(sh, b, a, "EURUSD", "15min")
    # SHORT: geplande SL 100,9 · risico 1,9 · geen oude low -> TP via 2R (engine), cancel op 99 − 3,8 = 95,2
    assert q.tp_price is None and q.max_rr is None and q.cancel_price == pytest.approx(95.2)
    assert q.valid_until == pd.Timestamp("2018-03-05 18:00") and q.signal_time == pd.Timestamp("2018-03-05 17:30")
