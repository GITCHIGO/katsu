"""
KATSU Live (docs/live_spec.md): orderniveaus = backtest, scan, orderbeheer met een nep-MT5.
Alle verwachte getallen zijn met de hand uitgerekend (zie de commentaarregels).
"""
import os
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from katsu.execution import M1, OrderPlan, simulate
from katsu.live.broker import ClosedInfo, server_now, server_to_be
from katsu.live.fake import FakeBroker
from katsu.live.levels import sl_price, tp_price, zone_tp_plan
from katsu.live.orders import Manager
from katsu.live.scan import Signal, closed_bars, signal_from_row
from scripts.dashboard_build import INS

EUR = INS["EURUSD"]
LOTS = {"EURUSD": 0.10, "GBPUSD": 0.10, "XAUUSD": 0.02}
T0 = pd.Timestamp("2026-10-21 10:15")


# ------------------------------------------------------------------ niveaus = backtest

def test_sl_tp_hand():
    # long, anchor 1.10000, ATR 0.00100: SL = 1.10000 − (min. spread 0.00001 + 0,1 × 0.00100) = 1.09989
    sl = sl_price("LONG", 1.10000, 0.00100, EUR)
    assert sl == pytest.approx(1.09989)
    # limiet 1.10100 → risk 0.00111; oude high 1.10500 ligt verder dan 2R (1.10322) → TP 1.10322
    assert tp_price("LONG", 1.10100, sl, EUR, 1.10500, 2.0) == pytest.approx(1.10322)
    # oude high dichterbij (1.10200) → TP = oude high
    assert tp_price("LONG", 1.10100, sl, EUR, 1.10200, 2.0) == pytest.approx(1.10200)
    # short gespiegeld: anchor 1.20000 → SL 1.20011; limiet 1.19900, risk 0.00111, 2R = 1.19678
    sl = sl_price("SHORT", 1.20000, 0.00100, EUR)
    assert sl == pytest.approx(1.20011)
    assert tp_price("SHORT", 1.19900, sl, EUR, 1.19000, 2.0) == pytest.approx(1.19678)
    # TP niet voorbij de entry → ongeldig (backtest: tp_ongeldig)
    assert tp_price("LONG", 1.10100, 1.09989, EUR, 1.10050, 2.0) is None


def test_levels_equal_simulate():
    """Zelfde SL/TP als simulate() bij een vulling op de limiet (spread in de data = 0 → minimumspread)."""
    rng = np.random.default_rng(3)
    idx = pd.date_range("2026-10-20 02:00", periods=40, freq="15min")
    for _ in range(50):
        long = rng.random() < 0.5
        s = 1 if long else -1
        a = float(rng.uniform(0.0005, 0.002))
        limit = 1.1 + rng.uniform(-0.001, 0.001)
        anchor = limit - s * rng.uniform(0.5, 2) * a
        tpp = limit + s * rng.uniform(0.3, 4) * a
        # candles: eerst boven de limiet (long), dan één candle die de limiet raakt, dan rustig
        o = np.full(len(idx), limit + s * 3 * a)
        lo, hi = o - 0.0002, o + 0.0002
        lo[5], hi[5] = (limit - 0.00001, limit + s * 3 * a) if long else (limit - s * 3 * a, limit + 0.00001)
        bars = pd.DataFrame({"open": o, "high": np.maximum(hi, lo), "low": np.minimum(hi, lo), "close": o,
                             "spread": 0}, index=idx)
        ins = replace(EUR, min_sl_atr=0.0)
        p = OrderPlan("LONG" if long else "SHORT", idx[1], "limit", anchor, a, limit, idx[-1], market="EURUSD",
                      tp_price=tpp, max_rr=2.0)
        tr = simulate(p, M1(bars, ins), ins)
        if tr.status not in ("gesloten", "tp_ongeldig"):
            continue
        sl = sl_price(p.direction, anchor, a, ins)
        assert sl == pytest.approx(tr.sl, abs=1e-9)
        tp = tp_price(p.direction, tr.fill, sl, ins, tpp, 2.0)
        if tr.status == "tp_ongeldig":
            assert tp is None
        else:
            assert tp == pytest.approx(tr.tp, abs=1e-9)


