"""Tests voor inladen, controleren en omzetten van koersdata."""
import pandas as pd

from katsu.data import last_closed_index, resample, validate


def m1(n=10, start="2025-01-06 10:00"):
    idx = pd.date_range(start, periods=n, freq="1min")
    v = [float(i) for i in range(n)]
    return pd.DataFrame({"open": v, "high": [x + 1 for x in v], "low": [x - 1 for x in v],
                         "close": v, "tickvol": 1, "spread": 5}, index=idx)


def test_validate_schone_data():
    assert validate(m1()).ok


def test_validate_vindt_high_onder_low():
    d = m1(); d.iloc[3, d.columns.get_loc("high")] = -5
    r = validate(d)
    assert not r.ok and r.high_below_low == 1


def test_validate_vindt_dubbele_tijden():
    d = pd.concat([m1(3), m1(3)])
    r = validate(d)
    assert not r.ok and r.duplicates == 3


def test_resample_m5_label_is_begintijd():
    b = resample(m1(10), "5min")
    assert list(b.index.strftime("%H:%M")) == ["10:00", "10:05"]
    first = b.iloc[0]
    assert (first.open, first.high, first.low, first.close) == (0, 5, -1, 4)


def test_last_closed_index_gebruikt_geen_lopende_candle():
    b = resample(m1(10), "5min")
    # Om 10:07 loopt de candle van 10:05 nog: alleen 10:00 is gesloten.
    assert last_closed_index(b, "5min", pd.Timestamp("2025-01-06 10:07")) == 0
    # Om 10:10 is ook 10:05 gesloten.
    assert last_closed_index(b, "5min", pd.Timestamp("2025-01-06 10:10")) == 1
    # Vóór 10:05 is er nog niets gesloten.
    assert last_closed_index(b, "5min", pd.Timestamp("2025-01-06 10:04")) == -1
