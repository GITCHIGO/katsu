"""
Zones: supply & demand / order block met limietorder (docs/spec_v0.7.md).

LONG (demand): op TF-candle k de eerste close boven de laatste bevestigde, ongebroken swing high (L = 3);
oorsprong o = laagste low tussen die swing high en k; kracht close[k] − low[o] ≥ 2 × ATR[k];
zone = order block (laatste dalende candle in o−2..o, anders candle o): bovenrand = high daarvan, onderrand = low[o];
zone hoger dan 1,5 × ATR → geen zone. SHORT gespiegeld (in "LONG-ruimte": prijzen × −1, high ↔ low).
Alleen gesloten candles; de zone is bekend op het einde van candle k.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from katsu.execution import OrderPlan
from katsu.structure import find_swings

L_STRUCT = 3
MIN_DEPART_ATR = 2.0
MAX_ZONE_ATR = 1.5
OB_LOOKBACK = 2
VALID = pd.Timedelta(days=7)
MAX_RR = 2.0


@dataclass(frozen=True)
class Zone:
    direction: str      # LONG / SHORT
    k: int              # breukcandle (zone bekend op haar einde)
    o: int              # oorsprong
    ob: int             # order-block-candle
    top: float          # proximale rand (LONG: bovenrand)
    bottom: float       # distale rand (LONG: onderrand = laagste punt)
    leg_high: float     # top van het vertrekbeen (LONG); bij SHORT de bodem
    fvg: bool           # liet het vertrek een FVG achter
    atr: float


def _space(bars: pd.DataFrame, d: int):
    o, h, lo, c = (bars[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    return (o, h, lo, c) if d > 0 else (-o, -lo, -h, -c)


def find_zones(bars: pd.DataFrame, atr_values, L: int = L_STRUCT) -> list[Zone]:
    a = np.asarray(atr_values, float)
    out: list[Zone] = []
    for d in (1, -1):
        o_, h, lo, c = _space(bars, d)
        sw = find_swings(pd.DataFrame({"high": h, "low": lo}), L)
        highs = sorted((s for s in sw if s.kind == "HIGH"), key=lambda s: s.confirmed_at)
        q = 0
        active = None                                  # (index, prijs) van de laatste bevestigde ongebroken swing high
        for k in range(len(c)):
            while q < len(highs) and highs[q].confirmed_at <= k:
                active = (highs[q].index, highs[q].price); q += 1
            if active is None or not np.isfinite(a[k]):
                continue
            si, sp = active
            if c[k] <= sp:
                continue
            active = None                              # doorbroken: wacht op een nieuwe bevestigde swing high
            seg = np.arange(si + 1, k + 1)
            if len(seg) == 0:
                continue
            org = int(seg[np.argmin(lo[seg])])
            if c[k] - lo[org] < MIN_DEPART_ATR * a[k]:
                continue
            ob = org
            for j in range(org, max(org - OB_LOOKBACK, 0) - 1, -1):
                if c[j] < o_[j]:
                    ob = j; break
            top, bottom = h[ob], lo[org]
            if top - bottom > MAX_ZONE_ATR * a[k] or top <= bottom:
                continue
            leg = float(h[org:k + 1].max())
            fvg = bool(any(lo[j] > h[j - 2] for j in range(max(org + 2, 2), k + 1)))
            if d > 0:
                out.append(Zone("LONG", k, org, ob, float(top), float(bottom), leg, fvg, float(a[k])))
            else:
                out.append(Zone("SHORT", k, org, ob, float(-top), float(-bottom), -leg, fvg, float(a[k])))
    out.sort(key=lambda z: (z.k, z.direction))
    return out


def zone_entry(z: Zone, entry: str) -> float:
    """'rand' = proximale rand; '38.2' = 38,2% diep vanaf de proximale rand."""
    if entry == "rand":
        return z.top
    if entry == "38.2":
        return z.top - 0.382 * (z.top - z.bottom)
    raise ValueError(entry)


def make_zone_plan(z: Zone, bars: pd.DataFrame, entry: str, market: str, tf: str) -> OrderPlan:
    t_known = bars.index[z.k] + pd.Timedelta(tf)
    px = zone_entry(z, entry)
    return OrderPlan(z.direction, t_known, "limit", z.bottom, z.atr, px, t_known + VALID, market=market,
                     tp_price=z.leg_high, cancel_price=z.leg_high, max_rr=MAX_RR)


def tp_at_fill(z: Zone, high, low, i_from: int, i_fill: int) -> float:
    """v0.7b: TP = extreme van het vertrekbeen t/m de laatste uitvoeringscandle vóór de vulling (i_fill exclusief).
    high/low = arrays van de uitvoeringsdata; i_from = eerste uitvoeringscandle na het bekend worden van de zone."""
    if z.direction == "LONG":
        seg = high[i_from:i_fill]
        return float(max(z.leg_high, seg.max())) if len(seg) else z.leg_high
    seg = low[i_from:i_fill]
    return float(min(z.leg_high, seg.min())) if len(seg) else z.leg_high


def make_zone_plan_b(z: Zone, bars: pd.DataFrame, entry: str, market: str, tf: str, tp: float | None = None) -> OrderPlan:
    """v0.7b: geen annulering; tp = None geeft een verre TP (enkel om de vulling te vinden)."""
    t_known = bars.index[z.k] + pd.Timedelta(tf)
    px = zone_entry(z, entry)
    far = px + (1e6 if z.direction == "LONG" else -1e6) if tp is None else tp
    return OrderPlan(z.direction, t_known, "limit", z.bottom, z.atr, px, t_known + VALID, market=market,
                     tp_price=far, max_rr=MAX_RR if tp is not None else None)
