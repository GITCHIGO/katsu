"""
Handberekende scenario's voor de uitvoering op M1.

Vaste instellingen (Instrument-standaard): tick 0,01 · minimum spread 0,10 ·
slippage 1 tick = 0,01 · commissie 0,08 · TP = 2R · SL-buffer = spread + 0,1×ATR.
De spreadkolom staat op 5 punten (= 0,05), dus het minimum 0,10 geldt.

LONG-basis: signaal 10:00, sweep-low (anchor) 98,00, ATR 1,0
  fill  = open 100,00 + spread 0,10 + slip 0,01 = 100,11
  SL    = 98,00 − (0,10 + 0,1×1,0)            =  97,80
  risk  = 100,11 − 97,80                       =   2,31
  TP    = 100,11 + 2 × 2,31                    = 104,73
  kosten in R = 0,08 / 2,31
"""
import pandas as pd
import pytest

from katsu.execution import M1, Instrument, OrderPlan, run_portfolio, simulate

INS = Instrument()
T0 = pd.Timestamp("2025-01-06 10:00")


def m1(rows, start=T0):
    idx = pd.date_range(start, periods=len(rows), freq="1min")
    o, h, l, c = zip(*rows)
    return M1(pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "spread": 5}, index=idx), INS)


def long_plan(atr=1.0, **kw):
    return OrderPlan("LONG", T0, "market", 98.0, atr, **kw)


def test_long_tp():
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 105.0, 100.0, 104.9)])
    tr = simulate(long_plan(), d, INS)
    assert tr.status == "gesloten"
    assert (tr.fill, tr.sl, tr.tp) == (pytest.approx(100.11), 97.80, 104.73)
    assert tr.exit_reason == "TP" and tr.exit_price == 104.73
    assert tr.r_gross == pytest.approx(2.0)
    assert tr.r_net == pytest.approx(2.0 - 0.08 / 2.31)


def test_long_sl_met_slippage():
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 100.5, 97.5, 98.0)])
    tr = simulate(long_plan(), d, INS)
    assert tr.exit_reason == "SL"
    assert tr.exit_price == pytest.approx(97.79)                 # SL 97,80 − 1 tick
    assert tr.r_gross == pytest.approx((97.79 - 100.11) / 2.31)  # iets slechter dan −1R


def test_sl_en_tp_in_dezelfde_candle_telt_sl():
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 105.0, 97.5, 104.0)])
    assert simulate(long_plan(), d, INS).exit_reason == "SL"


def test_gap_door_sl_vult_op_open():
    d = m1([(100, 100.5, 99.8, 100.2), (97.0, 97.2, 96.9, 97.1)])
    tr = simulate(long_plan(), d, INS)
    assert tr.exit_price == pytest.approx(96.99)                 # open 97,00 − 1 tick, niet 97,79
    assert tr.r_gross < -1.3


def test_short_gebruikt_ask_voor_tp():
    # SHORT: fill = bid 100,00 − slip = 99,99; SL = 102,00 + 0,20 = 102,20; risk 2,21; TP = 95,57
    plan = OrderPlan("SHORT", T0, "market", 102.0, 1.0)
    d = m1([(100, 100.2, 99.5, 99.6),
            (99.6, 99.7, 95.5, 95.6),     # bid-low 95,50 -> ask-low 95,60 > 95,57: NOG GEEN TP
            (95.6, 95.7, 95.4, 95.5)])    # bid-low 95,40 -> ask-low 95,50 <= 95,57: TP
    tr = simulate(plan, d, INS)
    assert (tr.fill, tr.sl, tr.tp) == (pytest.approx(99.99), 102.20, 95.57)
    assert tr.exit_reason == "TP" and tr.exit_time == T0 + pd.Timedelta(minutes=2)
    assert tr.r_gross == pytest.approx(2.0)


