"""
De uitvoering in de replay (replay/sim.js) moet exact hetzelfde doen als katsu/execution.py.
1) Met de hand uitgerekende gevallen (zelfde getallen als tests/test_execution.py).
2) 300 willekeurige koersreeksen: dezelfde order in Python en in JS -> zelfde vulling, uitstap en reden.
"""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from katsu.execution import EURUSD, M1, Instrument, OrderPlan, simulate

NODE = shutil.which("node")
CLI = str(Path(__file__).resolve().parents[1] / "replay" / "sim_cli.js")
pytestmark = pytest.mark.skipif(NODE is None, reason="node niet geïnstalleerd")
T0 = pd.Timestamp("2025-01-06 10:00")
TEST_SPEC = {"point": 0.01, "tick": 0.01, "minSpread": 0.10, "slip": 0.01, "comm": 0.08, "rolloverMin": 0.0}


def run_js(sym, bars, orders, spec=None):
    inp = {"sym": sym, "spec": spec or {}, "bars": bars, "orders": orders}
    res = subprocess.run([NODE, CLI], input=json.dumps(inp), capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def mins(ts):
    return int(np.datetime64(ts, "m").astype(np.int64))


def bars_from(rows, start=T0, spread=5):
    return [{"t": mins(start) + i, "o": o, "h": h, "l": l, "c": c, "s": spread} for i, (o, h, l, c) in enumerate(rows)]


def test_market_long_tp_zoals_python():
    b = bars_from([(100, 100.5, 99.8, 100.2), (100.2, 105.0, 100.0, 104.9)])
    (o,) = run_js("XAUUSD", b, [{"dir": 1, "type": "market", "sl": 97.80, "tp": 104.73}], TEST_SPEC)
    assert o["fill"] == pytest.approx(100.11) and o["reason"] == "TP"
    assert o["rGross"] == pytest.approx(2.0) and o["rNet"] == pytest.approx(2.0 - 0.08 / 2.31)


def test_sl_met_slippage_en_sl_eerst_bij_twijfel():
    b = bars_from([(100, 100.5, 99.8, 100.2), (100.2, 105.0, 97.5, 104.0)])
    (o,) = run_js("XAUUSD", b, [{"dir": 1, "type": "market", "sl": 97.80, "tp": 104.73}], TEST_SPEC)
    assert o["reason"] == "SL" and o["exitPx"] == pytest.approx(97.79)


def test_gap_door_sl_vult_op_open():
    b = bars_from([(100, 100.5, 99.8, 100.2), (97.0, 97.2, 96.9, 97.1)])
    (o,) = run_js("XAUUSD", b, [{"dir": 1, "type": "market", "sl": 97.80, "tp": 104.73}], TEST_SPEC)
    assert o["exitPx"] == pytest.approx(96.99)


def test_limiet_geen_tp_op_vulcandle():
    b = bars_from([(100, 100.5, 99.8, 100.2), (100.2, 110.0, 99.3, 100.0), (100.0, 100.4, 99.9, 100.1)])
    (o,) = run_js("XAUUSD", b, [{"dir": 1, "type": "limit", "entry": 99.5, "sl": 97.8, "tp": 102.9}], TEST_SPEC)
    assert o["status"] == "open" and o["fill"] == 99.5 and o["fillT"] == mins(T0) + 1


def test_manueel_sluiten_op_de_volgende_open():
    b = bars_from([(100, 100.5, 99.8, 100.2), (100.2, 100.6, 100.0, 100.5), (100.5, 100.9, 100.4, 100.8)])
    (o,) = run_js("XAUUSD", b, [{"dir": 1, "type": "market", "sl": 97.8, "tp": 104.0, "closeAt": mins(T0) + 2}],
                  TEST_SPEC)
    assert o["reason"] == "MANUEEL" and o["exitPx"] == pytest.approx(100.49)


@pytest.mark.parametrize("seed", range(6))
def test_willekeurige_reeksen_zelfde_als_python(seed):
    rng = np.random.default_rng(seed)
    n = 3000
    idx = pd.date_range("2021-03-08 20:00", periods=n, freq="1min")     # loopt door de rollover
    steps = rng.normal(0, 0.00012, n).cumsum() + 1.2
    o = np.round(steps, 5); c = np.round(o + rng.normal(0, 0.00008, n), 5)
    h = np.round(np.maximum(o, c) + rng.exponential(0.00006, n), 5)
    l = np.round(np.minimum(o, c) - rng.exponential(0.00006, n), 5)
    sp = rng.integers(0, 8, n)
    m1 = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "spread": sp}, index=idx)
    ins = Instrument("EURUSD", tick=0.00001, point=0.00001, min_spread=0.00001, slip=0.00003, commission=0.00008,
                     rollover_min_spread=0.00005, rr=2.0)
    d = M1(m1, ins)
    bars = [{"t": mins(t), "o": float(a), "h": float(b_), "l": float(cc), "c": float(e), "s": int(s)}
            for t, a, b_, cc, e, s in zip(idx, o, h, l, c, sp)]
    orders, pys = [], []
    for k in range(50):
        i = int(rng.integers(10, n - 500)); dr = 1 if rng.random() < 0.5 else -1
        kind = ["market", "limit", "stop"][k % 3]
        ref = o[i]
        ent = ref - dr * 0.0003 if kind == "limit" else ref + dr * 0.0003
        anchor = ref - dr * 0.0010
        plan = OrderPlan("LONG" if dr > 0 else "SHORT", idx[i], kind, anchor, 0.0001,
                         None if kind == "market" else ent, idx[-1] + pd.Timedelta(minutes=1),
                         tp_price=ref + dr * 0.0015)
        tr = simulate(plan, d, ins)
        if tr.status != "gesloten":
            continue
        pys.append(tr)
        orders.append({"dir": dr, "type": kind, "entry": None if kind == "market" else ent, "sl": tr.sl,
                       "tp": tr.tp, "_start": mins(idx[i])})
    js = []
    for od in orders:
        start = od.pop("_start")
        js += run_js("EURUSD", [b for b in bars if b["t"] >= start], [od])
    assert len(js) == len(pys) and len(pys) > 10
    for p, j in zip(pys, js):
        assert j["fill"] == pytest.approx(p.fill, abs=1e-9)
        assert j["exitPx"] == pytest.approx(p.exit_price, abs=1e-9)
        assert j["exitT"] == mins(p.exit_time)
        assert j["reason"] == p.exit_reason
        assert j["rNet"] == pytest.approx(p.r_net + p.swap_r, abs=1e-9)           # swap rekent alleen Python
