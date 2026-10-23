"""KATSU Replay: codering van episodes moet exact terug te lezen zijn (geen afrondingsfouten, juiste tijden)."""
import numpy as np
import pandas as pd

from katsu.replay import decode, encode, episode_frame, pick_mondays


def frame():
    idx = pd.DatetimeIndex(["2021-03-05 23:58", "2021-03-05 23:59", "2021-03-08 00:00", "2021-03-08 00:01",
                            "2021-03-08 00:05"])
    return pd.DataFrame({"open": [1.19001, 1.19011, 1.19105, 1.19090, 1.19050],
                         "high": [1.19020, 1.19015, 1.19120, 1.19095, 1.19077],
                         "low": [1.18990, 1.19000, 1.19080, 1.19040, 1.19049],
                         "close": [1.19010, 1.19002, 1.19090, 1.19050, 1.19060],
                         "spread": [2, 3, 15, 4, 2]}, index=idx)


def test_roundtrip_eurusd():
    m1 = frame()
    meta, back = decode(encode(m1, "EURUSD", "eur01", pd.Timestamp("2021-03-08")))
    assert meta["start"] == 2 and meta["id"] == "eur01" and meta["digits"] == 5
    assert list(back.index) == list(m1.index)                       # weekendgat en ontbrekende minuten blijven
    for col in ("open", "high", "low", "close"):
        assert np.allclose(back[col], m1[col], atol=1e-9)
    assert list(back.spread) == [2, 3, 15, 4, 2]


def test_roundtrip_goud():
    m1 = frame() * 1
    m1[["open", "high", "low", "close"]] = m1[["open", "high", "low", "close"]] * 1500
    m1[["open", "high", "low", "close"]] = m1[["open", "high", "low", "close"]].round(2)
    _, back = decode(encode(m1, "XAUUSD", "xau01", pd.Timestamp("2021-03-08")))
    assert np.allclose(back[["open", "high", "low", "close"]], m1[["open", "high", "low", "close"]], atol=1e-9)


def test_maandagen_alleen_oneven_maanden_en_genoeg_data():
    idx = pd.date_range("2021-02-01", "2021-04-30 23:59", freq="1min")
    idx = idx[idx.dayofweek < 5]
    rng = np.random.default_rng(1)
    mons = pick_mondays(idx, 10, rng)
    assert mons and all(m.dayofweek == 0 and m.month == 3 and m.day <= 14 for m in mons)
    assert len(mons) == 1                              # maart 2021 heeft 2 kandidaten (1 en 8 maart), maar max. één per maand
    ep = episode_frame(pd.DataFrame(index=idx, data={"x": 0}), mons[0])
    assert ep.index.min() >= mons[0] - pd.Timedelta(days=28) and ep.index.max() < mons[0] + pd.Timedelta(days=12)


def test_ronde2_geen_overlap_en_geziene_maanden_uitgesloten():
    # handberekend: werkdagen 2020-2024; oneven maanden = 30, min 3 uitgesloten = 27 mogelijke maanden
    idx = pd.date_range("2020-01-01", "2024-12-31 23:59", freq="1min")
    idx = idx[idx.dayofweek < 5]
    excl = ("2022-01", "2022-07", "2024-07")
    mons = pick_mondays(idx, 40, np.random.default_rng(5), exclude_months=excl)
    assert len(mons) == 27                                           # niet meer dan er maanden zijn
    assert len({m.strftime("%Y-%m") for m in mons}) == len(mons)     # één per maand
    assert not {m.strftime("%Y-%m") for m in mons} & set(excl)
    mons = sorted(mons)
    for a, b in zip(mons, mons[1:]):
        # speelvenster van a (12 dagen) ligt volledig vóór de geschiedenis van b (28 dagen): geen enkele overlap
        assert a + pd.Timedelta(days=12) <= b - pd.Timedelta(days=28)