def test_zone_tp_at_fill():
    # long: vertrekbeen-high 1.2050; candles na de zone tot vóór de vulling met highs 1.2040, 1.2063 → TP 1.2063
    assert zone_tp_plan("LONG", 1.2050, [1.2040, 1.2063], [1.20, 1.20]) == pytest.approx(1.2063)
    # geen candles ertussen → vertrekbeen
    assert zone_tp_plan("LONG", 1.2050, [], []) == pytest.approx(1.2050)
    # short: laagste low
    assert zone_tp_plan("SHORT", 1.3000, [1.31, 1.31], [1.2990, 1.3010]) == pytest.approx(1.2990)


# ------------------------------------------------------------------ tijd

def test_server_time_and_belgian_time():
    from datetime import datetime, timezone
    # 21 okt 2026 08:00 UTC: New York = 04:00 (EDT, UTC−4) → server 11:00; België = 10:00 (CEST)
    assert server_now(datetime(2026, 10, 21, 8, 0, tzinfo=timezone.utc)) == pd.Timestamp("2026-10-21 11:00")
    assert server_to_be(pd.Timestamp("2026-10-21 11:00")) == pd.Timestamp("2026-10-21 10:00")
    # 28 okt 2026: Europa al wintertijd, VS nog zomertijd → België = server − 2 u
    assert server_to_be(pd.Timestamp("2026-10-28 11:00")) == pd.Timestamp("2026-10-28 09:00")


# ------------------------------------------------------------------ scan

def test_closed_bars_drops_running_candle():
    idx = pd.date_range("2026-10-21 10:00", periods=3, freq="15min")       # 10:00, 10:15, 10:30
    b = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "spread": 0}, index=idx)
    # om 10:30:10 is de 10:30-candle nog bezig
    assert list(closed_bars(b, pd.Timestamp("2026-10-21 10:30:10")).index) == list(idx[:2])
    # om 10:45:00 is ze net gesloten
    assert len(closed_bars(b, pd.Timestamp("2026-10-21 10:45:00"))) == 3


def _row(**kw):
    r = {"markt": "EURUSD", "soort": "FVG", "t_sig": T0, "plan_kind": "limit", "plan_richting": "LONG",
         "plan_anchor": 1.1, "plan_atr": 0.001, "plan_limit": 1.101, "plan_valid_until": T0, "plan_valid_bars": 480,
         "plan_tp": 1.105, "plan_cancel": 1.103, "plan_max_rr": 2.0, "plan_close_eod": np.nan, "status": "geen_data"}
    r.update(kw)
    return pd.Series(r)


def test_signal_from_row_kinds():
    s = signal_from_row(_row(), "Test #1 (FVG)")
    assert (s.valid_bars, s.valid_until, s.close_eod, s.tp_mode) == (480, None, False, "vast")
    a = signal_from_row(_row(soort="AMD", plan_kind="market", plan_limit=None, plan_valid_until=None,
                             plan_valid_bars=None, plan_cancel=None, plan_max_rr=None, plan_close_eod=True),
                        "AMD-extra (#386)")
    assert (a.kind, a.limit, a.close_eod, a.valid_bars) == ("market", None, True, None)
    z = signal_from_row(_row(markt="GBPUSD", soort="Zone", plan_valid_bars=None,
                             plan_valid_until=T0 + pd.Timedelta(days=7), plan_tp=1.101 + 1e6, plan_cancel=None,
                             plan_tp_mode="zone_bij_vulling", plan_leg_high=1.104), "Zone GBPUSD")
    assert (z.tp_mode, z.tp_plan, z.leg_high, z.valid_until) == ("zone_bij_vulling", None, 1.104,
                                                                  T0 + pd.Timedelta(days=7))
    assert s.key != signal_from_row(_row(plan_limit=1.1011), "Test #1 (FVG)").key


