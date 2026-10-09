"""
Handberekende scenario's voor sweep + CHoCH (spec §3).

Basisscenario LONG (L=1, M5-candles). Vóór de sweep zit M5 in een correctie
met lower highs (115 -> 113) en lower lows (106 -> 103):
  idx  high   low   open  close
   0   112    108   110   111
   1   115    110   111   114   <- swing high 115 (bevestigd na 2)
   2   111    106   113   107   <- swing low 106 (bevestigd na 3)
   3   113    108   107   112   <- lower high 113 (bevestigd na 4)
   4   110    103   111   104   <- lower low 103 (bevestigd na 5)
   5   109    105   104   108
   6   107    102   106   104   <- SWEEP: low 102 onder 103, close 104 erboven
   7   112    104   104   111      (close 111 nog ONDER de lower high 113: geen CHoCH)
   8   115    110   111   114   <- CHoCH: close 114 boven de laatste lower high 113

Verwacht: 1 LONG-signaal, sweep op 6, sweep-low 102, geveegd niveau 103,
CHoCH op 8, CHoCH-niveau 113, signaal op het einde van candle 8 (10:45).
"""
import pandas as pd

from katsu.signals import detect_setups
from katsu.structure import DOWN, NEUTRAL, UP

BASE = [  # high, low, open, close
    (112, 108, 110, 111),
    (115, 110, 111, 114),
    (111, 106, 113, 107),
    (113, 108, 107, 112),
    (110, 103, 111, 104),
    (109, 105, 104, 108),
    (107, 102, 106, 104),
    (112, 104, 104, 111),
    (115, 110, 111, 114),
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
    assert (s.sweep_index, s.sweep_extreme, s.swept_level) == (6, 102, 103)
    assert (s.choch_index, s.choch_level) == (8, 113)
    assert s.signal_time == pd.Timestamp("2025-01-06 10:45")
    # body van de sweep-candle: |104-106| / (107-102)
    assert abs(s.sweep_body_pct - 0.4) < 1e-9


def test_geldige_short_gespiegeld():
    sig = run(mirror(BASE), trend=DOWN)
    assert len(sig) == 1
    s = sig[0]
    assert s.direction == "SHORT"
    assert (s.sweep_extreme, s.swept_level, s.choch_level) == (300 - 102, 300 - 103, 300 - 113)


def test_close_onder_niveau_is_run_geen_sweep():
    rows = list(BASE)
    rows[6] = (107, 102, 106, 102.5)    # sluit ONDER 103 -> run: niveau 103 is doorbroken
    rows[7] = (112, 102.5, 102.5, 111)  # prikt weer onder 103 en sluit erboven
    # Candle 6 is geen sweep (close onder het niveau). Daardoor is niveau 103 "opgebruikt":
    # candle 7 kan het niet meer sweepen. Geen signaal.
    assert run(rows) == []


def test_close_onder_geveegd_niveau_na_sweep_maakt_setup_ongeldig():
    rows = list(BASE)
    rows[7] = (105, 102.5, 104, 102.8)  # sluit onder 103 na de sweep -> run, setup vervalt
    rows[8] = (115, 102.6, 102.8, 114)
    sig = run(rows)
    # sweep op 6 vervalt; niveau 103 is doorbroken en candle 8 komt niet onder sweep-low 102
    # -> geen nieuwe sweep, geen signaal.
    assert sig == []


def test_choch_alleen_met_wick_telt_niet():
    rows = list(BASE)
    rows[8] = (115, 110, 111, 112.5)    # wick tot 115, close 112,5 onder 113
    assert run(rows) == []


def test_choch_buiten_venster_telt_niet():
    # met een venster van 1 candle moet de CHoCH op candle 7 komen; hij komt pas op 8
    assert run(BASE, choch_window=1) == []
    assert len(run(BASE, choch_window=2)) == 1


def test_geen_trade_tegen_of_zonder_trend():
    assert run(BASE, trend=NEUTRAL) == []
    assert run(BASE, trend=DOWN) == []


def test_lager_dan_sweep_low_vervangt_de_setup():
    rows = list(BASE)
    rows[7] = (112, 101, 104, 111)      # zakt onder sweep-low 102, sluit boven 103 -> nieuwe sweep
    sig = run(rows)
    assert len(sig) == 1
    assert (sig[0].sweep_index, sig[0].sweep_extreme) == (7, 101)


def test_swing_buiten_lookback_telt_niet():
    # swing low op 4, sweep op 6: met lookback 1 ligt de swing te ver terug
    assert run(BASE, sweep_lookback=1) == []
    assert len(run(BASE, sweep_lookback=2)) == 1


def test_swing_nog_niet_bevestigd_kan_niet_geveegd_worden():
    rows = list(BASE)
    # candle 5 prikt onder 103, maar swing low 4 wordt pas bevestigd ná candle 5
    rows[5] = (109, 102.9, 104, 108)
    sig = run(rows)
    assert all(s.sweep_index != 5 for s in sig)


def test_zonder_tegenbeweging_geen_choch():
    rows = list(BASE)
    rows[3] = (117, 108, 107, 112)      # higher high 117 i.p.v. lower high 113: geen dalende structuur
    assert run(rows) == []


def test_tegenbeweging_regel_is_echt_nodig():
    # Lows dalend maar highs STIJGEND (115 -> 113 wordt 115 -> 116): geen echte correctie.
    rows = list(BASE)
    rows[1] = (114, 110, 111, 113)      # eerste swing high 114 ...
    rows[3] = (116, 108, 107, 112)      # ... tweede 116: higher high
    rows[8] = (118, 110, 111, 117)      # close 117 boven 116: zonder regel zou dit een signaal zijn
    assert run(rows) == []
    assert len(run(rows, require_counter=False)) == 1


def test_multi_tf_trend_geeft_vier_timeframes():
    from katsu.signals import multi_tf_trend
    idx = pd.date_range("2025-01-06", periods=60 * 24 * 3, freq="1min")
    import numpy as np
    p = 100 + np.sin(np.arange(len(idx)) / 200.0) * 5
    m1 = pd.DataFrame({"open": p, "high": p + .1, "low": p - .1, "close": p, "tickvol": 1, "spread": 5}, index=idx)
    out = multi_tf_trend(m1)(pd.Timestamp("2025-01-08 12:00"))
    assert set(out) == {"M15", "H1", "H4", "D1"}
    assert all(v in ("UP", "DOWN", "NEUTRAL") for v in out.values())


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
