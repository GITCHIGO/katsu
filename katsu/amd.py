"""
AMD / Power of 3 (docs/spec_v0.6.md).

Tijden in servertijd (New York + 7 u). Per markt per dag hoogstens één setup:
Azië-range 02:00–06:45, midnight open = open van 07:00, manipulatievenster 07:00–11:45.
Long: sweep onder Azië-low én onder de midnight open, daarna bevestiging (C1 close terug boven de Azië-low,
C2 close terug boven de midnight open). Short gespiegeld. Entry markt (E1) of limiet 38,2% diep in de laatste FVG van
de terugkeer (E2). SL-basis = manipulatie-extreem. TP = overkant van de Azië-range. Exit uiterlijk op de dagclose.
Alleen gesloten candles: de bevestiging is bekend op het einde van haar candle; de order vertrekt pas daarna.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from katsu.execution import OrderPlan

ASIA_START, ASIA_END = 2 * 60, 7 * 60          # minuten servertijd, einde exclusief
MO_MIN = 7 * 60
WIN_END = 12 * 60                              # manipulatievenster 07:00–11:45 (einde exclusief)
LIMIT_END = 18 * 60                            # E2-limiet geldig tot 18:00 server (NY 11:00)
MIN_ASIA_BARS = 16
STEP = pd.Timedelta("15min")


@dataclass(frozen=True)
class AmdSetup:
    direction: str          # "LONG" / "SHORT"
    day: pd.Timestamp       # serverdatum
    k_sweep: int            # eerste candle van de sweep (van de kant die bevestigd werd)
    k_conf: int             # bevestigingscandle
    k_ext: int              # candle van het manipulatie-extreem
    asia_hi: float
    asia_lo: float
    mo: float
    anchor: float           # manipulatie-extreem (SL-basis)
    tp: float               # overkant van de Azië-range
    entry: float | None     # E2: limietprijs; E1: None (markt)
    fvg: tuple | None       # E2: (c1, c3, onder, boven)


def _fvg_entry(h, lo, a, b, long, frac):
    """Laatste FVG in de richting met c1 >= a en c3 <= b. Geeft (c1, c3, onder, boven, entry) of None."""
    for c3 in range(b, a + 1, -1):
        c1 = c3 - 2
        if c1 < a:
            break
        if long and lo[c3] > h[c1]:
            bottom, top = h[c1], lo[c3]
            return c1, c3, bottom, top, top - frac * (top - bottom)
        if not long and h[c3] < lo[c1]:
            bottom, top = h[c3], lo[c1]
            return c1, c3, bottom, top, bottom + frac * (top - bottom)
    return None


def amd_setups(bars: pd.DataFrame, confirm: str = "open", entry: str = "market", frac: float = 0.382,
               trend: np.ndarray | None = None, day_mask=None) -> list[AmdSetup]:
    """
    confirm: "range" (C1) of "open" (C2). entry: "market" (E1) of "fvg" (E2).
    trend: optioneel array UP/DOWN/NEUTRAL per candle (D1-trend op het einde van de candle); dan alleen 'mee'.
    day_mask: optioneel functie(DatetimeIndex) -> bool-array; alleen dagen waarvan de 07:00-candle True geeft.
    """
    if confirm not in ("range", "open") or entry not in ("market", "fvg"):
        raise ValueError("onbekende variant")
    idx = bars.index
    o, h, lo, c = (bars[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    mins = (idx.hour * 60 + idx.minute).to_numpy()
    days = idx.normalize()
    out: list[AmdSetup] = []
    # grenzen per dag
    starts = np.flatnonzero(np.r_[True, days[1:] != days[:-1]])
    ends = np.r_[starts[1:], len(idx)]
    for s0, e0 in zip(starts, ends):
        m = mins[s0:e0]
        asia = np.flatnonzero((m >= ASIA_START) & (m < ASIA_END)) + s0
        mo_k = np.flatnonzero(m == MO_MIN)
        win = np.flatnonzero((m >= MO_MIN) & (m < WIN_END)) + s0
        if len(asia) < MIN_ASIA_BARS or len(mo_k) == 0 or len(win) == 0:
            continue
        k_mo = int(mo_k[0]) + s0
        if day_mask is not None and not bool(day_mask(idx[[k_mo]])[0]):
            continue
        a_hi, a_lo, mo = float(h[asia].max()), float(lo[asia].min()), float(o[k_mo])
        sweep_l = sweep_s = None
        found = None
        for k in win:
            if sweep_l is None and lo[k] < a_lo and lo[k] < mo:
                sweep_l = k
            if sweep_s is None and h[k] > a_hi and h[k] > mo:
                sweep_s = k
            ok_l = sweep_l is not None and (c[k] > (a_lo if confirm == "range" else mo))
            ok_s = sweep_s is not None and (c[k] < (a_hi if confirm == "range" else mo))
            if ok_l and ok_s:
                found = "beide"
                break
            if ok_l or ok_s:
                found = ("LONG", sweep_l) if ok_l else ("SHORT", sweep_s)
                k_conf = k
                break
        if found is None or found == "beide":
            continue
        d, k_sw = found
        long = d == "LONG"
        if trend is not None and trend[k_conf] != ("UP" if long else "DOWN"):
            continue
        seg = np.arange(win[0], k_conf + 1)
        k_ext = int(seg[np.argmin(lo[seg])] if long else seg[np.argmax(h[seg])])
        anchor = float(lo[k_ext] if long else h[k_ext])
        tp = a_hi if long else a_lo
        ent, fvg = None, None
        if entry == "fvg":
            r = _fvg_entry(h, lo, k_ext, k_conf, long, frac)
            if r is None:
                continue
            fvg, ent = r[:4], float(r[4])
        out.append(AmdSetup(d, days[k_mo], int(k_sw), int(k_conf), k_ext, a_hi, a_lo, mo, anchor, float(tp), ent, fvg))
    return out


def amd_day_map(setups: list[AmdSetup], bars: pd.DataFrame) -> dict:
    """Per serverdag: (richting +1/−1, moment waarop de bevestiging bekend is = einde bevestigingscandle)."""
    return {s.day: (1 if s.direction == "LONG" else -1, bars.index[s.k_conf] + STEP) for s in setups}


def amd_day_labels(t_sig: pd.DatetimeIndex, d: np.ndarray, day_map: dict) -> np.ndarray:
    """
    Kenmerk 'AMD-dag' voor andere setups: was er op dezelfde serverdag vóór (of op) het signaal al een bevestigde
    AMD-beweging? 'mee' (zelfde richting), 'tegen', of 'geen'. Signaal = einde van de signaalcandle.
    """
    t_sig = pd.DatetimeIndex(t_sig)
    day = (t_sig - pd.Timedelta(minutes=1)).normalize()
    out = np.full(len(t_sig), "geen", dtype=object)
    for i, (dy, t) in enumerate(zip(day, t_sig)):
        v = day_map.get(dy)
        if v is not None and v[1] <= t:
            out[i] = "mee" if v[0] == d[i] else "tegen"
    return out


def make_amd_plan(s: AmdSetup, bars: pd.DataFrame, atr_values: np.ndarray, market: str) -> OrderPlan:
    t_sig = bars.index[s.k_conf] + STEP                       # einde van de bevestigingscandle
    a = float(atr_values[s.k_conf])
    if s.entry is None:
        return OrderPlan(s.direction, t_sig, "market", s.anchor, a, market=market, tp_price=s.tp)
    valid = s.day + pd.Timedelta(minutes=LIMIT_END)
    return OrderPlan(s.direction, t_sig, "limit", s.anchor, a, s.entry, valid, market=market,
                     tp_price=s.tp, cancel_price=s.tp)