DATA = "/home/claude/katsu_research/htf"


@pytest.mark.skipif(not os.path.isdir(DATA), reason="geen koersdata op deze machine")
def test_live_scan_equals_backtest_on_history():
    """Werkregel 3: de live-scan (alleen data tot T) vindt exact dezelfde setups als de backtest op alle data."""
    from katsu.live.scan import scan
    from scripts.eindtest_gfvg import load_full
    from scripts.vooruittest import needed_kinds
    bars = {m: load_full(DATA, m) for m in needed_kinds()}
    since, until = pd.Timestamp("2026-09-07"), pd.Timestamp("2026-09-12")
    full, _, win_full = scan(bars, since, until)                        # 'backtest': alle data
    keys_full = {s.key for s in full} | {s.key for s in _}
    found = set()
    for T in sorted({s.t_sig for s in full} | {s.t_sig for s in _})[:6]:
        live = {m: closed_bars(b[b.index >= T - pd.DateOffset(months=24)], T + pd.Timedelta(seconds=10))
                for m, b in bars.items()}
        sig, missed, _w = scan(live, T - pd.Timedelta("15min"), T)
        found |= {s.key for s in sig}
        assert {s.key for s in sig} <= keys_full                           # niets extra
        assert not missed                                                   # op het moment zelf nooit 'gemist'
    assert found                                                            # en ze worden echt gevonden


# ------------------------------------------------------------------ orderbeheer met nep-MT5

def sig(**kw):
    d = dict(key="k1", setup="Test #1 (FVG)", market="EURUSD", direction="LONG", t_sig=T0, kind="limit",
             anchor=1.10000, atr=0.00100, limit=1.10100, tp_plan=1.10500, cancel=1.10322, max_rr=2.0,
             valid_until=None, valid_bars=480, close_eod=False, tp_mode="vast", leg_high=None)
    d.update(kw)
    return Signal(**d)


def mgr(tmp_path=None, mode="orders", fb=None):
    fb = fb or FakeBroker()
    fb.set_price("EURUSD", 1.10200, 1.10201, T0)
    fb.set_price("GBPUSD", 1.30200, 1.30203, T0)
    store = str(tmp_path / "state.json") if tmp_path else None
    return Manager(fb, INS, LOTS, store, mode), fb


def test_loggen_sends_nothing():
    m, fb = mgr(mode="loggen")
    o = m.add_signal(sig(), T0)
    assert o.state == "log" and fb.calls == []
    assert m.add_signal(sig(), T0) is None                     # zelfde signaal bij de volgende scan: niet dubbel


def test_limit_fill_and_tp_full_cycle():
    m, fb = mgr()
    o = m.add_signal(sig(), T0)
    # limiet 1.10100, SL 1.09989, TP min(1.10500, 2R=1.10322) = 1.10322, 0,10 lot
    assert fb.calls[0] == ("pending", "EURUSD", "LONG", 1.101, 1.09989, 1.10322, 0.1, 710101)
    assert o.state == "geplaatst"
    fb.set_price("EURUSD", 1.10099, 1.10100, T0 + pd.Timedelta(minutes=30))      # ASK raakt de limiet
    m.step(T0 + pd.Timedelta(minutes=30))
    assert o.state == "gevuld" and o.fill_px == pytest.approx(1.10100)
    assert o.risk_px == pytest.approx(0.00111)
    fb.set_price("EURUSD", 1.10322, 1.10323, T0 + pd.Timedelta(hours=3))          # TP
    m.step(T0 + pd.Timedelta(hours=3))
    assert o.state == "gesloten" and o.exit_reason == "TP"
    # winst 0.00222 × 100 000 × 0,1 = 22,20; commissie 7 × 0,1 = 0,70 → netto 21,50
    # risico in geld 0.00111 × 10 000 = 11,10 → R = 21,50 / 11,10 = 1,937
    assert o.net == pytest.approx(21.50)
    assert o.r_net == pytest.approx(21.50 / 11.10)
    assert o.pips == pytest.approx(22.2)
    kinds = [e.kind for e in m.drain()]
    assert kinds == ["geplaatst", "gevuld", "gesloten"]


