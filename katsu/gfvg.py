"""
Gitchi-FVG (docs/spec_v0.4.md): een FVG telt alleen als de beweging die hem maakt een vorige swing high breekt
(bearish: een vorige swing low). Instap = limiet op de rand van de FVG, SL-basis = order block / laatste low,
TP = eerstvolgende oude swing high boven het been die nog niet geraakt is.

Alles werkt intern in "LONG-ruimte": voor SHORT worden de prijzen gespiegeld (high <-> −low, open/close × −1),
zodat één stuk logica beide richtingen dekt. Alleen gesloten candles; swings pas na bevestiging.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from katsu.execution import OrderPlan
from katsu.structure import find_swings

L_STRUCT = 3
VALID_BARS = 480          # 5 handelsdagen op M15
MAX_COST_R = 0.2


@dataclass(frozen=True)
class GfvgSetup:
    direction: str          # "LONG" of "SHORT"
    signal_index: int       # candle waarop het signaal er is (einde van die candle)
    fvg_index: int          # candle 3 van de FVG
    break_index: int        # candle die de vorige high/low doorbrak
    broken_level: float     # de doorbroken swing high/low
    origin_index: int       # begin van het been
    ob_index: int           # order block (laatste candle tegen de richting vóór de FVG)
    entry: float            # rand van de FVG (LONG: bovenkant, SHORT: onderkant)
    gap_far: float          # andere rand van de FVG
    anchor: float           # SL-basis (LONG: laagste low OB..candle 2)
    tp: float | None        # oude high/low (None = geen doel gevonden)
    leg_end_index: int      # candle waarop het einde van de duw bekend is (nieuwe swing bevestigd)
    replaced_index: int | None = None   # variant 'laatste': candle waarop een nieuwere FVG deze vervangt


def _mirror(bars: pd.DataFrame, d: int):
    o, h, lo, c = (bars[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    if d > 0:
        return o, h, lo, c
    return -o, -lo, -h, -c


def _setups_one_side(bars: pd.DataFrame, d: int, choice: str, L: int) -> list[GfvgSetup]:
    o, h, lo, c = _mirror(bars, d)
    n = len(c)
    m = pd.DataFrame({"high": h, "low": lo})
    sw = find_swings(m, L)
    highs = sorted((s for s in sw if s.kind == "HIGH"), key=lambda s: s.confirmed_at)
    conf = np.array([s.confirmed_at for s in highs], dtype=int)
    hidx = np.array([s.index for s in highs], dtype=int)
    hprice = np.array([s.price for s in highs], dtype=float)
    fvg_at = np.zeros(n, bool)
    fvg_at[2:] = lo[2:] > h[:-2]                       # bullish FVG met candle 3 = k
    used_fvg: set[int] = set()
    out: list[GfvgSetup] = []
    sgn = 1 if d > 0 else -1
    direction = "LONG" if d > 0 else "SHORT"

    def ob_and_anchor(origin, k):
        bear = [i for i in range(origin, k - 1) if c[i] < o[i]]        # origin .. candle 1
        ob = bear[-1] if bear else origin
        return ob, float(lo[ob:k].min())                               # OB t/m candle 2

    # moment waarop elke swing high voor het eerst weer geraakt wordt (eerste latere high >= prijs)
    nxt_ge = np.full(n, n, dtype=int)
    stack: list[int] = []
    for i in range(n):
        while stack and h[i] >= h[stack[-1]]:
            nxt_ge[stack.pop()] = i
        stack.append(i)
    death = nxt_ge[hidx] if len(hidx) else np.array([], dtype=int)

    def target(sig, leg_high):
        # bevestigd op/vóór sig, boven het been, sindsdien door geen high geraakt -> de laagste daarvan
        q = int(np.searchsorted(conf, sig, side="right"))
        ok = (death[:q] > sig) & (hprice[:q] > leg_high)
        return float(hprice[:q][ok].min()) if ok.any() else None

    def untouched(k, sig):
        return k == sig or lo[k + 1:sig + 1].min() > lo[k]

    def make(k, sig, b, H, origin, leg_end):
        ob, anchor = ob_and_anchor(origin, k)
        leg_high = h[origin:sig + 1].max()
        tp = target(sig, leg_high)
        return GfvgSetup(direction, int(sig), int(k), int(b), float(sgn * H), int(origin), int(ob),
                         float(sgn * lo[k]), float(sgn * h[k - 2]), float(sgn * anchor),
                         None if tp is None else float(sgn * tp), int(leg_end))

    broken = np.zeros(len(highs), bool)
    for b in range(n):
        m_ = int(np.searchsorted(conf, b, side="right"))            # swings bevestigd op/vóór b
        if m_ == 0:
            continue
        j = m_ - 1                                                   # laatste bevestigde swing high
        if broken[j] or c[b] <= hprice[j]:
            continue
        broken[j] = True
        if c[hidx[j] + 1:b].max(initial=-np.inf) > hprice[j]:        # al eerder doorbroken: telt niet
            continue
        H, hi_ = hprice[j], hidx[j]
        origin = hi_ + int(np.argmin(lo[hi_:b + 1]))
        # einde van de duw: eerste swing high met index >= b die bevestigd wordt
        later = np.where(hidx >= b)[0]
        leg_end = int(conf[later].min()) if len(later) else n - 1
        cluster = [k for k in range(max(origin + 2, 2), min(leg_end, n - 1) + 1)
                   if fvg_at[k] and k - 2 >= origin and k not in used_fvg]
        if not cluster:
            continue
        if choice == "eerste":
            for k in cluster:
                sig = max(k, b)
                if untouched(k, sig):
                    used_fvg.add(k)
                    out.append(make(k, sig, b, H, origin, leg_end))
                    break
        else:                                                         # "laatste"
            # op de breuk: de nieuwste onaangeraakte FVG; daarna vervangt elke nieuwe FVG de vorige
            cands = [k for k in cluster if max(k, b) == b and untouched(k, b)]
            chain = ([cands[-1]] if cands else []) + [k for k in cluster if k > b]
            chain = [k for k in chain if untouched(k, max(k, b))]
            for i, k in enumerate(chain):
                used_fvg.add(k)
                s = make(k, max(k, b), b, H, origin, leg_end)
                nxt = chain[i + 1] if i + 1 < len(chain) else None
                out.append(s if nxt is None else GfvgSetup(**{**s.__dict__, "replaced_index": int(nxt)}))
    return out


def detect_gfvg(bars: pd.DataFrame, choice: str = "eerste", L: int = L_STRUCT) -> list[GfvgSetup]:
    """Alle Gitchi-FVG's (LONG en SHORT), gesorteerd op signaalcandle. choice = 'eerste' of 'laatste'."""
    if choice not in ("eerste", "laatste"):
        raise ValueError(choice)
    out = _setups_one_side(bars, 1, choice, L) + _setups_one_side(bars, -1, choice, L)
    return sorted(out, key=lambda s: (s.signal_index, s.direction))


def make_gfvg_plan(s: GfvgSetup, bars: pd.DataFrame, atr_series, validity: str, market: str,
                   tf: str = "15min") -> OrderPlan | None:
    """Orderplan volgens spec v0.4 §5. validity = 'ongeldig' (5 handelsdagen) of '24u'. None = geen TP."""
    if s.tp is None:
        return None
    step = pd.Timedelta(tf)
    t_sig = bars.index[s.signal_index] + step
    if validity == "24u":
        until = t_sig + pd.Timedelta(hours=24)
    else:
        until = bars.index[min(s.signal_index + VALID_BARS, len(bars) - 1)] + step
    if s.replaced_index is not None:
        until = min(until, bars.index[s.replaced_index] + step)
    a = float(np.asarray(atr_series)[s.fvg_index])
    return OrderPlan(s.direction, t_sig, "limit", s.anchor, a, s.entry, until, market=market,
                     max_cost_r=MAX_COST_R, tp_price=s.tp, cancel_price=s.tp)
