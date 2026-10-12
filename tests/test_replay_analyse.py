"""MFE/MAE van replay-trades, met de hand uitgerekend (EURUSD, 1 pip = 0,0001, minimum spread 0,1 pip)."""
import pandas as pd
import pytest

from katsu.replay_analyse import excursion, net_pips


def m1():
    idx = pd.date_range("2021-03-08 10:00", periods=4, freq="1min")
    return pd.DataFrame({"open": [1.1000, 1.1005, 1.1030, 1.1010], "high": [1.1010, 1.1031, 1.1035, 1.1012],
                         "low": [1.0995, 1.1000, 1.1008, 1.0980], "close": [1.1005, 1.1030, 1.1010, 1.0985],
                         "spread": [2, 2, 2, 2]}, index=idx)


def test_long_bijna_tp_daarna_sl():
    # long gevuld op 1,1000 (candle 0), TP 1,1036, SL geraakt op candle 3
    x = excursion(m1(), "EURUSD", 1, 1.1000, 1.1036, 0, 3)
    assert x["mfe_pips"] == pytest.approx(35.0)          # hoogste bid 1,1035
    assert x["mae_pips"] == pytest.approx(20.0)          # laagste bid 1,0980
    assert x["tp_rest_pips"] == pytest.approx(1.0) and x["tp_bereikt"] == pytest.approx(35 / 36)


def test_short_gemeten_op_ask():
    # short gevuld op 1,1030; ask = bid + 0,2 pip. Laagste ask candle 0..3 = 1,0980 + 0,00002
    x = excursion(m1(), "EURUSD", -1, 1.1030, 1.0970, 0, 3)
    assert x["mfe_pips"] == pytest.approx((1.1030 - 1.09802) / 0.0001)
    assert x["mae_pips"] == pytest.approx((1.10352 - 1.1030) / 0.0001)


def test_netto_pips_met_commissie():
    assert net_pips("EURUSD", 1, 1.04287, 1.04013) == pytest.approx(-28.2)
    assert net_pips("XAUUSD", -1, 1900.0, 1895.0) == pytest.approx(49.2)