def test_cancel_when_tp_level_first_by_tick_and_by_candle():
    m, fb = mgr()
    o = m.add_signal(sig(), T0)
    fb.set_price("EURUSD", 1.10330, 1.10331, T0 + pd.Timedelta(minutes=5))       # BID >= annuleerniveau 1.10322
    m.step(T0 + pd.Timedelta(minutes=5))
    assert o.state == "geannuleerd" and ("cancel", o.ticket) in fb.calls
    # zelfde via een candle-high (piek tussen twee ticks)
    m2, fb2 = mgr()
    o2 = m2.add_signal(sig(key="k2"), T0)
    bars = pd.DataFrame({"open": [1.1020], "high": [1.1033], "low": [1.1015], "close": [1.1020], "spread": [0]},
                        index=[T0])
    m2.on_bars({"EURUSD": bars}, T0 + pd.Timedelta(minutes=15, seconds=10))
    assert o2.state == "geannuleerd" and "TP-niveau" in o2.reason


def test_expiry_in_candles_and_in_time():
    m, fb = mgr()
    o = m.add_signal(sig(valid_bars=3), T0)
    idx = pd.date_range(T0, periods=2, freq="15min")
    bars = pd.DataFrame({"open": 1.1020, "high": 1.1025, "low": 1.1015, "close": 1.1020, "spread": 0}, index=idx)
    m.on_bars({"EURUSD": bars}, T0 + pd.Timedelta(minutes=30, seconds=10))
    assert o.state == "geplaatst"                                       # pas 2 van de 3 candles voorbij
    idx = pd.date_range(T0, periods=3, freq="15min")
    bars = pd.DataFrame({"open": 1.1020, "high": 1.1025, "low": 1.1015, "close": 1.1020, "spread": 0}, index=idx)
    m.on_bars({"EURUSD": bars}, T0 + pd.Timedelta(minutes=45, seconds=10))
    assert o.state == "geannuleerd" and "verlopen" in o.reason
    # tijdsgrens (AMD/zone)
    m2, fb2 = mgr()
    o2 = m2.add_signal(sig(key="k3", valid_bars=None, valid_until=T0 + pd.Timedelta(hours=2)), T0)
    m2.step(T0 + pd.Timedelta(hours=1))
    assert o2.state == "geplaatst"
    m2.step(T0 + pd.Timedelta(hours=2))
    assert o2.state == "geannuleerd"


def test_one_trade_at_a_time_parks_and_rearms():
    m, fb = mgr()
    a = m.add_signal(sig(key="a"), T0)
    b = m.add_signal(sig(key="b", t_sig=T0 + pd.Timedelta("15min"), limit=1.10050, cancel=None), T0)
    assert a.state == b.state == "geplaatst"
    fb.set_price("EURUSD", 1.10099, 1.10100, T0 + pd.Timedelta(minutes=20))      # a vult, b (1.10050) nog niet
    m.step(T0 + pd.Timedelta(minutes=20))
    assert a.state == "gevuld" and b.state == "wacht" and b.ticket is None       # b van de broker gehaald
    fb.set_price("EURUSD", 1.10322, 1.10323, T0 + pd.Timedelta(minutes=40))      # a raakt TP; b (1.10050) niet
    m.step(T0 + pd.Timedelta(minutes=40))
    assert a.state == "gesloten" and a.exit_reason == "TP"
    assert b.state == "geplaatst" and b.ticket is not None                        # terug naar de broker
    assert [c[0] for c in fb.calls].count("pending") == 3                         # a, b, en b opnieuw


