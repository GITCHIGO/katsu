"""
ICT Silver Bullet (docs/spec_v0.5.md).

Vensters in servertijd (New York + 7 u): London 10:00, NY AM 17:00, NY PM 21:00, telkens 60 minuten.
Per venster per dag hoogstens één setup: de eerste FVG (candle 2 en 3 in het venster, candle 3 gesloten vóór het einde)
die de filter haalt ('alle', 'sweep' of 'bias'). Entry = limiet op de rand van de FVG, geldig tot het einde van het
venster. SL-basis = extreme van het venster t/m candle 3. TP = eerste oude, ongeraakte swing voorbij de beweging,
maximaal 2R (geen: 2R).
Intern werkt alles in "LONG-ruimte" (SHORT = gespiegelde prijzen). Alleen gesloten candles.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from katsu.execution import OrderPlan
from katsu.structure import find_swings

WINDOWS = {"london": 10 * 60, "ny_am": 17 * 60, "ny_pm": 21 * 60}    # start in minuten servertijd
WINDOW_LEN = 60
L_STRUCT = 3
MAX_RR = 2.0
MAX_COST_R = 0.2
SL_BUFFER_ATR = 0.1


@dataclass(frozen=True)
class SbSetup:
    direction: str
    window: str
    k: int                  # candle 3 van de FVG
    window_start: int       # eerste candle van het venster
    window_end: pd.Timestamp
    entry: float
    anchor: float
    tp: float | None
    swept: bool


class _Side:
    """Arrays en swings in LONG-ruimte voor één richting."""
    def __init__(self, bars: pd.DataFrame, d: int, L: int):
        o, h, lo, c = (bars[x].to_numpy(float) for x in ("open", "high", "low", "close"))
        if d < 0:
            o, h, lo, c = -o, -lo, -h, -c
        self.d, self.h, self.lo = d, h, lo
        sw = find_swings(pd.DataFrame({"high": h, "low": lo}), L)
        hi = sorted((s for s in sw if s.kind == "HIGH"), key=lambda s: s.confirmed_at)
        lw = sorted((s for s in sw if s.kind == "LOW"), key=lambda s: s.confirmed_at)
        self.h_conf = np.array([s.confirmed_at for s in hi], dtype=int)
        self.h_idx = np.array([s.index for s in hi], dtype=int)
        self.h_price = np.array([s.price for s in hi], dtype=float)
        self.l_conf = np.array([s.confirmed_at for s in lw], dtype=int)
        self.l_price = np.array([s.price for s in lw], dtype=float)
        n = len(h)
        nxt = np.full(n, n, dtype=int)
        stack: list[int] = []
        for i in range(n):
            while stack and h[i] >= h[stack[-1]]:
                nxt[stack.pop()] = i
            stack.append(i)
        self.death = nxt[self.h_idx] if len(self.h_idx) else np.array([], dtype=int)

    def fvg(self, k):
        return self.lo[k] > self.h[k - 2]

    def swept(self, ws, k):
        q = int(np.searchsorted(self.l_conf, ws, side="right"))
        return q > 0 and self.lo[ws:k].min() < self.l_price[q - 1]            # venster-begin t/m candle 2

    def target(self, k, leg_high):
        q = int(np.searchsorted(self.h_conf, k, side="right"))
        ok = (self.death[:q] > k) & (self.h_price[:q] > leg_high)
        return float(self.h_price[:q][ok].min()) if ok.any() else None


def sb_setups(bars: pd.DataFrame, tf: str, mode: str, trend=None, windows=None, L: int = L_STRUCT) -> list[SbSetup]:
    """Silver Bullet-setups. mode = 'alle', 'sweep' of 'bias' (dan is `trend` = H1-trend per candle verplicht)."""
    if mode not in ("alle", "sweep", "bias"):
        raise ValueError(mode)
    windows = windows or list(WINDOWS)
    step = pd.Timedelta(tf)
    t = bars.index
    mins = np.asarray(t.hour * 60 + t.minute)
    day = np.asarray(t.normalize())
    sides = {1: _Side(bars, 1, L), -1: _Side(bars, -1, L)}
    out = []
    for w in windows:
        w0 = WINDOWS[w]
        inw = np.where((mins >= w0) & (mins < w0 + WINDOW_LEN))[0]
        if len(inw) == 0:
            continue
        starts = inw[np.r_[True, day[inw][1:] != day[inw][:-1]]]
        for ws in starts:
            wend = pd.Timestamp(day[ws]) + pd.Timedelta(minutes=w0 + WINDOW_LEN)
            k = ws + 1
            while k < len(t) and t[k] + step <= wend and day[k] == day[ws]:
                if k >= 2:
                    for d in (1, -1):
                        s = sides[d]
                        if not s.fvg(k):
                            continue
                        sw = s.swept(ws, k)
                        if mode == "sweep" and not sw:
                            continue
                        if mode == "bias" and trend[k] != ("UP" if d > 0 else "DOWN"):
                            continue
                        anchor = s.lo[ws:k + 1].min()
                        tp = s.target(k, s.h[ws:k + 1].max())
                        out.append(SbSetup("LONG" if d > 0 else "SHORT", w, int(k), int(ws), wend,
                                           float(d * s.lo[k]), float(d * anchor), None if tp is None else float(d * tp),
                                           bool(sw)))
                        break
                    else:
                        k += 1
                        continue
                    break                                   # één setup per venster per dag
                k += 1
    return sorted(out, key=lambda s: s.k)


def make_sb_plan(s: SbSetup, bars: pd.DataFrame, atr_values, market: str, tf: str) -> OrderPlan:
    """Limiet op de rand van de FVG, geldig tot het einde van het venster; TP oud niveau max 2R (geen: 2R)."""
    a = float(np.asarray(atr_values)[s.k])
    sgn = 1.0 if s.direction == "LONG" else -1.0
    risk = sgn * (s.entry - (s.anchor - sgn * SL_BUFFER_ATR * a))
    cap = s.entry + sgn * MAX_RR * risk
    cancel = cap if s.tp is None or sgn * (s.tp - cap) > 0 else s.tp
    return OrderPlan(s.direction, bars.index[s.k] + pd.Timedelta(tf), "limit", s.anchor, a, s.entry, s.window_end,
                     market=market, max_cost_r=MAX_COST_R, tp_price=s.tp,
                     cancel_price=cancel, max_rr=MAX_RR if s.tp is not None else None)
