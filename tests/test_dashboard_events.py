"""Bouwstenen-dashboard: setups en kenmerken, met de hand uitgerekend (L = 1 om de reeksen kort te houden)."""
import numpy as np
import pandas as pd
import pytest

from katsu.dashboard_events import (bin_label, breuk_label, build_events, day_context, nfp_day, rel_trend,
                                    session_label)

# zelfde reeks als tests/test_gfvg.py: breuk van swing high 105 door candle 9, FVG 101–102 op candle 10
BASE = [(100, 101, 99, 100), (100, 110, 100, 105), (105, 106, 103, 104), (104, 105, 101, 102),
        (102, 103, 100, 101), (101, 105, 100.5, 104), (104, 104, 102, 102.5), (102.5, 103, 98, 99),
        (99, 101, 98.5, 100.8), (100.8, 106, 100.7, 105.8), (104, 107, 102, 106.8),
        (106.8, 106.9, 105, 105.5), (105.5, 106, 104, 104.5)]


def bars(rows, start="2018-03-05 08:00"):
    idx = pd.date_range(start, periods=len(rows), freq="15min")
    o, h, l, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "spread": 0}, index=idx)


def test_fvg_met_breuk_zoals_spec_v04():
    ev = build_events(bars(BASE), L=1)
    e = ev[(ev.soort == "FVG") & (ev.d == 1) & (ev.s == 10)].iloc[0]
    assert e.brk and e.swing_idx == 5 and e.c1 == 8
    assert e.entry == pytest.approx(102 - 0.382) and e.anchor == 98 and e.tp == 110
    assert e.gap == pytest.approx(1.0) and e.disp == pytest.approx(5.0) and e.ob


def test_ifvg_na_close_door_een_bearish_gat():
    # bearish FVG op candle 4 (high 99 < low(2) 100): gat 99–100; candle 6 sluit boven 100 -> bullish IFVG op 6
    rows = [(103, 104, 102, 103), (103, 103.5, 101, 101.5), (101.5, 101.8, 100, 100.2), (100.2, 100.3, 98.5, 98.8),
            (98.8, 99, 97.5, 97.8), (97.8, 99.5, 97.6, 99.4), (99.4, 101.2, 99.2, 101.0), (101, 101.5, 100.6, 101.2)]
    ev = build_events(bars(rows), L=1)
    e = ev[(ev.soort == "IFVG") & (ev.d == 1)].iloc[0]
    assert e.s == 6 and e.c1 == 2
    assert e.entry == pytest.approx(100 - 0.382 * 1.0)            # bovenrand 100, onderrand 99
    assert e.anchor == pytest.approx(97.5)                         # laagste low van candle 2 t/m 6


def test_spiegeling_short():
    rows = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in BASE]
    ev = build_events(bars(rows), L=1)
    e = ev[(ev.soort == "FVG") & (ev.d == -1) & (ev.s == 10)].iloc[0]
    assert e.entry == pytest.approx(98 + 0.382) and e.anchor == 102 and e.tp == 90


def test_labels():
    assert list(breuk_label(np.array([False, True, True, True]), np.array(["UP", "UP", "DOWN", "NEUTRAL"], dtype=object))) == \
        ["geen", "BOS", "CHoCH", "breuk uit neutraal"]
    assert list(rel_trend(np.array(["UP", "UP", "NEUTRAL"], dtype=object), np.array([1, -1, 1]))) == ["mee", "tegen", "neutraal"]
    assert list(session_label(np.array([3, 9, 14, 18, 23]))) == ["Azië", "Londen", "overlap", "New York", "nacht"]
    assert list(bin_label([0.1, 0.25, 0.7, np.nan], [0.25, 0.5], ["a", "b", "c"])) == ["a", "b", "c", "onbekend"]


def test_nfp_en_dagcontext():
    t = pd.DatetimeIndex(["2021-03-05 15:30", "2021-03-12 15:30", "2021-04-02 15:30"])   # vr 5/3, vr 12/3, vr 2/4
    assert list(nfp_day(t)) == [True, False, True]
    idx = pd.date_range("2021-03-08 00:00", periods=2 * 96, freq="15min")
    b = pd.DataFrame({"open": 1.0, "high": 1.0 + np.arange(192) * 0, "low": 1.0, "close": 1.0, "spread": 0}, index=idx)
    b.loc[idx[10], "low"] = 0.9                                   # maandag 02:30 server: lage low (in de Azië-sessie)
    ctx = day_context(b)
    assert np.isnan(ctx.prev_l.iloc[0]) and ctx.prev_l.iloc[100] == pytest.approx(0.9)
    assert np.isnan(ctx.asia_l.iloc[20]) and ctx.asia_l.iloc[40] == pytest.approx(0.9)   # pas na 09:00 bekend