def test_parked_order_passed_during_other_trade_is_blocked_on_rearm():
    m, fb = mgr()
    a = m.add_signal(sig(key="a"), T0)
    b = m.add_signal(sig(key="b", t_sig=T0 + pd.Timedelta("15min"), limit=1.10050, cancel=None), T0)
    fb.set_price("EURUSD", 1.10099, 1.10100, T0 + pd.Timedelta(minutes=20))
    m.step(T0 + pd.Timedelta(minutes=20))
    # koers zakt in één sprong door b's limiet (1.10050) tot a's SL (1.09989): b werd geraakt terwijl a liep
    fb.set_price("EURUSD", 1.09980, 1.09981, T0 + pd.Timedelta(minutes=40))
    m.step(T0 + pd.Timedelta(minutes=40))
    assert a.state == "gesloten" and a.exit_reason == "SL"
    assert b.state == "geblokkeerd"


def test_parked_order_blocked_if_limit_touched_while_other_trade_runs():
    m, fb = mgr()
    a = m.add_signal(sig(key="a"), T0)
    fb.set_price("EURUSD", 1.10099, 1.10100, T0 + pd.Timedelta(minutes=20))
    m.step(T0 + pd.Timedelta(minutes=20))
    b = m.add_signal(sig(key="b", t_sig=T0 + pd.Timedelta("30min"), limit=1.10060, cancel=None, anchor=1.0995), T0)
    assert b.state == "wacht"
    fb.set_price("EURUSD", 1.10059, 1.10060, T0 + pd.Timedelta(minutes=50))      # a loopt nog (SL 1.09989)
    m.step(T0 + pd.Timedelta(minutes=50))
    assert a.state == "gevuld" and b.state == "geblokkeerd"
    assert not any(c[0] == "pending" and c[3] == 1.1006 for c in fb.calls)


def test_market_order_amd_and_blocked_when_busy():
    m, fb = mgr()
    s = sig(key="m1", setup="AMD-extra (#386)", kind="market", limit=None, tp_plan=1.10500, cancel=None,
            max_rr=None, valid_bars=None, close_eod=True, direction="LONG", anchor=1.10100)
    o = m.add_signal(s, T0)
    # ASK 1.10201 → SL 1.10100 − 0.00011 = 1.10089; TP = Azië-overkant 1.10500 (geen plafond)
    assert fb.calls[0] == ("market", "EURUSD", "LONG", 1.10089, 1.105, 0.1, 710102)
    assert o.state == "gevuld" and o.fill_px == pytest.approx(1.10201)
    o2 = m.add_signal(sig(key="m2", setup="AMD-extra (#386)", kind="market", limit=None, cancel=None,
                          valid_bars=None, close_eod=True), T0)
    assert o2.state == "geblokkeerd"


def test_amd_closes_at_end_of_day():
    m, fb = mgr()
    o = m.add_signal(sig(key="m1", setup="AMD-extra (#386)", kind="market", limit=None, tp_plan=1.10500,
                         cancel=None, max_rr=None, valid_bars=None, close_eod=True, anchor=1.10100), T0)
    m.step(pd.Timestamp("2026-10-21 23:54"))
    assert o.state == "gevuld"
    fb.set_price("EURUSD", 1.10300, 1.10301, pd.Timestamp("2026-10-21 23:55"))
    m.step(pd.Timestamp("2026-10-21 23:55"))                           # sluit
    m.step(pd.Timestamp("2026-10-21 23:55:10"))                        # historiek opgehaald
    assert o.state == "gesloten" and o.exit_reason == "EINDE_DAG"
    assert o.exit_px == pytest.approx(1.10300)


def test_max_hold_deadline_weekend():
    o = type("O", (), {"fill_time": "2026-10-03 12:00", "close_eod": False})()   # zaterdag + 14 d = zaterdag
    assert Manager.deadline(o) == pd.Timestamp("2026-10-16 23:50")                 # → vrijdag 23:50
    o.fill_time = "2026-10-07 12:00"                                               # woensdag + 14 d = woensdag
    assert Manager.deadline(o) == pd.Timestamp("2026-10-21 12:00")


