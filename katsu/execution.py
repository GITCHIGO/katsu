"""
Uitvoering op M1 (spec §4–6): hoe een setup een echte trade wordt.

Prijzen in de MT5-data zijn BID. ASK = BID + spread.
- Een long koopt op ASK en wordt gesloten op BID (SL/TP kijken naar de BID).
- Een short verkoopt op BID en wordt gesloten op ASK (SL/TP kijken naar de ASK).

Conservatieve regels (geen gunstige aannames):
- Spread = max(spread van de candle, minimum uit de config). MT5 bewaart de laagste spread per candle.
- Slippage: elke markt- en stoporder wordt `slip_ticks` slechter gevuld.
- Opent een candle al voorbij de SL (gap), dan wordt gevuld op die open (min slippage).
- Raakt één M1-candle zowel SL als TP, dan telt de SL.
- TP is een limietorder: gevuld exact op de TP, nooit beter.
- Bij een limiet-entry (variant B) wordt op de vulcandle alleen de SL gecontroleerd,
  niet de TP (we weten niet of de high vóór of na de vulling kwam).
- Einde handelsdag = 00:00 servertijd (= 23:00 Brussel). Dan sluiten op de close van de laatste M1-candle.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from katsu.signals import LONG, Setup


@dataclass(frozen=True)
class Instrument:
    name: str = "XAUUSD"
    tick: float = 0.01            # kleinste prijsstap
    point: float = 0.01           # eenheid van de MT5-spreadkolom
    min_spread: float = 0.10      # minimum spread in prijs (spec §2)
    slip_ticks: int = 1           # slippage per markt-/stopuitvoering (spec §5)
    commission: float = 0.08      # commissie round turn per eenheid, in prijs (€7/lot ≈ $0,08/oz)
    rr: float = 2.0               # TP in R
    sl_atr_buffer: float = 0.1    # SL-buffer = spread + 0,1 × ATR
    min_sl_atr: float = 1.0       # minimale SL-afstand = 1 × ATR
    limit_valid_bars: int = 6     # variant B: geldigheid limietorder in setup-candles


@dataclass(frozen=True)
class OrderPlan:
    direction: str
    signal_time: pd.Timestamp
    kind: str                       # "market" of "limit"
    anchor: float                   # sweep-extreme (basis voor de SL)
    atr: float                      # ATR14 van de setup-timeframe op het signaal
    limit_price: float | None = None
    valid_until: pd.Timestamp | None = None


@dataclass
class Trade:
    direction: str
    signal_time: pd.Timestamp
    status: str                     # "gesloten", "sl_te_klein", "niet_gevuld", "geen_data"
    entry_time: pd.Timestamp | None = None
    fill: float | None = None
    sl: float | None = None
    tp: float | None = None
    risk: float | None = None
    exit_time: pd.Timestamp | None = None
    exit_price: float | None = None
    exit_reason: str | None = None  # "TP", "SL", "EINDE_DAG"
    r_gross: float | None = None
    cost_r: float | None = None
    r_net: float | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class M1:
    """Snelle toegang tot M1-data als numpy-reeksen."""
    def __init__(self, m1: pd.DataFrame, ins: Instrument):
        self.t = m1.index
        self.o = m1["open"].to_numpy(float); self.h = m1["high"].to_numpy(float)
        self.lo = m1["low"].to_numpy(float); self.c = m1["close"].to_numpy(float)
        self.sp = np.maximum(m1["spread"].to_numpy(float) * ins.point, ins.min_spread)


def _round_tick(x: float, tick: float) -> float:
    return round(round(x / tick) * tick, 10)


def simulate(plan: OrderPlan, d: M1, ins: Instrument) -> Trade:
    long = plan.direction == LONG
    s = 1.0 if long else -1.0
    slip = ins.slip_ticks * ins.tick
    i = int(d.t.searchsorted(plan.signal_time))      # eerste M1-candle die start op/na het signaal
    if i >= len(d.t):
        return Trade(plan.direction, plan.signal_time, "geen_data")

    # ---- Entry ----
    tp_from_same_bar = True
    if plan.kind == "market":
        fi = i
        fill = d.o[fi] + d.sp[fi] + slip if long else d.o[fi] - slip
    else:
        fi = None
        end_t = plan.valid_until
        j = i
        while j < len(d.t) and d.t[j] < end_t:
            ask_o, ask_l = d.o[j] + d.sp[j], d.lo[j] + d.sp[j]
            if long and ask_l <= plan.limit_price:
                fi = j; fill = min(plan.limit_price, ask_o); break
            if not long and d.h[j] >= plan.limit_price:
                fi = j; fill = max(plan.limit_price, d.o[j]); break
            j += 1
        if fi is None:
            return Trade(plan.direction, plan.signal_time, "niet_gevuld")
        tp_from_same_bar = False

    buffer = d.sp[fi] + ins.sl_atr_buffer * plan.atr
    sl = _round_tick(plan.anchor - s * buffer, ins.tick)
    risk = s * (fill - sl)
    if risk < ins.min_sl_atr * plan.atr:
        return Trade(plan.direction, plan.signal_time, "sl_te_klein", d.t[fi], fill, sl, None, risk)
    tp = _round_tick(fill + s * ins.rr * risk, ins.tick)

    # ---- Beheer tot exit ----
    day_end = (d.t[fi] + pd.Timedelta(days=1)).normalize()   # 00:00 servertijd volgende dag
    k = fi
    exit_price = reason = None
    while k < len(d.t) and d.t[k] < day_end:
        sp = d.sp[k]
        if long:
            adv_o, adv, fav = d.o[k], d.lo[k], d.h[k]                    # BID
        else:
            adv_o, adv, fav = d.o[k] + sp, d.h[k] + sp, d.lo[k] + sp    # ASK
        sl_hit = s * (adv - sl) <= 0
        tp_hit = s * (fav - tp) >= 0 and (k != fi or tp_from_same_bar)
        if sl_hit:
            gap = k != fi and s * (adv_o - sl) <= 0
            exit_price = (adv_o if gap else sl) - s * slip
            reason = "SL"; break
        if tp_hit:
            exit_price, reason = tp, "TP"; break
        k += 1
    if reason is None:
        k = min(k, len(d.t)) - 1                                       # laatste candle vóór einde dag
        close = d.c[k] if long else d.c[k] + d.sp[k]
        exit_price, reason = close - s * slip, "EINDE_DAG"

    r_gross = s * (exit_price - fill) / risk
    cost_r = ins.commission / risk
    return Trade(plan.direction, plan.signal_time, "gesloten", d.t[fi], fill, sl, tp, risk,
                 d.t[k], exit_price, reason, r_gross, cost_r, r_gross - cost_r)


# ---------------- Van setup naar orderplan ----------------

def entry_level_variant_b(setup: Setup, bars: pd.DataFrame) -> float:
    """Eerste FVG in de CHoCH-beweging (bovenkant bij long, onderkant bij short), anders 50%."""
    h = bars["high"].to_numpy(float); lo = bars["low"].to_numpy(float); c = bars["close"].to_numpy(float)
    a, b = setup.sweep_index, setup.choch_index
    for i in range(a + 1, b):                         # FVG-midden-candle i, met i-1 >= a en i+1 <= b
        if setup.direction == LONG and lo[i + 1] > h[i - 1]:
            return float(lo[i + 1])
        if setup.direction != LONG and h[i + 1] < lo[i - 1]:
            return float(h[i + 1])
    return float((setup.sweep_extreme + c[b]) / 2)


def make_plan(setup: Setup, bars: pd.DataFrame, tf: str, atr_series: pd.Series,
              variant: str, ins: Instrument) -> OrderPlan:
    atr = float(atr_series.iloc[setup.choch_index])
    if variant == "A":
        return OrderPlan(setup.direction, setup.signal_time, "market", setup.sweep_extreme, atr)
    lvl = entry_level_variant_b(setup, bars)
    valid = setup.signal_time + ins.limit_valid_bars * pd.Timedelta(tf)
    return OrderPlan(setup.direction, setup.signal_time, "limit", setup.sweep_extreme, atr, lvl, valid)


# ---------------- Portefeuille: 1 positie, dagstop ----------------

def run_portfolio(plans: list[OrderPlan], d: M1, ins: Instrument, day_stop_r: float = -2.0,
                  server_offset_h: int = 1) -> pd.DataFrame:
    """
    Speelt de plannen in tijdsvolgorde af:
    - maximaal 1 positie (of lopende limietorder) tegelijk;
    - na day_stop_r (som netto R) op een Brusselse kalenderdag geen nieuwe trades die dag.
    Overgeslagen setups worden ook gelogd (status 'positie_open' of 'dagstop').
    """
    rows = []
    busy_until = pd.Timestamp.min
    day_r: dict = {}
    for p in sorted(plans, key=lambda x: x.signal_time):
        day = (p.signal_time - pd.Timedelta(hours=server_offset_h)).date()
        if p.signal_time < busy_until:
            rows.append({"direction": p.direction, "signal_time": p.signal_time, "status": "positie_open"}); continue
        if day_r.get(day, 0.0) <= day_stop_r:
            rows.append({"direction": p.direction, "signal_time": p.signal_time, "status": "dagstop"}); continue
        tr = simulate(p, d, ins)
        if tr.status == "gesloten":
            busy_until = tr.exit_time + pd.Timedelta(minutes=1)
            day_r[day] = day_r.get(day, 0.0) + tr.r_net
        elif tr.status == "niet_gevuld" and p.valid_until is not None:
            busy_until = p.valid_until
        rows.append(tr.as_dict())
    return pd.DataFrame(rows)
