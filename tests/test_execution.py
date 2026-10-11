"""
Handberekende scenario's voor de uitvoering op M1.

Vaste instellingen (Instrument-standaard): tick 0,01 · minimum spread 0,10 ·
slippage 1 tick = 0,01 · commissie 0,08 · TP = 2R · SL-buffer = spread + 0,1×ATR.
De tests gebruiken slippage 0,01 (de echte basis is $0,25, zie spec).
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

INS = Instrument(slip=0.01)   # 1 tick: houdt de handberekening eenvoudig
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


def test_oude_regel_einde_dag_sluit_op_laatste_candle_voor_middernacht():
    # Oud gedrag (spec v0.1/v0.2 vóór 9 okt 2026), alleen nog beschikbaar met close_eod=True.
    from dataclasses import replace
    eod = replace(INS, close_eod=True)
    start = pd.Timestamp("2025-01-06 23:58")
    plan = OrderPlan("LONG", start, "market", 98.0, 1.0)
    d = m1([(100, 100.3, 99.9, 100.1), (100.1, 100.4, 100.0, 100.3), (100.3, 110, 100.2, 109)], start)
    tr = simulate(plan, d, eod)
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
    assert tr.exit_reason == "EINDE_DATA"          # geen SL/TP geraakt vóór het einde van de data


def test_portefeuille_een_positie_en_dagstop():
    # Drie longs op dezelfde dag; elk verliest (SL in de volgende candle).
    rows = []
    for _ in range(3):
        rows += [(100, 100.5, 99.8, 100.2), (100.2, 100.5, 97.5, 98.0)]
    d = m1(rows)
    p = [OrderPlan("LONG", T0 + pd.Timedelta(minutes=m), "market", 98.0, 1.0) for m in (0, 1, 2, 4)]
    out = run_portfolio(p, {"XAUUSD": d}, {"XAUUSD": INS})
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


def test_portefeuille_per_markt_en_gezamenlijke_dagstop():
    rows = []
    for _ in range(3):
        rows += [(100, 100.5, 99.8, 100.2), (100.2, 100.5, 97.5, 98.0)]
    g, e = m1(rows), m1(rows)
    ins = {"XAUUSD": INS, "EURUSD": INS}
    p = [OrderPlan("LONG", T0, "market", 98.0, 1.0, market="XAUUSD"),
         OrderPlan("LONG", T0, "market", 98.0, 1.0, market="EURUSD"),    # zelfde moment, andere markt: mag
         OrderPlan("LONG", T0 + pd.Timedelta(minutes=2), "market", 98.0, 1.0, market="XAUUSD")]
    out = run_portfolio(p, {"XAUUSD": g, "EURUSD": e}, ins)
    # twee verliezers samen ≈ −2,1R -> derde setup (andere markt of niet) valt onder de dagstop
    assert list(zip(out.market, out.status)) == [("EURUSD", "gesloten"), ("XAUUSD", "gesloten"),
                                                  ("XAUUSD", "dagstop")]


def test_vastgelegde_instellingen_per_markt():
    from katsu.execution import EURUSD, XAUUSD
    assert (XAUUSD.slip, XAUUSD.min_spread, XAUUSD.commission) == (0.25, 0.10, 0.08)
    assert (EURUSD.slip, EURUSD.min_spread) == (0.00003, 0.00001)


# ---------------- Kostenplafond (spec v0.2 §4) ----------------
# Verwachte kosten = spread 0,10 + 2 × slippage 0,01 + commissie 0,08 = 0,20 (in prijs).

def test_kostenplafond_marktorder():
    # geplande entry 100,11 · SL 97,80 · R = 2,31 · kosten 0,20 / 2,31 = 0,087R
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 105.0, 100.0, 104.9)])
    assert simulate(long_plan(max_cost_r=0.2), d, INS).status == "gesloten"
    tr = simulate(long_plan(max_cost_r=0.05), d, INS)
    assert tr.status == "kosten_te_hoog"
    assert tr.cost_r == pytest.approx(0.20 / 2.31)


def test_kostenplafond_limiet_gebruikt_de_limietprijs():
    # limiet 99,50 · SL 97,80 · R = 1,70 · kosten 0,20 / 1,70 = 0,118R
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 110.0, 99.3, 100.0), (100.0, 100.4, 99.9, 100.1)])
    p = dict(kind="limit", limit_price=99.5, valid_until=T0 + pd.Timedelta(minutes=5))
    ok = OrderPlan("LONG", T0, p["kind"], 98.0, 1.0, p["limit_price"], p["valid_until"], max_cost_r=0.2)
    te = OrderPlan("LONG", T0, p["kind"], 98.0, 1.0, p["limit_price"], p["valid_until"], max_cost_r=0.1)
    assert simulate(ok, d, INS).status == "gesloten"
    tr = simulate(te, d, INS)
    assert tr.status == "kosten_te_hoog" and tr.cost_r == pytest.approx(0.20 / 1.70)


def test_overgeslagen_wegens_kosten_blokkeert_de_markt_niet():
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 105.0, 100.0, 104.9)])
    p = [long_plan(max_cost_r=0.01), OrderPlan("LONG", T0, "market", 98.0, 1.0)]
    out = run_portfolio(p, {"XAUUSD": d}, {"XAUUSD": INS})
    assert sorted(out.status) == ["gesloten", "kosten_te_hoog"]


# ---------------- Looptijd tot SL/TP, swap, rollover (gewijzigd 9 okt 2026) ----------------

def test_trade_loopt_over_middernacht_tot_tp_met_swap():
    """
    LONG zoals de basis (fill 100,11 · SL 97,80 · risk 2,31 · TP 104,73), maar de TP valt pas
    de volgende dag. Swap 0,05 per nacht, 1 nacht:
      r_net = 2 − (0,08 + 0,05) / 2,31
    """
    from dataclasses import replace
    ins = replace(INS, swap=0.05)
    start = pd.Timestamp("2025-01-06 23:58")
    plan = OrderPlan("LONG", start, "market", 98.0, 1.0)
    d = M1(pd.DataFrame({"open": [100, 100.1, 100.3], "high": [100.3, 100.4, 105.0],
                         "low": [99.9, 100.0, 100.2], "close": [100.1, 100.3, 104.9], "spread": 5},
                        index=pd.to_datetime(["2025-01-06 23:58", "2025-01-06 23:59", "2025-01-07 01:00"])),
           ins)
    tr = simulate(plan, d, ins)
    assert tr.exit_reason == "TP" and tr.exit_time == pd.Timestamp("2025-01-07 01:00")
    assert tr.nights == 1
    assert tr.swap_r == pytest.approx(0.05 / 2.31)
    assert tr.r_net == pytest.approx(2.0 - (0.08 + 0.05) / 2.31)


def test_weekend_telt_als_drie_nachten_en_gap_vult_op_open():
    from dataclasses import replace
    ins = replace(INS, swap=0.05)
    fri = pd.Timestamp("2025-01-10 22:00")                       # vrijdag
    idx = pd.to_datetime(["2025-01-10 22:00", "2025-01-10 22:01", "2025-01-13 01:00"])   # maandag
    d = M1(pd.DataFrame({"open": [100, 100.1, 97.0], "high": [100.3, 100.4, 97.2],
                         "low": [99.9, 100.0, 96.9], "close": [100.1, 100.3, 97.1], "spread": 5},
                        index=idx), ins)
    tr = simulate(OrderPlan("LONG", fri, "market", 98.0, 1.0), d, ins)
    assert tr.nights == 3
    assert tr.exit_reason == "SL" and tr.exit_price == pytest.approx(96.99)   # gap: open 97,00 − 1 tick


def test_lange_trade_over_meerdere_zoekstappen():
    # Meer dan CHUNK candles vlak, daarna pas de TP: de zoektocht in stukken mag niets missen.
    from katsu.execution import CHUNK
    n = CHUNK + 500
    rows = [(100, 100.5, 99.8, 100.2)] + [(100.2, 100.3, 100.1, 100.2)] * n + [(100.2, 105.0, 100.1, 104.9)]
    tr = simulate(long_plan(), m1(rows), INS)
    assert tr.exit_reason == "TP" and tr.exit_time == T0 + pd.Timedelta(minutes=n + 1)


def test_rollover_verbreedt_de_spread():
    from dataclasses import replace
    ins = replace(INS, rollover_min_spread=0.50)
    idx = pd.to_datetime(["2025-01-06 10:00", "2025-01-06 23:56", "2025-01-07 00:30", "2025-01-07 01:30"])
    d = M1(pd.DataFrame({"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0,
                         "spread": [5, 5, 30, 5]}, index=idx), ins)
    # 10:00 normaal 0,10 · 23:56 max(2×0,10; 0,50) = 0,50 · 00:30 max(2×0,30; 0,50) = 0,60 · 01:30 weer normaal
    assert list(d.sp) == pytest.approx([0.10, 0.50, 0.60, 0.10])


def test_dagstop_telt_alleen_gesloten_trades():
    """
    Goud verliest om 10:01 (SL). EURUSD-signaal om 10:00:30 komt VÓÓR die exit: mag nog.
    EURUSD-signaal om 10:05 komt erna: dag staat op ≈ −1R, onder de dagstop van −0,5R -> geblokkeerd.
    """
    rows = [(100, 100.5, 99.8, 100.2), (100.2, 100.5, 97.5, 98.0)] + [(100, 100.2, 99.9, 100)] * 10
    g, e = m1(rows), m1(rows)
    p = [OrderPlan("LONG", T0, "market", 98.0, 1.0, market="XAUUSD"),
         OrderPlan("LONG", T0 + pd.Timedelta(seconds=30), "market", 90.0, 1.0, market="EURUSD"),
         OrderPlan("LONG", T0 + pd.Timedelta(minutes=5), "market", 90.0, 1.0, market="XAUUSD")]
    out = run_portfolio(p, {"XAUUSD": g, "EURUSD": e}, {"XAUUSD": INS, "EURUSD": INS}, day_stop_r=-0.5)
    assert list(zip(out.market, out.status)) == [("XAUUSD", "gesloten"), ("EURUSD", "gesloten"),
                                                  ("XAUUSD", "dagstop")]


def test_kostenplafond_signaal_na_laatste_candle():
    from katsu.execution import planned_cost_r
    d = m1([(100, 100.5, 99.8, 100.2)])
    late = OrderPlan("LONG", T0 + pd.Timedelta(minutes=5), "market", 98.0, 1.0, max_cost_r=0.2)
    assert planned_cost_r(late, d, INS) == (None, None)
    assert simulate(late, d, INS).status == "geen_data"


def test_swap_apart_voor_long_en_short():
    """EURUSD-instelling: long betaalt swap, short niet (opbrengst wordt niet meegeteld)."""
    from dataclasses import replace
    ins = replace(INS, swap=0.05, swap_short=0.0)
    idx = pd.to_datetime(["2025-01-06 23:58", "2025-01-06 23:59", "2025-01-07 01:00"])
    # SHORT: fill 99,99 · SL 102,20 · risk 2,21 · TP 95,57; TP de volgende dag
    d = M1(pd.DataFrame({"open": [100, 99.6, 95.6], "high": [100.2, 99.7, 95.7],
                         "low": [99.5, 99.5, 95.4], "close": [99.6, 99.6, 95.5], "spread": 5}, index=idx), ins)
    tr = simulate(OrderPlan("SHORT", idx[0], "market", 102.0, 1.0), d, ins)
    assert tr.nights == 1 and tr.swap_r == 0.0
    assert tr.r_net == pytest.approx(2.0 - 0.08 / 2.21)


def test_eurusd_swap_preset():
    from katsu.execution import EURUSD
    assert (EURUSD.swap, EURUSD.swap_short) == (0.00008, 0.0)


# ---------------- Maximale looptijd en meegroeiende swap (11 okt 2026) ----------------

def test_maximale_looptijd_sluit_op_de_close():
    from dataclasses import replace
    ins = replace(INS, max_hold_days=1)
    # LONG zoals de basis; 3 dagen vlak, geen SL/TP -> sluiten op de laatste candle vóór 24 uur na de vulling
    idx = pd.date_range("2025-01-06 10:00", periods=3 * 24, freq="1h")
    d = M1(pd.DataFrame({"open": 100.0, "high": 100.3, "low": 99.9, "close": 100.2, "spread": 5}, index=idx), ins)
    tr = simulate(OrderPlan("LONG", idx[0], "market", 98.0, 1.0), d, ins)
    assert tr.exit_reason == "MAX_DUUR"
    assert tr.exit_time == pd.Timestamp("2025-01-07 09:00")      # laatste candle vóór 10:00 de dag erna
    assert tr.exit_price == pytest.approx(100.19)                 # close 100,20 − slippage


def test_swap_als_procent_van_de_prijs():
    from dataclasses import replace
    ins = replace(INS, swap_pct_long=0.0365, swap_pct_short=0.0)  # 3,65%/jaar = 0,01% per nacht
    start = pd.Timestamp("2025-01-06 23:58")
    d = M1(pd.DataFrame({"open": [100, 100.1, 100.3], "high": [100.3, 100.4, 105.0],
                         "low": [99.9, 100.0, 100.2], "close": [100.1, 100.3, 104.9], "spread": 5},
                        index=pd.to_datetime(["2025-01-06 23:58", "2025-01-06 23:59", "2025-01-07 01:00"])), ins)
    tr = simulate(OrderPlan("LONG", start, "market", 98.0, 1.0), d, ins)
    # 1 nacht × 100,11 × 0,0001 = 0,010011 in prijs; risico 2,31
    assert tr.swap_r == pytest.approx(100.11 * 0.0001 / 2.31)


def test_sell_stop_vult_op_stopprijs_min_slippage():
    # SHORT sell-stop op 99,50: candle 1 bid-low 99,40 <= 99,50 -> gevuld op 99,50 − 0,01 = 99,49
    # SL = anker 101 + (0,10 + 0,1) = 101,20 · risico 1,71 · TP = 99,49 − 1,5 × 1,71 = 96,925 -> 96,93 (afronding tick)
    from dataclasses import replace
    ins = replace(INS, rr=1.5)
    plan = OrderPlan("SHORT", T0, "stop", 101.0, 1.0, 99.5, T0 + pd.Timedelta(minutes=5))
    d = m1([(100, 100.2, 99.8, 100.0), (100.0, 100.1, 99.4, 99.6), (99.6, 99.7, 96.5, 96.8)])
    tr = simulate(plan, d, ins)
    assert tr.fill == pytest.approx(99.49) and tr.sl == pytest.approx(101.20)
    assert tr.exit_reason == "TP" and tr.entry_time == T0 + pd.Timedelta(minutes=1)


def test_buy_stop_gap_vult_op_open():
    plan = OrderPlan("LONG", T0, "stop", 98.0, 1.0, 100.5, T0 + pd.Timedelta(minutes=5))
    d = m1([(100, 100.3, 99.8, 100.1), (101.0, 101.2, 100.9, 101.1)])   # opent boven de stop
    tr = simulate(plan, d, INS)
    assert tr.fill == pytest.approx(101.0 + 0.10 + 0.01)               # ask-open + slippage


def test_stop_niet_geraakt():
    plan = OrderPlan("LONG", T0, "stop", 98.0, 1.0, 101.0, T0 + pd.Timedelta(minutes=2))
    d = m1([(100, 100.3, 99.8, 100.1), (100.1, 100.5, 100.0, 100.4), (100.4, 102, 100.3, 101.8)])
    assert simulate(plan, d, INS).status == "niet_gevuld"               # candle 2 valt buiten de geldigheid