def test_zone_tp_set_at_fill():
    fb = FakeBroker()
    tz = T0
    idx = pd.date_range(tz, periods=4, freq="15min")                    # candles 10:15 .. 11:00
    fb.bars["GBPUSD"] = pd.DataFrame({"open": 1.3010, "high": [1.3040, 1.3063, 1.3020, 1.3015],
                                      "low": 1.3005, "close": 1.3010, "spread": 0}, index=idx)
    m, fb = mgr(fb=fb)
    s = sig(key="z", setup="Zone GBPUSD", market="GBPUSD", limit=1.30000, anchor=1.29900, atr=0.001, tp_plan=None,
            cancel=None, max_rr=2.0, valid_bars=None, valid_until=T0 + pd.Timedelta(days=7),
            tp_mode="zone_bij_vulling", leg_high=1.30500)
    o = m.add_signal(s, T0)
    # SL = 1.29900 − (0.00003 + 0.0001) = 1.29887; risk 0.00113; voorlopige TP = 2R = 1.30226
    assert fb.calls[-1][4:6] == (1.29887, 1.30226)
    fb.set_price("GBPUSD", 1.29998, 1.30000, pd.Timestamp("2026-10-21 11:05"))   # vulling in de 11:00-candle
    m.step(pd.Timestamp("2026-10-21 11:05"))
    # TP = max(vertrekbeen 1.30500, highs 10:15–10:45 = 1.3063) = 1.3063, maar plafond 2R = 1.30226 → 1.30226
    assert o.state == "gevuld" and o.tp == pytest.approx(1.30226)
    # met een dichtere oude high: vertrekbeen 1.30100 en highs tot 1.30150 → TP 1.30150 (onder het plafond)
    fb2 = FakeBroker()
    fb2.bars["GBPUSD"] = pd.DataFrame({"open": 1.3010, "high": [1.3012, 1.3015, 1.3020, 1.3011],
                                       "low": 1.3005, "close": 1.3010, "spread": 0}, index=idx)
    m2, fb2 = mgr(fb=fb2)
    o2 = m2.add_signal(sig(**{**s.__dict__, "key": "z2", "leg_high": 1.30100}), T0)
    fb2.set_price("GBPUSD", 1.29998, 1.30000, pd.Timestamp("2026-10-21 10:50"))  # vulling in de 10:45-candle
    m2.step(pd.Timestamp("2026-10-21 10:50"))
    # candles vóór de vulcandle: 10:15 (1.3012) en 10:30 (1.3015) → TP 1.30150
    assert o2.tp == pytest.approx(1.30150)
    assert ("sltp", o2.position, 1.29887, 1.3015) in fb2.calls


def test_restart_keeps_state_and_picks_up_close(tmp_path):
    m, fb = mgr(tmp_path)
    o = m.add_signal(sig(), T0)
    fb.set_price("EURUSD", 1.10099, 1.10100, T0 + pd.Timedelta(minutes=30))
    m.step(T0 + pd.Timedelta(minutes=30))
    # KATSU ligt plat; ondertussen raakt de SL
    fb.set_price("EURUSD", 1.09989, 1.09990, T0 + pd.Timedelta(hours=2))
    m2 = Manager(fb, INS, LOTS, str(tmp_path / "state.json"), "orders")       # herstart
    o2 = m2.orders[o.id]
    assert o2.state == "gevuld"
    m2.step(T0 + pd.Timedelta(hours=2, minutes=1))
    assert o2.state == "gesloten" and o2.exit_reason == "SL"
    # verlies 0.00111 × 10 000 = −11,10, commissie −0,70 → −11,80 → R = −11,80/11,10 = −1,063
    assert o2.r_net == pytest.approx(-11.80 / 11.10)