def test_einde_dag_sluit_op_laatste_candle_voor_middernacht():
    start = pd.Timestamp("2025-01-06 23:58")
    plan = OrderPlan("LONG", start, "market", 98.0, 1.0)
    d = m1([(100, 100.3, 99.9, 100.1), (100.1, 100.4, 100.0, 100.3), (100.3, 110, 100.2, 109)], start)
    tr = simulate(plan, d, INS)
    # candle van 00:00 (die de TP zou raken) hoort bij de volgende dag en wordt niet gebruikt
    assert tr.exit_reason == "EINDE_DAG"
    assert tr.exit_time == pd.Timestamp("2025-01-06 23:59")
    assert tr.exit_price == pytest.approx(100.29)                # close 100,30 − 1 tick


def test_te_krappe_sl_wordt_overgeslagen():
    d = m1([(100, 100.5, 99.8, 100.2)])
    assert simulate(long_plan(atr=5.0), d, INS).status == "sl_te_klein"   # risk 2,81 < 5


def test_limiet_niet_gevuld():
    plan = OrderPlan("LONG", T0, "limit", 98.0, 1.0, 99.0, T0 + pd.Timedelta(minutes=2))
    d = m1([(100, 100.5, 99.5, 100.2), (100.2, 100.5, 99.0, 99.5), (99.5, 99.6, 98.5, 99.0)])
    # ask-low candle 0 = 99,60, candle 1 = 99,10 (> 99,00); candle 2 valt buiten de geldigheid
    assert simulate(plan, d, INS).status == "niet_gevuld"


def test_limiet_gevuld_op_limietprijs_en_geen_tp_op_vulcandle():
    plan = OrderPlan("LONG", T0, "limit", 98.0, 1.0, 99.5, T0 + pd.Timedelta(minutes=5))
    d = m1([(100, 100.5, 99.8, 100.2),
            (100.2, 110.0, 99.3, 100.0),   # ask-low 99,40 <= 99,50 -> gevuld op 99,50; high 110 telt niet
            (100.0, 100.4, 99.9, 100.1)])
    tr = simulate(plan, d, INS)
    # SL = 97,80 (spread 0,10 + 0,1 ATR) · risk = 99,50 − 97,80 = 1,70 · TP = 102,90
    assert (tr.fill, tr.sl, tr.tp) == (99.5, 97.80, 102.90)
    assert tr.entry_time == T0 + pd.Timedelta(minutes=1)
    assert tr.exit_reason == "EINDE_DAG"


def test_portefeuille_een_positie_en_dagstop():
    # Drie longs op dezelfde dag; elk verliest (SL in de volgende candle).
    rows = []
    for _ in range(3):
        rows += [(100, 100.5, 99.8, 100.2), (100.2, 100.5, 97.5, 98.0)]
    d = m1(rows)
    p = [OrderPlan("LONG", T0 + pd.Timedelta(minutes=m), "market", 98.0, 1.0) for m in (0, 1, 2, 4)]
    out = run_portfolio(p, d, INS)
    # 10:00 gesloten (SL om 10:01) · 10:01 positie nog open · 10:02 gesloten (SL 10:03) ·
    # 10:04: dag al op ≈ −2,1R -> dagstop
    assert list(out.status) == ["gesloten", "positie_open", "gesloten", "dagstop"]


def test_variant_b_niveau_fvg_of_midden():
    from katsu.execution import entry_level_variant_b
    from katsu.signals import Setup
    idx = pd.date_range(T0, periods=4, freq="5min")
    bars = pd.DataFrame({"open": [99, 101, 103, 104], "high": [101, 102, 104, 106],
                         "low": [97, 100, 102.5, 103], "close": [100, 101.5, 103.5, 105.5]}, index=idx)
    s = Setup("LONG", 98, 0, 0, 97.0, 0.5, 3, 103.0, idx[3] + pd.Timedelta("5min"))
    # FVG op candle 1: low van candle 2 (102,5) ligt boven high van candle 0 (101) -> bovenkant 102,5
    assert entry_level_variant_b(s, bars) == 102.5
    bars.loc[idx[2], "low"] = 100.5          # geen gat meer tussen candle 0 en 2
    bars.loc[idx[3], "low"] = 101.5          # ook geen gat tussen candle 1 en 3
    # geen FVG -> midden tussen sweep-low 97 en CHoCH-close 105,5 = 101,25
    assert entry_level_variant_b(s, bars) == 101.25
