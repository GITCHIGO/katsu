"""
Gitchi-FVG (docs/spec_v0.4.md, versie 2 na Gitchi's feedback op 10 voorbeelden, 11 okt 2026).

LONG (SHORT exact gespiegeld):
- De MIDDELSTE candle van de FVG (candle 2) sluit boven de laatste bevestigde, nog intacte swing high.
- Bullish FVG: low(candle 3) > high(candle 1); het gat moet minstens MIN_GAP_ATR × ATR groot zijn.
- Candle 3 is een "volle" candle: body ≥ MIN_BODY3 × range (geen wick-candle).
- Entry = limiet in het gat op ENTRY_FRAC (61,8%) vanaf de rand waar de koers eerst komt (keuze Gitchi).
- SL-basis = laagste low van het order block (laatste bearish candle tussen de oorsprong en candle 1) t/m candle 2.
- TP = laagste bevestigde swing high boven de top van het been die sindsdien niet geraakt is,
  maar nooit verder dan MAX_RR × risico (wat het dichtst ligt; keuze Gitchi).

Intern werkt alles in "LONG-ruimte": voor SHORT worden de prijzen gespiegeld (high <-> −low, open/close × −1).
Alleen gesloten candles; swings pas na bevestiging.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from katsu.execution import OrderPlan
from katsu.structure import find_swings

L_STRUCT = 3
MIN_GAP_ATR = 0.5         # gat minstens een halve ATR ("niet te krap")
MIN_BODY3 = 0.25          # candle 3: body minstens 25% van de range ("geen wick-candle")
VALID_BARS = 480          # 5 handelsdagen op M15
MAX_COST_R = 0.2
ENTRY_FRAC = 0.618        # 61,8% in het gat
MAX_RR = 2.0              # TP-plafond
SL_BUFFER_ATR = 0.1       # zelfde buffer als de uitvoering (zonder spread) voor het geplande annuleerniveau


@dataclass(frozen=True)
class GfvgSetup:
    direction: str          # "LONG" of "SHORT"
    signal_index: int       # = candle 3 van de FVG (signaal op het einde ervan)
    fvg_index: int          # candle 3 van de FVG
    break_index: int        # candle 2 = de candle die de vorige high/low doorbrak
    broken_level: float     # de doorbroken swing high/low
    swing_index: int        # positie van die swing
    origin_index: int       # begin van het been (laagste low tussen swing en breuk)
    ob_index: int           # order block
    edge: float             # rand van het gat waar de koers eerst komt (LONG: bovenkant)
    gap_far: float          # andere rand van het gat
    anchor: float           # SL-basis
    tp: float | None        # oude high/low (None = geen doel)

    def entry(self, frac: float) -> float:
        return self.edge + frac * (self.gap_far - self.edge)


def _mirror(bars: pd.DataFrame, d: int):
    o, h, lo, c = (bars[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    if d > 0:
        return o, h, lo, c
    return -o, -lo, -h, -c


def _one_side(bars: pd.DataFrame, a: np.ndarray, d: int, L: int, min_gap: float, min_body3: float):
    o, h, lo, c = _mirror(bars, d)
    n = len(c)
    sw = find_swings(pd.DataFrame({"high": h, "low": lo}), L)
    highs = sorted((s for s in sw if s.kind == "HIGH"), key=lambda s: s.confirmed_at)
    conf = np.array([s.confirmed_at for s in highs], dtype=int)
    hidx = np.array([s.index for s in highs], dtype=int)
    hprice = np.array([s.price for s in highs], dtype=float)
    # eerste latere candle waarvan de high een swing high weer raakt (>=)
    nxt_ge = np.full(n, n, dtype=int)
    stack: list[int] = []
    for i in range(n):
        while stack and h[i] >= h[stack[-1]]:
            nxt_ge[stack.pop()] = i
        stack.append(i)
    death = nxt_ge[hidx] if len(hidx) else np.array([], dtype=int)
    sgn = 1 if d > 0 else -1
    direction = "LONG" if d > 0 else "SHORT"
    out = []
    broken = np.zeros(len(highs), bool)
    for b in range(1, n - 1):                       # b = candle 2, k = b + 1 = candle 3
        q = int(np.searchsorted(conf, b, side="right"))
        if q == 0:
            continue
        j = q - 1                                    # laatste bevestigde swing high op candle 2
        if broken[j] or c[b] <= hprice[j]:
            continue
        broken[j] = True                             # een swing kan maar één keer gebroken worden
        if c[hidx[j] + 1:b].max(initial=-np.inf) > hprice[j]:
            continue
        k = b + 1
        gap = lo[k] - h[k - 2]
        if not (gap > 0 and np.isfinite(a[k]) and gap >= min_gap * a[k]):
            continue
        rng3 = h[k] - lo[k]
        if rng3 <= 0 or abs(c[k] - o[k]) < min_body3 * rng3:
            continue
        origin = hidx[j] + int(np.argmin(lo[hidx[j]:b + 1]))
        bear = [i for i in range(origin, k - 1) if c[i] < o[i]]
        ob = bear[-1] if bear else origin
        anchor = float(lo[ob:k].min())
        leg_high = h[origin:k + 1].max()
        cand = (death[:int(np.searchsorted(conf, k, side="right"))] > k) & \
               (hprice[:int(np.searchsorted(conf, k, side="right"))] > leg_high)
        tp = float(hprice[:len(cand)][cand].min()) if cand.any() else None
        out.append(GfvgSetup(direction, k, k, b, float(sgn * hprice[j]), int(hidx[j]), int(origin), int(ob),
                             float(sgn * lo[k]), float(sgn * h[k - 2]), float(sgn * anchor),
                             None if tp is None else float(sgn * tp)))
    return out


def detect_gfvg(bars: pd.DataFrame, atr_values, L: int = L_STRUCT, min_gap: float = MIN_GAP_ATR,
                min_body3: float = MIN_BODY3) -> list[GfvgSetup]:
    """Alle Gitchi-FVG's (LONG en SHORT), gesorteerd op signaalcandle."""
    a = np.asarray(atr_values, dtype=float)
    out = _one_side(bars, a, 1, L, min_gap, min_body3) + _one_side(bars, a, -1, L, min_gap, min_body3)
    return sorted(out, key=lambda s: (s.signal_index, s.direction))