def test_kill_switch():
    m, fb = mgr()
    a = m.add_signal(sig(key="a"), T0)
    fb.set_price("EURUSD", 1.10099, 1.10100, T0 + pd.Timedelta(minutes=20))
    m.step(T0 + pd.Timedelta(minutes=20))
    b = m.add_signal(sig(key="b", setup="Zone GBPUSD", market="GBPUSD", limit=1.3, anchor=1.299, tp_plan=None,
                         tp_mode="zone_bij_vulling", leg_high=1.305, cancel=None, valid_bars=None,
                         valid_until=T0 + pd.Timedelta(days=7)), T0)
    m.kill(T0 + pd.Timedelta(minutes=25))
    m.step(T0 + pd.Timedelta(minutes=25, seconds=10))
    assert m.paused and b.state == "geannuleerd" and a.state == "gesloten" and a.exit_reason == "NOODKNOP"
    assert fb.pending == {} and fb.open == {}
    c = m.add_signal(sig(key="c"), T0 + pd.Timedelta(hours=1))
    assert c.state == "geannuleerd" and "gepauzeerd" in c.reason


def test_broker_rejects_and_invalid_plan():
    m, fb = mgr()
    fb.reject_next = "Invalid stops"
    o = m.add_signal(sig(), T0)
    assert o.state == "geweigerd" and "Invalid stops" in o.reason
    o2 = m.add_signal(sig(key="x", tp_plan=1.10090), T0)              # TP onder de entry
    assert o2.state == "geweigerd"


def test_marketable_limit_becomes_market_order():
    m, fb = mgr()
    fb.set_price("EURUSD", 1.10050, 1.10051, T0)                      # ASK al onder de limiet 1.10100
    o = m.add_signal(sig(), T0)
    assert fb.calls[0][0] == "market" and o.state == "gevuld" and o.fill_px == pytest.approx(1.10051)


def test_missing_sl_tp_restored_and_unknown_orders_reported():
    m, fb = mgr()
    o = m.add_signal(sig(), T0)
    fb.set_price("EURUSD", 1.10099, 1.10100, T0 + pd.Timedelta(minutes=20))
    m.step(T0 + pd.Timedelta(minutes=20))
    fb.open[o.position].update(sl=0.0, tp=0.0)                         # iemand haalde SL/TP weg
    fb.pending[9999] = {"market": "EURUSD", "direction": "LONG", "price": 1.09, "sl": 1.08, "tp": 1.1,
                        "volume": 0.1, "magic": 710101, "comment": "?"}
    m.drain()
    m.step(T0 + pd.Timedelta(minutes=21))
    assert fb.open[o.position]["sl"] == pytest.approx(1.09989) and fb.open[o.position]["tp"] == pytest.approx(1.10322)
    texts = " ".join(e.text for e in m.drain())
    assert "#9999" in texts and "SL/TP ontbrak" in texts


def test_double_fill_in_same_group_keeps_first():
    m, fb = mgr()
    a = m.add_signal(sig(key="a", limit=1.10100), T0)
    b = m.add_signal(sig(key="b", t_sig=T0 + pd.Timedelta("15min"), limit=1.10110, cancel=None), T0)
    fb.set_price("EURUSD", 1.10095, 1.10096, T0 + pd.Timedelta(minutes=20))      # beide limieten in één tick
    m.step(T0 + pd.Timedelta(minutes=20))
    m.step(T0 + pd.Timedelta(minutes=20, seconds=10))
    states = sorted([a.state, b.state])
    assert states == ["gesloten", "gevuld"]
    closed = a if a.state == "gesloten" else b
    assert closed.exit_reason == "DUBBEL"


def test_demo_only_flag_on_fake():
    fb = FakeBroker(demo=False)
    assert fb.account().demo is False


@pytest.mark.skipif(not os.path.isdir(DATA), reason="geen koersdata op deze machine")
def test_replay_live_orders_match_backtest():
    """Het echte orderbeheer, nagespeeld met een nep-MT5 op september 2026, geeft dezelfde trades als de backtest."""
    from scripts.live_replay import replay
    orders, ctl, res = replay(DATA, "2026-09-01", "2026-09-30")
    assert ctl["n_trades"] >= 5
    assert ctl["overeenkomst"] == 1.0, [t["status"] for t in ctl["trades"]]
