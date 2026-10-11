"""
Handberekend scenario voor trendvolgen (Donchian) en structuurtests voor dips kopen (katsu/trend.py).

Donchian N=3, M=2: 25 vlakke dagen (high 100,5 · low 99,5 · close 100), dan dag 25 close 102 (high 102,2):
  ATR20 op dag 25 = (19 × 1,0 + 2,2) / 20 = 1,06  ->  SL-afstand 2 × 1,06 = 2,12
  instap open dag 26 = 102  ->  SL 99,88
  dag 28 sluit op 101,5, onder de laagste low van dag 26–27 (101,8)  ->  uit op de open van dag 29 = 101,6
  R = (101,6 − 102) / 2,12 = −0,1887
"""
import numpy as np
import pandas as pd
import pytest

from katsu import trend


def d1(rows):
    o, h, l, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c},
                        index=pd.date_range("2018-01-01", periods=len(rows), freq="D"))


FLAT = [(100, 100.5, 99.5, 100)] * 25


def test_donchian_handberekend():
    rows = FLAT + [(100, 102.2, 100, 102), (102, 103, 101.8, 102.8), (102.8, 104, 102.5, 103.5),
                   (103.5, 103.6, 101.4, 101.5), (101.6, 101.8, 101.4, 101.6)]
    tr = trend.donchian(d1(rows), N=3, M=2)
    assert len(tr) == 1
    t = tr.iloc[0]
    assert (t.d, t.entry, t.exit, t.reden) == (1, 102, 101.6, "uitstap")
    assert t.risk == pytest.approx(2.12)
    assert t.R == pytest.approx(-0.4 / 2.12)


def test_donchian_sl_en_kosten():
    rows = FLAT + [(100, 102.2, 100, 102), (102, 102.5, 99.5, 100.0), (100, 100.2, 99.9, 100)]
    tr = trend.donchian(d1(rows), N=3, M=2, cost=0.212, swap=lambda p: 0.0)
    t = tr.iloc[0]
    assert t.reden == "SL" and t.exit == pytest.approx(99.88) and t.R == pytest.approx(-1.0)
    assert t.R_net == pytest.approx(-1.1)                # kosten 0,212 / 2,12 = 0,1R


def test_rsi2_daalt_na_twee_rode_dagen():
    c = pd.Series([100 + i for i in range(10)] + [105, 101])
    r = trend.rsi(c, 2)
    assert r[9] > 90 and r[11] < 10


def _dips_rows(after):
    up = [(100 + 0.1 * i, 100.2 + 0.1 * i, 99.9 + 0.1 * i, 100.1 + 0.1 * i) for i in range(210)]
    last = up[-1][3]
    drops = [(last, last + 0.1, last - 2.0, last - 1.9), (last - 1.9, last - 1.8, last - 4.0, last - 3.9)]
    return up + drops + after


def test_dips_uitstap_boven_sma5():
    # Al na de 1e rode dag is RSI(2) = 5: instap open 119,1; ATR14 = 0,4286 -> nood-SL 3 × = 1,2857 (117,81).
    # De 2e rode dag zakt tot 117,0 -> SL (−1R). RSI(2) blijft < 10 -> nieuwe instap open 117,0;
    # close 120,9 > SMA5 -> uit op de open van de volgende dag (121,0).
    rows = _dips_rows([(117, 117.2, 116.9, 117.1), (117.1, 121, 117, 120.9), (121, 121.5, 120.5, 121)])
    tr = trend.dips(d1(rows), threshold=10)
    assert list(tr.reden) == ["SL", "uitstap"]
    assert tr.iloc[0].entry == 119.1 and tr.iloc[0].R == pytest.approx(-1.0)
    assert (tr.iloc[1].entry, tr.iloc[1].exit) == (117, 121)


def test_dips_tijdsuitstap_na_10_dagen():
    flat = [(117, 117.3, 116.8, 117)] * 14
    tr = trend.dips(d1(_dips_rows(flat)), threshold=10)
    assert tr.iloc[1].reden == "tijd"
    assert (tr.iloc[1].exit_time - tr.iloc[1].entry_time).days == 10
    assert list(tr.reden).count("einde_data") <= 1 and tr.iloc[-1].reden in ("einde_data", "tijd", "SL", "uitstap")
