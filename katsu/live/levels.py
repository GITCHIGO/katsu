"""
SL en TP voor een live order, met exact dezelfde formules als de backtest (katsu/execution.simulate en
katsu/zones.tp_at_fill). Een test vergelijkt deze functies met simulate().

Enige keuze die live anders moet: de backtest neemt de spread van de vulcandle voor de SL-buffer. Die is bij het
plaatsen van een limiet nog niet bekend. Live gebruikt de minimumspread van het instrument (= wat de backtest neemt
als de candle geen bredere spread toont, wat bij IC Markets Raw meestal zo is).
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from katsu.execution import Instrument, _round_tick
from katsu.zones import tp_at_fill


def sign(direction: str) -> float:
    return 1.0 if direction == "LONG" else -1.0


def sl_price(direction: str, anchor: float, atr: float, ins: Instrument, spread: float | None = None) -> float:
    """SL = anchor voorbij met spread + 0,1 × ATR (zoals simulate)."""
    sp = ins.min_spread if spread is None else max(spread, ins.min_spread)
    return _round_tick(anchor - sign(direction) * (sp + ins.sl_atr_buffer * atr), ins.tick)


def tp_price(direction: str, fill: float, sl: float, ins: Instrument, tp_plan: float | None,
             max_rr: float | None) -> float | None:
    """TP zoals simulate: vaste TP (oude high) met plafond max_rr × risk, of rr × risk zonder vaste TP.
    None als de TP niet voorbij de vulling ligt (backtest: 'tp_ongeldig' = geen trade)."""
    s = sign(direction)
    risk = s * (fill - sl)
    if risk <= 0:
        return None
    if tp_plan is not None and np.isfinite(tp_plan):
        tp = tp_plan
        if max_rr is not None and s * (tp - (fill + s * max_rr * risk)) > 0:
            tp = fill + s * max_rr * risk
    else:
        tp = fill + s * ins.rr * risk
    tp = _round_tick(tp, ins.tick)
    return tp if s * (tp - fill) > 0 else None


def zone_tp_plan(direction: str, leg_high: float, highs: np.ndarray, lows: np.ndarray) -> float:
    """Zone v0.7b: TP = uiterste van het vertrekbeen t/m de laatste gesloten M15-candle vóór de vulling.
    highs/lows = de M15-candles vanaf het bekend worden van de zone tot (zonder) de vulcandle."""
    z = SimpleNamespace(direction=direction, leg_high=leg_high)
    return tp_at_fill(z, np.asarray(highs, float), np.asarray(lows, float), 0, len(highs))
