"""
Handberekende scenario's voor de ICT-tijdmodellen (katsu/ict.py). Servertijd = New York + 7 uur.
"""
import numpy as np
import pandas as pd
import pytest

from katsu import ict


def bars_at(rows, times):
    idx = pd.to_datetime(times)
    o, h, l, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=idx)


def lv_for(day, **kw):
    base = dict(asia_h=np.nan, asia_l=np.nan, london_h=np.nan, london_l=np.nan, mno=np.nan, adr5=np.nan,
                bias=0, prev_high=np.nan, prev_low=np.nan)
    base.update(kw)
    return pd.DataFrame([base], index=pd.to_datetime([day]))


# ---------- trademeting (ATR = 1, LONG, instap open candle 1 = 100, anker 99 -> SL 98,9, risico 1,1) ----------
A = np.ones(5)


def mt(rows, **kw):
    b = bars_at(rows, pd.date_range("2025-01-07 10:00", periods=len(rows), freq="15min"))
    args = dict(k=[0], d=[1], anchor=[99.0], exit_bar=[len(rows) - 1])
    args.update(kw)
    return ict.measure_trades(b, A, **args).iloc[0]


def test_tp_15r():
    r = mt([(100, 100, 100, 100), (100, 100.5, 99.5, 100.2), (100.2, 101.7, 100, 101.6)], cost=0.11)
    assert r.status == "ok" and r.R == 1.5            # TP = 100 + 1,5 × 1,1 = 101,65
    assert r.R_net == pytest.approx(1.5 - 0.11 / 1.1)


def test_sl_eerst_bij_twijfel():
    r = mt([(100, 100, 100, 100), (100, 100.5, 99.5, 100.2), (100.2, 101.7, 98.8, 100)])
    assert r.R == pytest.approx(-1.0)


def test_tijd_exit_op_close():
    r = mt([(100, 100, 100, 100), (100, 100.5, 99.5, 100.2), (100.2, 100.6, 99.9, 100.55)])
    assert r.R == pytest.approx(0.55 / 1.1)


def test_gap_door_sl():
    r = mt([(100, 100, 100, 100), (100, 100.5, 99.5, 100.2), (98.5, 98.6, 98.2, 98.4)])
    assert r.R == pytest.approx(-1.5 / 1.1)


def test_limiet_geen_tp_op_vulcandle():
    # limiet 99,5 gevuld op candle 1; SL 98,9 -> risico 0,6; TP 100,4; candle 1 high 100,5 telt niet
    r = mt([(100, 100, 100, 100), (100, 100.5, 99.5, 100.2), (100.2, 100.45, 100, 100.3)],
           limit=[99.5], valid_bar=[2])
    assert r.status == "ok" and r.R == 1.5


def test_limiet_niet_gevuld_en_te_krappe_sl():
    r = mt([(100, 100, 100, 100), (100, 100.5, 99.6, 100.2), (100.2, 100.45, 100, 100.3)],
           limit=[99.5], valid_bar=[2])
    assert r.status == "niet_gevuld"
    assert mt([(100, 100, 100, 100), (100, 100.5, 99.9, 100.2)], anchor=[99.8]).status == "sl_te_klein"


# ---------- dagniveaus en bias ----------

def test_dagbias_uit_gisteren():
    # dag 1: high 10 low 5 · dag 2: high 11 (boven 10) maar close 9 (onder 10) -> dag 3 bias SHORT
    t = ["2025-01-06 10:00", "2025-01-07 10:00", "2025-01-07 11:00", "2025-01-08 10:00"]
    b = bars_at([(7, 10, 5, 8), (8, 11, 7.5, 10.5), (10.5, 10.6, 8.5, 9), (9, 9.5, 8.8, 9.2)], t)
    lv = ict.day_levels(b)
    d3 = lv.loc[pd.Timestamp("2025-01-08")]
    assert d3.bias == -1 and d3.prev_high == 11


def test_azie_en_london_range_en_midnight_open():
    t = ["2025-01-07 03:00", "2025-01-07 06:45", "2025-01-07 07:00", "2025-01-07 09:00", "2025-01-07 11:45",
         "2025-01-07 12:00"]
    b = bars_at([(1, 2, 0.5, 1), (1, 1.5, 0.8, 1), (1.1, 1.2, 1, 1.1), (1, 3, 0.9, 2), (2, 2.5, 1.5, 2),
                 (2, 9, 0, 2)], t)
    r = ict.day_levels(b).iloc[0]
    assert (r.asia_h, r.asia_l, r.mno, r.london_h, r.london_l) == (2, 0.5, 1.1, 3, 0.9)   # 12:00 telt niet


