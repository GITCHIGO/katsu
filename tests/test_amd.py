"""AMD / Power of 3 (spec v0.6) — met de hand opgebouwde dag, M15, servertijd."""
import numpy as np
import pandas as pd
import pytest

from katsu.amd import amd_setups, make_amd_plan

DAY = pd.Timestamp("2025-01-06")


def _day(special: dict, drop=()):
    """96 candles van 00:00 tot 23:45; standaard vlak (o=c=1.1005, h=1.1006, l=1.1004).
    Azië-range 02:00–06:45: high 1.1010 (03:00), low 1.1000 (04:00). special: {'HH:MM': (o,h,l,c)}."""
    idx = pd.date_range(DAY, periods=96, freq="15min")
    rows = {t: (1.1005, 1.1006, 1.1004, 1.1005) for t in idx}
    rows[DAY + pd.Timedelta("03:00:00")] = (1.1005, 1.1010, 1.1004, 1.1005)
    rows[DAY + pd.Timedelta("04:00:00")] = (1.1005, 1.1006, 1.1000, 1.1005)
    for k, v in special.items():
        rows[DAY + pd.Timedelta(k + ":00")] = v
    df = pd.DataFrame([rows[t] for t in idx], index=idx, columns=["open", "high", "low", "close"])
    return df.drop(index=[DAY + pd.Timedelta(k + ":00") for k in drop])


# Manipulatie onder Azië-low (1.1000) en MO (1.1005) om 08:00, terug in de range om 08:15, boven MO om 08:30.
# FVG: high 08:00 = 1.0998 < low 08:30 = 1.1001.
BULL = {"08:00": (1.0997, 1.0998, 1.0990, 1.0995),
        "08:15": (1.0995, 1.1004, 1.0994, 1.1003),
        "08:30": (1.1003, 1.1009, 1.1001, 1.1008)}


def _mirror(df):
    """Spiegel rond 1.1: prijs p -> 2.2 - p (high en low wisselen)."""
    return pd.DataFrame({"open": 2.2 - df.open, "high": 2.2 - df.low, "low": 2.2 - df.high, "close": 2.2 - df.close},
                        index=df.index)


def _t(k, df):
    return df.index[k].strftime("%H:%M")


def test_c2_markt_long():
    df = _day(BULL)
    (s,) = amd_setups(df, confirm="open", entry="market")
    assert s.direction == "LONG" and _t(s.k_sweep, df) == "08:00" and _t(s.k_conf, df) == "08:30"
    assert s.asia_hi == 1.1010 and s.asia_lo == 1.1000 and s.mo == 1.1005
    assert s.anchor == 1.0990 and s.tp == 1.1010 and s.entry is None
    p = make_amd_plan(s, df, np.full(len(df), 0.0010), "EURUSD")
    assert p.kind == "market" and p.signal_time == DAY + pd.Timedelta("08:45:00") and p.tp_price == 1.1010


def test_c1_bevestigt_vroeger():
    df = _day(BULL)
    (s,) = amd_setups(df, confirm="range", entry="market")
    assert _t(s.k_conf, df) == "08:15"                  # close 1.1003 > Azië-low 1.1000


def test_e2_fvg_entry_382():
    df = _day(BULL)
    (s,) = amd_setups(df, confirm="open", entry="fvg")
    # FVG 1.0998–1.1001; 38,2% diep vanaf de bovenrand: 1.1001 − 0,382 × 0,0003 = 1.10008854
    assert s.fvg[2] == pytest.approx(1.0998) and s.fvg[3] == pytest.approx(1.1001)
    assert s.entry == pytest.approx(1.1001 - 0.382 * 0.0003)
    p = make_amd_plan(s, df, np.full(len(df), 0.0010), "EURUSD")
    assert p.kind == "limit" and p.valid_until == DAY + pd.Timedelta("18:00:00") and p.cancel_price == 1.1010


def test_e2_zonder_fvg_geen_setup():
    # bij C1 is de bevestiging 08:15: geen FVG met c1 >= 08:00 en c3 <= 08:15
    assert amd_setups(_day(BULL), confirm="range", entry="fvg") == []


def test_short_gespiegeld():
    df = _mirror(_day(BULL))
    (s,) = amd_setups(df, confirm="open", entry="fvg")
    assert s.direction == "SHORT" and _t(s.k_conf, df) == "08:30"
    assert s.anchor == pytest.approx(2.2 - 1.0990) and s.tp == pytest.approx(2.2 - 1.1010)
    assert s.entry == pytest.approx(2.2 - (1.1001 - 0.382 * 0.0003))


def test_trendfilter():
    df = _day(BULL)
    assert amd_setups(df, trend=np.full(len(df), "DOWN", dtype=object)) == []
    assert len(amd_setups(df, trend=np.full(len(df), "UP", dtype=object))) == 1


def test_beide_kanten_zelfde_candle_geen_setup():
    # 08:00 veegt boven én onder en sluit midden in de range: C1 bevestigt beide kanten tegelijk
    df = _day({"08:00": (1.1005, 1.1015, 1.0990, 1.1005)})
    assert amd_setups(df, confirm="range") == []


def test_geen_sweep_onder_open():
    # midnight open 1.0995 ligt onder de Azië-low; low 1.0997 zit onder de Azië-low maar niet onder de open
    df = _day({"07:00": (1.0995, 1.1006, 1.0995, 1.1005), "08:00": (1.1000, 1.1001, 1.0997, 1.1006)})
    assert amd_setups(df, confirm="range") == []


def test_ontbrekende_midnight_open():
    assert amd_setups(_day(BULL, drop=["07:00"])) == []


def test_bevestiging_na_venster_telt_niet():
    # sweep om 11:30, terug boven de open pas om 12:00 (buiten het venster)
    df = _day({"11:30": (1.1005, 1.1005, 1.0990, 1.0995), "11:45": (1.0995, 1.1000, 1.0994, 1.0999),
               "12:00": (1.0999, 1.1009, 1.0998, 1.1008)})
    assert amd_setups(df, confirm="open") == []


def test_dagfilter():
    df = _day(BULL)
    assert amd_setups(df, day_mask=lambda t: np.zeros(len(t), bool)) == []


def test_amd_dag_label():
    from katsu.amd import amd_day_labels, amd_day_map
    df = _day(BULL)
    m = amd_day_map(amd_setups(df, confirm="open"), df)      # long, bekend om 08:45
    assert m == {DAY: (1, DAY + pd.Timedelta("08:45:00"))}
    t = pd.DatetimeIndex([DAY + pd.Timedelta("08:30:00"), DAY + pd.Timedelta("08:45:00"), DAY + pd.Timedelta("14:00:00"),
                          DAY + pd.Timedelta("14:00:00"), DAY + pd.Timedelta("1 days 09:00:00"), DAY])
    d = np.array([1, 1, 1, -1, 1, 1])
    # te vroeg · net bekend · later mee · later tegen · volgende dag · signaal om 00:00 hoort bij de dag ervoor
    assert list(amd_day_labels(t, d, m)) == ["geen", "mee", "mee", "tegen", "geen", "geen"]
