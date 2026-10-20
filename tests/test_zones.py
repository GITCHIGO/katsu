"""Zones (spec v0.7) — met de hand opgebouwde H4-reeks."""
import numpy as np
import pandas as pd
import pytest

from katsu.zones import find_zones, make_zone_plan, zone_entry

ROWS = [  # o, h, l, c
    (9.5, 10.0, 9.0, 9.8), (9.8, 10.2, 9.4, 10.0),
    (10.0, 10.5, 9.5, 10.0), (10.0, 11.0, 9.8, 10.8),
    (10.8, 12.0, 10.6, 11.8),          # 4: swing high 12.0 (bevestigd op 7)
    (11.8, 11.9, 11.0, 11.2), (11.2, 11.5, 10.5, 10.6),
    (10.6, 11.0, 10.0, 10.2),          # 7: dalend
    (10.2, 10.4, 9.0, 9.2),            # 8: dalend, laagste low 9.0 = oorsprong en order block
    (9.2, 10.5, 9.1, 10.4), (10.4, 11.8, 10.3, 11.7),
    (11.7, 12.6, 11.6, 12.5),          # 11: eerste close boven 12.0 = breuk; FVG: low 11.6 > high[9] 10.5
]


def _bars(rows=ROWS):
    idx = pd.date_range("2025-03-03", periods=len(rows), freq="4h")
    return pd.DataFrame(rows, index=idx, columns=["open", "high", "low", "close"])


def _mirror(df, m=30.0):
    return pd.DataFrame({"open": m - df.open, "high": m - df.low, "low": m - df.high, "close": m - df.close}, index=df.index)


def test_demandzone():
    df = _bars()
    zs = [z for z in find_zones(df, np.full(len(df), 1.0)) if z.direction == "LONG"]
    assert len(zs) == 1
    z = zs[0]
    assert (z.k, z.o, z.ob) == (11, 8, 8)
    assert z.top == 10.4 and z.bottom == 9.0 and z.leg_high == 12.6 and z.fvg
    assert zone_entry(z, "rand") == 10.4
    assert zone_entry(z, "38.2") == pytest.approx(10.4 - 0.382 * 1.4)     # 9.8652


def test_te_zwak_vertrek_of_te_hoge_zone():
    df = _bars()
    # kracht 12.5 − 9.0 = 3.5 < 2 × 2.0
    assert [z for z in find_zones(df, np.full(len(df), 2.0)) if z.direction == "LONG"] == []
    # zone 1.4 hoog > 1,5 × 0.9 = 1.35
    assert [z for z in find_zones(df, np.full(len(df), 0.9)) if z.direction == "LONG"] == []


def test_supplyzone_gespiegeld():
    df = _mirror(_bars())
    zs = [z for z in find_zones(df, np.full(len(df), 1.0)) if z.direction == "SHORT"]
    assert len(zs) == 1
    z = zs[0]
    assert z.top == pytest.approx(19.6) and z.bottom == pytest.approx(21.0) and z.leg_high == pytest.approx(17.4)
    assert zone_entry(z, "38.2") == pytest.approx(19.6 + 0.382 * 1.4)      # dieper = hoger bij short


def test_plan():
    df = _bars()
    z = [z for z in find_zones(df, np.full(len(df), 1.0)) if z.direction == "LONG"][0]
    p = make_zone_plan(z, df, "38.2", "EURUSD", "4h")
    assert p.kind == "limit" and p.signal_time == df.index[11] + pd.Timedelta("4h")
    assert p.valid_until == p.signal_time + pd.Timedelta(days=7)
    assert p.anchor == 9.0 and p.tp_price == 12.6 and p.cancel_price == 12.6 and p.max_rr == 2.0


def test_geen_breuk_zonder_bevestigde_swing():
    # zelfde reeks maar de laatste candle sluit onder 12.0: geen breuk, geen zone
    rows = ROWS[:-1] + [(11.7, 12.6, 11.6, 11.9)]
    df = _bars(rows)
    assert [z for z in find_zones(df, np.full(len(df), 1.0)) if z.direction == "LONG"] == []


def test_tp_bij_vulling_v07b():
    from katsu.zones import make_zone_plan_b, tp_at_fill
    df = _bars()
    z = [z for z in find_zones(df, np.full(len(df), 1.0)) if z.direction == "LONG"][0]
    h = np.array([12.0, 12.9, 13.4, 11.0, 10.0]); lo = np.array([11.5, 12.0, 12.5, 10.2, 9.8])
    # na de zone: highs 12.0, 12.9, 13.4, daarna terugkeer; vulling op index 4 -> TP = 13.4 (hoogste vóór de vulling)
    assert tp_at_fill(z, h, lo, 0, 4) == 13.4
    assert tp_at_fill(z, h, lo, 0, 0) == 12.6          # meteen gevuld: top van het vertrekbeen
    p = make_zone_plan_b(z, df, "rand", "EURUSD", "4h", tp=13.4)
    assert p.cancel_price is None and p.tp_price == 13.4 and p.max_rr == 2.0
    z2 = [z for z in find_zones(_mirror(df), np.full(len(df), 1.0)) if z.direction == "SHORT"][0]
    assert tp_at_fill(z2, 30 - lo, 30 - h, 0, 4) == pytest.approx(30 - 13.4)