# ---------- gebeurtenissen ----------

def test_london_judas():
    t = ["2025-01-07 08:45", "2025-01-07 09:00", "2025-01-07 09:15"]
    b = bars_at([(100.5, 100.6, 100.3, 100.5), (100.4, 100.5, 99.8, 100.2), (100.2, 100.4, 99.7, 100.1)], t)
    ev = ict.judas_events(b, lv_for("2025-01-07", asia_h=101, asia_l=100))
    assert list(zip(ev.k, ev.d, ev.anchor)) == [(1, 1, 99.8)]      # alleen de eerste sweep
    # sluit de eerste candle ONDER de Azië-low, dan is het een run: geen LONG meer die dag
    b2 = bars_at([(100.5, 100.6, 100.3, 100.5), (100.4, 100.5, 99.8, 99.9), (99.9, 100.4, 99.7, 100.1)], t)
    assert len(ict.judas_events(b2, lv_for("2025-01-07", asia_h=101, asia_l=100))) == 0


def test_silver_bullet():
    t = ["2025-01-07 16:30", "2025-01-07 16:45", "2025-01-07 17:00", "2025-01-07 17:15", "2025-01-07 17:45",
         "2025-01-07 18:00"]
    rows = [(100.3, 100.2, 99.8, 100.1),     # sweep van London-low 100 (low 99,8, close 100,1)
            (100.1, 100.3, 100.0, 100.25),
            (100.3, 100.8, 100.4, 100.7),    # FVG: low 100,4 > high 100,2 van 16:30
            (100.7, 100.9, 100.5, 100.8), (100.8, 100.9, 100.6, 100.7), (100.7, 100.8, 100.6, 100.7)]
    rows[0] = (100.1, 100.2, 99.8, 100.1)
    ev = ict.silver_bullet_events(bars_at(rows, t), lv_for("2025-01-07", london_h=102, london_l=100))
    r = ev.iloc[0]
    assert (r.k, r.d, r.anchor, r.limit, r.valid_bar) == (2, 1, 99.8, pytest.approx(100.3), 4)


def test_monday_range():
    t = ["2025-01-06 10:00", "2025-01-06 11:00", "2025-01-07 10:00", "2025-01-07 11:00"]
    b = bars_at([(7, 10, 5, 8), (8, 9, 6, 8.5), (8.5, 10.5, 8, 9.8), (9.8, 10.8, 9.5, 10.2)], t)
    ev = ict.monday_events(b)
    assert list(zip(ev.k, ev.d, ev.anchor)) == [(2, -1, 10.5)]


def test_dagbias_trade_op_midnight_open():
    t = ["2025-01-07 06:45", "2025-01-07 07:00", "2025-01-07 08:00"]
    b = bars_at([(9, 9.2, 8.9, 9), (9, 9.1, 8.7, 8.8), (8.8, 8.9, 8.5, 8.6)], t)
    ev = ict.bias_events(b, lv_for("2025-01-07", bias=-1, prev_high=11, prev_low=7))
    assert list(zip(ev.k, ev.d, ev.anchor)) == [(0, -1, 11)]


def test_london_close_fade():
    t = ["2025-01-07 07:00", "2025-01-07 12:00", "2025-01-07 16:45", "2025-01-07 17:00"]
    b = bars_at([(100, 100.5, 99.8, 100.4), (100.4, 102.5, 100.3, 102.2), (102.2, 102.4, 101.9, 102.1),
                 (102.1, 102.2, 101.8, 101.9)], t)
    ev = ict.london_close_events(b, lv_for("2025-01-07", mno=100, adr5=2.0))
    assert list(zip(ev.k, ev.d, ev.anchor)) == [(2, -1, 102.5)]    # range 2,7 > 2,0, dag omhoog -> SHORT
    assert len(ict.london_close_events(b, lv_for("2025-01-07", mno=100, adr5=3.0))) == 0


def test_basislijn_zelfde_kwartier_en_risico():
    rng = np.random.default_rng(1)
    p = 100 + np.cumsum(rng.normal(0, 0.2, 96 * 20))
    b = pd.DataFrame({"open": p, "high": p + 0.3, "low": p - 0.3, "close": p},
                     index=pd.date_range("2025-01-06", periods=len(p), freq="15min"))
    pool = np.arange(0, len(p) - 100)
    bl = ict.baseline_trades(b, np.ones(len(p)), [40], [1], [1.5], pool, per_event=5)
    assert len(bl) == 5 and bl.R.notna().all()
