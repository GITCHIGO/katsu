"""
Handberekende scenario's voor ronde 3 (katsu/blocks.py).

Basis = het BOS-scenario uit tests/test_bos.py (BOS LONG op candle 10, higher low 100 op candle 8),
aangevuld met drie candles:
  11: 107 / 107,5 / 105   / 105,5   (open/high/low/close)
  12: 105,5 / 106 / 103,8 / 104,2
  13: 104,2 / 104,5 / 103,0 / 103,5
Order block = laatste rode candle tussen candle 8 en de BOS = candle 8 (open 101,5 close 100,5), high 104.
  -> candle 12 raakt 104 (low 103,8): instap 104.
Fibonacci: been 100 -> 108 (hoogste high t/m candle 10). 61,8%: 108 − 0,618 × 8 = 103,056
  -> candle 13 raakt het (low 103,0): instap 103,056. Bij 70,5% (102,36) geen aanraking.
"""
import numpy as np
import pandas as pd
import pytest

from katsu import blocks as B
from tests.test_bos import BASE, make

EXT = list(BASE) + [(107.5, 105, 107, 105.5), (106, 103.8, 105.5, 104.2), (104.5, 103.0, 104.2, 103.5)]


def ext_bars():
    # make() verwacht (high, low, open, close)
    return make(EXT)


def test_order_block():
    ev = B.ob_events(ext_bars(), "5min", L=1)
    r = ev.iloc[0]
    assert (r.k, r.d, r.ob_index, r.entry_bar, r.entry_price) == (10, 1, 8, 12, 104)
    assert not bool(r.fvg)                         # low 104 van de BOS-candle is niet > high 104 van candle 8


def test_fibonacci_618_en_705():
    ev = B.fib_events(ext_bars(), "5min", L=1, level=0.618)
    r = ev.iloc[0]
    assert (r.k, r.entry_bar) == (10, 13) and r.entry_price == pytest.approx(103.056)
    assert (r.top, r.bot) == (108, 100)
    assert len(B.fib_events(ext_bars(), "5min", L=1, level=0.705)) == 0


def test_fibonacci_vervalt_bij_nieuwe_high():
    rows = list(BASE) + [(108.5, 106, 107, 108)] + EXT[11:]      # candle 11 maakt een nieuwe high
    assert len(B.fib_events(make(rows), "5min", L=1, level=0.618)) == 0


def _rows_from_closes(cl):
    return [(c + 0.2, c - 0.2, c, c) for c in cl]                # high, low, open, close


def test_rsi_divergentie():
    cl = [110, 108, 105, 100, 104, 103, 102, 101, 99.5, 102, 103]
    b = make(_rows_from_closes(cl))
    from katsu.trend import rsi
    r = rsi(b["close"], 14)
    assert r[8] > r[3]                            # voorwaarde: tweede low (99,5) heeft hogere RSI dan de eerste (100)
    ev = B.rsi_div_events(b, L=1)
    assert list(zip(ev.k, ev.d)) == [(9, 1)]      # tweede low op candle 8, bevestigd op candle 9


def test_bpr():
    rows = [(101, 99, 100, 100.5), (104, 100.5, 100.5, 103.8), (105, 102, 103.8, 104.5),
            (104, 101.6, 104.5, 102), (101.5, 100, 102, 100.5)]
    ev = B.bpr_events(make(rows))
    assert list(zip(ev.k, ev.d)) == [(4, -1)]     # bearish FVG 101,5–102 overlapt bullish FVG 101–102


def test_exhaustion_fvg():
    cl = [100 + 0.5 * i for i in range(13)]
    b = make(_rows_from_closes(cl))
    ev = B.exhaustion_events(b, np.ones(13))      # +6 in 12 candles ≥ 4 ATR -> ommekeer op candle 12
    assert list(zip(ev.k, ev.d)) == [(12, -1)]
    assert len(B.exhaustion_events(b, np.full(13, 2.0))) == 0


def test_equal_highs_sweep():
    rows = [(103, 101, 102, 102), (104, 102, 102, 103), (105, 103, 103, 104), (104, 102, 104, 103),
            (104.5, 102.5, 103, 104), (105.05, 103, 104, 104.5), (104, 102, 104.5, 103), (105.5, 103, 103, 104.8)]
    ev = B.equal_sweep_events(make(rows), np.ones(8), L=1)
    assert list(zip(ev.k, ev.d)) == [(7, -1)]     # highs 105 en 105,05 (binnen 0,1 ATR) geveegd, close 104,8
