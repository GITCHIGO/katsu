"""
Tests voor laag 1 (katsu/research.py), met handberekende scenario's.

Beugel-meting (ATR = 1 overal, instap = open van candle 1 = 100, LONG):
  candle 1: high 100,5 low 99,5   -> mee 0,5  tegen 0,5
  candle 2: high 101,2 low 99,8   -> mee 1,2  -> R11 = +1 (TP 1 ATR geraakt)
  candle 3: high 102,1 low 100,5  -> mee 2,1  -> R21 = +2
  MFE = 2,1 · MAE = 0,5
"""
import numpy as np
import pandas as pd
import pytest

from katsu import research as R

ONE = np.ones(10)


def bars_from(rows, start="2025-01-06 10:00", freq="5min"):
    idx = pd.date_range(start, periods=len(rows), freq=freq)
    o, h, l, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)


UP_ROWS = [(100, 100, 100, 100), (100, 100.5, 99.5, 100.2), (100.2, 101.2, 99.8, 101), (101, 102.1, 100.5, 102)]


def test_beugel_long_handberekend():
    m = R.measure(bars_from(UP_ROWS), ONE, np.array([0]), np.array([1]), max_bars=3).iloc[0]
    assert (m.R21, m.R11) == (2.0, 1.0)
    assert m.mfe24 == pytest.approx(2.1) and m.mae24 == pytest.approx(0.5)


def test_beugel_short_is_spiegelbeeld():
    rows = [(300 - o, 300 - l, 300 - h, 300 - c) for o, h, l, c in UP_ROWS]
    m = R.measure(bars_from(rows), ONE, np.array([0]), np.array([-1]), max_bars=3).iloc[0]
    assert (m.R21, m.R11) == (2.0, 1.0)


def test_beugel_sl_en_tp_in_zelfde_candle_telt_sl():
    rows = [(100, 100, 100, 100), (100, 102.5, 98.9, 100), (100, 100, 100, 100), (100, 100, 100, 100)]
    m = R.measure(bars_from(rows), ONE, np.array([0]), np.array([1]), max_bars=3).iloc[0]
    assert (m.R21, m.R11) == (-1.0, -1.0)


def test_beugel_niets_geraakt_eindigt_op_laatste_close():
    rows = [(100, 100, 100, 100), (100, 100.4, 99.7, 100.1), (100.1, 100.6, 99.9, 100.3), (100.3, 100.5, 100, 100.4)]
    m = R.measure(bars_from(rows), ONE, np.array([0]), np.array([1]), max_bars=3).iloc[0]
    assert m.R21 == pytest.approx(0.4) and m.R11 == pytest.approx(0.4)


def test_limiet_instap_telt_tp_niet_op_de_vulcandle():
    # instap op 100 in candle 1 (limiet); candle 1 gaat tot 102,5 maar dat telt niet; daarna niets
    rows = [(101, 101, 101, 101), (101, 102.5, 100, 101), (101, 101.5, 100.5, 101), (101, 101.2, 100.6, 101)]
    m = R.measure(bars_from(rows), ONE, np.array([0]), np.array([1]),
                  entry_bar=np.array([1]), entry_price=np.array([100.0]), max_bars=3).iloc[0]
    assert m.R21 == pytest.approx(1.0)          # TP niet op candle 1; einde op close 101 = +1 ATR
    assert m.R11 == pytest.approx(1.0)          # +1 wordt pas op candle 2 geraakt (high 101,5)


def test_geen_volledige_toekomst_geeft_nan():
    m = R.measure(bars_from(UP_ROWS), ONE, np.array([2]), np.array([1]), max_bars=3)
    assert np.isnan(m.R21.iloc[0])


def test_choch_met_sweep_handscenario():
    from tests.test_sweep_choch import BASE, make
    ev = R.choch_events(make(BASE), L=1)
    longs = ev[ev.d == 1]
    assert list(longs.k) == [8]                 # close 114 boven de lower high 113
    assert bool(longs.sweep.iloc[0])            # candle 6 prikte onder swing low 103 en sloot erboven


def test_bos_events_hergebruikt_detect_bos_zonder_filter():
    from tests.test_bos import BASE, make
    ev = R.bos_events(make(BASE), "5min", 1)
    assert list(zip(ev.k, ev.d)) == [(10, 1)]


def test_vorige_dag_sweep():
    # dag 1: high 10, low 5 · dag 2: low-sweep (low 4,5 close 5,5) -> LONG, tweede keer niet meer;
    # high-sweep (high 10,5 close 9,8) -> SHORT
    idx = pd.to_datetime(["2025-01-06 10:00", "2025-01-06 11:00", "2025-01-07 10:00", "2025-01-07 11:00",
                          "2025-01-07 12:00"])
    b = pd.DataFrame({"open": [7, 8, 6, 5, 9], "high": [10, 9, 6.5, 5.5, 10.5], "low": [5, 6, 4.5, 4, 8.5],
                      "close": [8, 7, 5.5, 4.8, 9.8]}, index=idx)
    ev = R.level_sweep_events(b, "day")
    assert list(zip(ev.k, ev.d)) == [(2, 1), (4, -1)]


