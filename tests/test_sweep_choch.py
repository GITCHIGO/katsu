"""
Handberekende scenario's voor sweep + CHoCH (spec §3).

Basisscenario LONG (L=1, M5-candles), candle per candle:
  idx  high   low   open  close
   0   105    100   102   103
   1   110    104   105   109   <- swing high 110 (bevestigd na candle 2)
   2   108    102   108   103
   3   106     98   103    99   <- swing low 98 (bevestigd na candle 4)
   4   107    100   100   106   <- swing high 107 (bevestigd na candle 5)
   5   104     97   103    99   <- SWEEP: low 97 onder 98, close 99 boven 98
   6   106    100    99   105
   7   109    104   105   108   <- CHoCH: close 108 boven laatste swing high vóór de sweep (107)

Verwacht: 1 LONG-signaal, sweep op 5, sweep-low 97, geveegd niveau 98,
CHoCH op 7, CHoCH-niveau 107, signaal op het einde van candle 7 (10:40).
"""
import pandas as pd

from katsu.signals import detect_setups
from katsu.structure import DOWN, NEUTRAL, UP

BASE = [  # high, low, open, close
    (105, 100, 102, 103),
    (110, 104, 105, 109),
    (108, 102, 108, 103),
    (106, 98, 103, 99),
    (107, 100, 100, 106),
    (104, 97, 103, 99),
    (106, 100, 99, 105),
    (109, 104, 105, 108),
]


def make(rows):
    idx = pd.date_range("2025-01-06 10:00", periods=len(rows), freq="5min")
    h, l, o, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)


def always(trend):
    return lambda t: trend


def mirror(rows, axis=300):
    """Spiegelt een scenario: long wordt short (high en low wisselen)."""
    return [(axis - l, axis - h, axis - o, axis - c) for h, l, o, c in rows]


def run(rows, trend=UP, **kw):
    kw.setdefault("L", 1)
    return detect_setups(make(rows), "5min", always(trend), **kw)


def test_geldige_long():
    sig = run(BASE)
    assert len(sig) == 1
    s = sig[0]
    assert s.direction == "LONG"
    assert (s.sweep_index, s.sweep_extreme, s.swept_level) == (5, 97, 98)
    assert (s.choch_index, s.choch_level) == (7, 107)
    assert s.signal_time == pd.Timestamp("2025-01-06 10:40")
    # body van de sweep-candle: |99-103| / (104-97)
    assert abs(s.sweep_body_pct - 4 / 7) < 1e-9


def test_geldige_short_gespiegeld():
    sig = run(mirror(BASE), trend=DOWN)
    assert len(sig) == 1
    s = sig[0]
    assert s.direction == "SHORT"
    assert (s.sweep_extreme, s.swept_level, s.choch_level) == (300 - 97, 300 - 98, 300 - 107)


def test_close_onder_niveau_is_run_geen_sweep():
    rows = list(BASE)
    rows[5] = (104, 97, 103, 97.5)      # sluit ONDER 98 -> run: niveau 98 is doorbroken
    rows[6] = (106, 97.5, 97.5, 105)    # prikt weer onder 98 en sluit erboven
    # Candle 5 is geen sweep (close onder het niveau). Daardoor is niveau 98 "opgebruikt":
    # candle 6 kan het niet meer sweepen. Geen signaal.
    assert run(rows) == []


def test_close_onder_geveegd_niveau_na_sweep_maakt_setup_ongeldig():
    rows = list(BASE)
    rows[6] = (100, 97.5, 99, 97.8)     # sluit onder 98 na de sweep -> run, setup vervalt
    rows[7] = (109, 97.6, 97.8, 108)
    sig = run(rows)
    # sweep op 5 vervalt. Candle 7 (low 97.6 < 98, close 108 > 98) is een nieuwe sweep,
    # maar er volgt geen CHoCH meer -> geen signaal.
    assert sig == []


def test_choch_alleen_met_wick_telt_niet():
    rows = list(BASE)
    rows[7] = (109, 104, 105, 106.5)    # wick tot 109, close 106,5 onder 107
    assert run(rows) == []


def test_choch_buiten_venster_telt_niet():
    # met een venster van 1 candle moet de CHoCH op candle 6 komen; hij komt pas op 7
    assert run(BASE, choch_window=1) == []
    assert len(run(BASE, choch_window=2)) == 1


def test_geen_trade_tegen_of_zonder_trend():
    assert run(BASE, trend=NEUTRAL) == []
    assert run(BASE, trend=DOWN) == []


def test_lager_dan_sweep_low_vervangt_de_setup():
    rows = list(BASE)
    rows[6] = (106, 96, 99, 105)        # zakt onder sweep-low 97, sluit boven 98 -> nieuwe sweep
    sig = run(rows)
    assert len(sig) == 1
    assert (sig[0].sweep_index, sig[0].sweep_extreme) == (6, 96)


def test_swing_buiten_lookback_telt_niet():
    # swing low op 3, sweep op 5: met lookback 1 ligt de swing te ver terug
    assert run(BASE, sweep_lookback=1) == []
    assert len(run(BASE, sweep_lookback=2)) == 1


def test_swing_nog_niet_bevestigd_kan_niet_geveegd_worden():
    rows = list(BASE)
    # candle 4 prikt al onder 98 en sluit erboven, maar swing low 3 is pas bevestigd ná candle 4
    rows[4] = (107, 97.9, 100, 106)
    sig = run(rows)
    assert all(s.sweep_index != 4 for s in sig)


def test_h1_trend_kijkt_niet_vooruit():
    from katsu.signals import h1_trend_lookup
    # zigzag op H1 met L=1: swings worden pas bevestigd een candle later
    pts = [("L", 10), ("H", 20), ("L", 12), ("H", 24), ("L", 15), ("H", 30), ("L", 18)]
    rows = [(p, p - 1, p - .5, p - .5) if k == "H" else (p + 1, p, p + .5, p + .5) for k, p in pts]
    idx = pd.date_range("2025-01-06 00:00", periods=len(rows), freq="1h")
    h, l, o, c = zip(*rows)
    h1 = pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)
    trend = h1_trend_lookup(h1, L=1)
    # Om 01:30 is enkel candle 0 gesloten: nog geen enkele swing bevestigd -> NEUTRAL.
    # Om 06:00 is candle 5 gesloten: highs 20, 24 en lows 12, 15 bevestigd -> UP.
    assert trend(pd.Timestamp("2025-01-06 01:30")) == NEUTRAL
    assert trend(pd.Timestamp("2025-01-06 06:00")) == UP