def make_gfvg_plan(s: GfvgSetup, bars: pd.DataFrame, atr_values, validity: str, market: str,
                   entry_frac: float = ENTRY_FRAC, max_rr: float | None = MAX_RR,
                   tf: str = "15min") -> OrderPlan | None:
    """
    Orderplan (spec v0.4 §5). validity = 'ongeldig' (5 handelsdagen) of '24u'. None = geen TP.
    Annuleerniveau = de geplande TP: de oude high/low, of het 2R-niveau als dat dichterbij ligt
    (gepland met de SL-basis − 0,1 ATR; de echte TP rekent de uitvoering na de vulling uit met de echte spread).
    """
    if s.tp is None:
        return None
    step = pd.Timedelta(tf)
    t_sig = bars.index[s.signal_index] + step
    if validity == "24u":
        until = t_sig + pd.Timedelta(hours=24)
    else:
        until = bars.index[min(s.signal_index + VALID_BARS, len(bars) - 1)] + step
    a = float(np.asarray(atr_values)[s.fvg_index])
    entry = s.entry(entry_frac)
    cancel = s.tp
    if max_rr is not None:
        sgn = 1.0 if s.direction == "LONG" else -1.0
        risk = sgn * (entry - (s.anchor - sgn * SL_BUFFER_ATR * a))
        cap = entry + sgn * max_rr * risk
        if sgn * (cancel - cap) > 0:
            cancel = cap
    return OrderPlan(s.direction, t_sig, "limit", s.anchor, a, entry, until, market=market,
                     max_cost_r=MAX_COST_R, tp_price=s.tp, cancel_price=cancel, max_rr=max_rr)