def test_azie_range_sweep():
    hrs = list(range(1, 9)) + [10]
    idx = pd.to_datetime([f"2025-01-06 {h:02d}:00" for h in hrs])
    hi = [101, 102, 101.5, 101, 101.2, 101.8, 101.1, 101.4, 102.5]
    lo = [100, 100.5, 100.2, 100.1, 100.3, 100.4, 100.2, 100.5, 101.5]
    cl = [100.5, 101, 101, 100.5, 101, 101, 100.8, 101, 101.9]
    b = pd.DataFrame({"open": cl, "high": hi, "low": lo, "close": cl}, index=idx)
    ev = R.level_sweep_events(b, "asia")
    assert list(zip(ev.k, ev.d)) == [(8, -1)]   # 10:00 prikt boven 102 en sluit eronder


def test_fvg_vorming_retest_en_inverse():
    from tests.test_fvg import BASE, make
    rows = list(BASE) + [(102.5, 102.6, 100.2, 100.5)]   # close 100,5 onder de onderkant 101 -> inverse
    ev = R.fvg_events(make(rows))
    assert list(zip(ev["vorming"].k, ev["vorming"].d)) == [(2, 1)]
    r = ev["retest"].iloc[0]
    assert (r.k, r.d, r.entry_bar, r.entry_price) == (2, 1, 3, 102)   # candle 3 raakt de bovenkant
    assert list(zip(ev["inverse"].k, ev["inverse"].d)) == [(5, -1)]


def test_verkenning_en_bevestiging_overlappen_nooit_en_sluiten_2025_uit():
    t = pd.to_datetime(["2019-06-03", "2020-01-15", "2020-02-15", "2024-11-02", "2024-12-02", "2025-01-03"])
    e, c = R.explore_mask(t), R.confirm_mask(t)
    assert list(e) == [True, True, False, True, False, False]
    assert list(c) == [False, False, True, False, True, False]
    assert not np.any(e & c)


def test_geclusterde_standaardfout():
    m, se = R.clustered_t(np.array([1.0, 3.0]), np.array([1, 1]))
    assert (m, se) == (2.0, 0.0)                 # zelfde week: afwijkingen heffen elkaar op
    m, se = R.clustered_t(np.array([1.0, 3.0]), np.array([1, 2]))
    assert se == pytest.approx(np.sqrt(2) / 2)


def test_hogere_timeframe_kijkt_niet_vooruit():
    rng = np.random.default_rng(5)
    p = 100 + np.cumsum(rng.normal(0, 1, 3000))
    b = pd.DataFrame({"open": p, "high": p + 0.5, "low": p - 0.5, "close": p},
                     index=pd.date_range("2024-01-01", periods=3000, freq="1h"))
    full = R.htf_trend(b, "1h", "4h")
    part = R.htf_trend(b.iloc[:2000], "1h", "4h")
    assert list(full[:2000]) == list(part)       # toekomst verandert het verleden niet
    assert set(full) <= {"UP", "DOWN", "NEUTRAL"} and "UP" in set(full)


def test_hogere_timeframe_gelijk_aan_trend_lookup():
    from katsu.signals import trend_lookup
    rng = np.random.default_rng(6)
    p = 100 + np.cumsum(rng.normal(0, 1, 2000))
    b = pd.DataFrame({"open": p, "high": p + 0.5, "low": p - 0.5, "close": p},
                     index=pd.date_range("2024-01-01", periods=2000, freq="15min"))
    arr = R.htf_trend(b, "15min", "1h")
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    tl = trend_lookup(b.resample("1h", label="left", closed="left").agg(agg).dropna(), "1h", 3)
    ref = [tl(t + pd.Timedelta("15min")) for t in b.index]
    assert list(arr) == ref


def test_basislijn_zelfde_uur_en_richting():
    rng = np.random.default_rng(2)
    p = 100 + np.cumsum(rng.normal(0, 1, 500))
    b = pd.DataFrame({"open": p, "high": p + 1, "low": p - 1, "close": p},
                     index=pd.date_range("2024-01-01", periods=500, freq="1h"))
    pool = np.arange(0, 400)
    bl = R.baseline(b, np.ones(500), np.array([10, 34]), np.array([1, -1]), pool, per_event=5)
    assert len(bl) == 10
    hours = b.index.hour.to_numpy()
    assert all(hours[k] == 10 for k in bl.k[:5]) and all(hours[k] == 10 for k in bl.k[5:])  # 10 en 34 = 10u
    assert list(bl.d) == [1] * 5 + [-1] * 5
    assert all(k in pool for k in bl.k)


def test_basislijn_zonder_vergelijkbare_candle_geeft_nan_en_blijft_uitgelijnd():
    rng = np.random.default_rng(3)
    p = 100 + np.cumsum(rng.normal(0, 1, 300))
    b = pd.DataFrame({"open": p, "high": p + 1, "low": p - 1, "close": p},
                     index=pd.date_range("2024-01-01", periods=300, freq="1h"))
    strata = np.array(["A"] * 300, dtype=object); strata[50] = "B"     # stratum B bestaat niet in de pool
    bl = R.baseline(b, np.ones(300), np.array([10, 50]), np.array([1, 1]), np.arange(0, 40), strata=strata)
    assert len(bl) == 10
    assert bl.R21.iloc[:5].notna().all() and bl.R21.iloc[5:].isna().all()
