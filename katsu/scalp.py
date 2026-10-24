"""
Spec v0.8 (docs/spec_v0.8.md): intraday-varianten met vector candles (tick-volume), ADR en ronde getallen.

Alleen gesloten M5-candles: een signaal op candle k is bekend bij de close van k (= start k + 5 min) en de order
vertrekt vanaf dat moment. Alles wat hier berekend wordt, gebruikt alleen candles t/m k (geen vooruitkijken).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from katsu.execution import OrderPlan
from katsu.structure import atr

M5 = pd.Timedelta(minutes=5)
SESSION = (9 * 60, 22 * 60)          # signalen 08:00–21:00 Belgisch = 09:00–22:00 server (close-tijd van de M5)
CLOSE_AT_MIN = 23 * 60 + 45           # 22:45 Belgisch = 23:45 server: alles dicht, orders vervallen


@dataclass(frozen=True)
class Params:
    """Afstanden in prijs per markt (spec v0.8 §2 en §2b)."""
    step: float          # rond niveau
    near_lo: float       # V3: minimaal zo ver onder/boven L
    near_hi: float       # V3: maximaal zo ver
    far: float           # V3: koers kwam van minstens zo ver
    offset: float        # V3: limiet zoveel vóór het niveau
    sl: float            # V3/V4: SL zoveel voorbij het niveau; ook de minimale SL voor alle varianten
    brk: float           # V4: close zoveel voorbij het niveau


PARAMS = {
    "EURUSD": Params(step=0.0050, near_lo=0.0002, near_hi=0.0010, far=0.0015, offset=0.0001, sl=0.0006, brk=0.0002),
    "XAUUSD": Params(step=10.0, near_lo=0.60, near_hi=3.00, far=5.00, offset=0.30, sl=2.50, brk=0.60),
}
RR, MIN_RR, ADR_N, ADR_FILTER = 1.5, 1.0, 14, 0.9


def to_m5(m1: pd.DataFrame) -> pd.DataFrame:
    """M5-candles uit M1 (label = start). Alleen tijdvakken met data. Tick-volume opgeteld."""
    g = m1.resample("5min", label="left", closed="left")
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(), "low": g["low"].min(),
                        "close": g["close"].last(), "tickvol": g["tickvol"].sum()})
    return out.dropna(subset=["open"])


def vectors(m5: pd.DataFrame) -> np.ndarray:
    """Climax-vector (Traders Reality): volume ≥ 2 × gemiddelde van de 10 vorige candles, of range × volume ≥ het
    hoogste van de 10 vorige. +1 = bull (close > open), −1 = bear, 0 = geen."""
    v = m5["tickvol"].astype(float)
    rv = (m5["high"] - m5["low"]) * v
    avg = v.shift(1).rolling(10).mean()
    mx = rv.shift(1).rolling(10).max()
    climax = ((v >= 2 * avg) | (rv >= mx)) & avg.notna()
    direction = np.sign(m5["close"] - m5["open"]).to_numpy()
    return np.where(climax.to_numpy(), direction, 0).astype(int)


def adr_series(m1: pd.DataFrame, n: int = ADR_N) -> pd.Series:
    """ADR per serverdag = gemiddelde (high − low) van de n vorige serverdagen (zondag niet meegeteld)."""
    day = m1.index.normalize()
    d = m1.groupby(day).agg(high=("high", "max"), low=("low", "min"))
    d = d[d.index.dayofweek != 6]
    return (d["high"] - d["low"]).shift(1).rolling(n).mean()


def features(m1: pd.DataFrame) -> pd.DataFrame:
    """M5 met ATR, vector, ADR van de dag, en dag-high/low t/m die candle."""
    m5 = to_m5(m1)
    m5["atr"] = atr(m5, 14)
    m5["vec"] = vectors(m5)
    day = m5.index.normalize()
    m5["day"] = day
    adr = adr_series(m1)
    m5["adr"] = adr.reindex(day).to_numpy()
    m5["dhi"] = m5.groupby("day")["high"].cummax()
    m5["dlo"] = m5.groupby("day")["low"].cummin()
    m5["t_close"] = m5.index + M5
    mins = m5["t_close"].dt.hour * 60 + m5["t_close"].dt.minute
    m5["in_session"] = (mins >= SESSION[0]) & (mins <= SESSION[1]) & (m5.index.dayofweek < 5)
    return m5


def _adr_blocks(direction: int, close: float, dhi: float, dlo: float, adr: float) -> bool:
    """ADR-filter: geen long als de koers ≥ 90% ADR boven de dag-low staat (spiegel voor short)."""
    return (close - dlo >= ADR_FILTER * adr) if direction > 0 else (dhi - close >= ADR_FILTER * adr)


def _tp_level(direction: int, dhi: float, dlo: float, adr: float) -> float:
    """ADR-high (long) of ADR-low (short), berekend op het signaal."""
    return dlo + adr if direction > 0 else dhi - adr


def _plan(direction, t, kind, anchor, atr_v, mkt, p, entry, valid_bars, tp_lvl):
    dirn = "LONG" if direction > 0 else "SHORT"
    valid = t + valid_bars * M5 if kind != "market" else None
    # geplande TP (voor annuleren als die eerst geraakt wordt), op basis van de geplande entry, zonder spread
    cancel = None
    if kind != "market":
        risk = max(abs(entry - anchor) + 0.1 * atr_v, p.sl)
        cancel = min(tp_lvl, entry + RR * risk) if direction > 0 else max(tp_lvl, entry - RR * risk)
    return OrderPlan(dirn, t, kind, float(anchor), float(atr_v), None if entry is None else float(entry), valid,
                     market=mkt, tp_price=float(tp_lvl), cancel_price=None if cancel is None else float(cancel),
                     max_rr=RR, min_risk=p.sl, min_rr=MIN_RR)


def signals(f: pd.DataFrame, mkt: str, allow: np.ndarray | None = None) -> dict:
    """Orderplannen per variant {"V1": [...], ...}. allow = masker op de M5-candles (periode); None = alles."""
    p = PARAMS[mkt]
    o, h, l, c = (f[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    a, vec, adr = f["atr"].to_numpy(float), f["vec"].to_numpy(int), f["adr"].to_numpy(float)
    dhi, dlo, day = f["dhi"].to_numpy(float), f["dlo"].to_numpy(float), f["day"].to_numpy()
    tc, sess = f["t_close"].to_numpy(), f["in_session"].to_numpy(bool)
    ok = sess & np.isfinite(a) & np.isfinite(adr)
    if allow is not None:
        ok &= allow
    out = {"V1": [], "V2": [], "V3": [], "V4": []}
    v3_done, v4_done = set(), set()
    n = len(f)
    for k in range(12, n):
        # ---- V4: doorbraak door een rond niveau (marktorder op de volgende open) ----
        # Elke doorbraak telt mee voor "de eerste close voorbij L vandaag", ook buiten de sessie of de periode;
        # alleen binnen de sessie en de periode wordt er een order van gemaakt.
        if day[k] == day[k - 1] and np.isfinite(adr[k]):
            for d, lvl in ((1, np.floor((c[k] - p.brk) / p.step) * p.step),      # hoogste L met c ≥ L + brk
                           (-1, np.ceil((c[k] + p.brk) / p.step) * p.step)):     # laagste L met c ≤ L − brk
                crossed = lvl > c[k - 1] if d > 0 else lvl < c[k - 1]
                key = (day[k], round(lvl / p.step), d)
                if not crossed or key in v4_done:
                    continue
                v4_done.add(key)
                if ok[k] and not _adr_blocks(d, c[k], dhi[k], dlo[k], adr[k]):
                    out["V4"].append(_plan(d, pd.Timestamp(tc[k]), "market", lvl - d * p.sl, 0.0, mkt, p, None, 0,
                                           _tp_level(d, dhi[k], dlo[k], adr[k])))
        if not ok[k]:
            continue
        t = pd.Timestamp(tc[k])
        # ---- V1: vector-recovery (mee met de vector), body ≥ 1 ATR ----
        if vec[k] != 0 and abs(c[k] - o[k]) >= a[k]:
            d = vec[k]
            if not _adr_blocks(d, c[k], dhi[k], dlo[k], adr[k]):
                anchor = l[k] if d > 0 else h[k]
                out["V1"].append(_plan(d, t, "limit", anchor, a[k], mkt, p, (o[k] + c[k]) / 2, 24,
                                       _tp_level(d, dhi[k], dlo[k], adr[k])))
        # ---- V2: vector aan het ADR-uiterste -> ommekeer met stoporder ----
        if vec[k] != 0 and dhi[k] - dlo[k] >= ADR_FILTER * adr[k]:
            if vec[k] > 0 and h[k] >= dhi[k]:          # bull-vector maakt nieuwe dag-high -> short
                out["V2"].append(_plan(-1, t, "stop", h[k], a[k], mkt, p, (o[k] + c[k]) / 2, 12,
                                       _tp_level(-1, dhi[k], dlo[k], adr[k])))
            elif vec[k] < 0 and l[k] <= dlo[k]:        # bear-vector maakt nieuwe dag-low -> long
                out["V2"].append(_plan(1, t, "stop", l[k], a[k], mkt, p, (o[k] + c[k]) / 2, 12,
                                       _tp_level(1, dhi[k], dlo[k], adr[k])))
        # ---- V3: kering aan een rond niveau (limiet vóór het niveau) ----
        up = np.ceil(c[k] / p.step) * p.step            # niveau boven -> short
        if up - c[k] < 1e-9:
            up += p.step
        dn = np.floor(c[k] / p.step) * p.step           # niveau onder -> long
        if c[k] - dn < 1e-9:
            dn -= p.step
        lo12, hi12 = l[k - 11:k + 1].min(), h[k - 11:k + 1].max()
        key = (day[k], round(up / p.step), -1)
        if (p.near_lo <= up - c[k] <= p.near_hi and lo12 <= up - p.far and dhi[k] < up and key not in v3_done
                and not _adr_blocks(-1, c[k], dhi[k], dlo[k], adr[k])):
            v3_done.add(key)
            out["V3"].append(_plan(-1, t, "limit", up + p.sl, 0.0, mkt, p, up - p.offset, 12,
                                   _tp_level(-1, dhi[k], dlo[k], adr[k])))
        key = (day[k], round(dn / p.step), 1)
        if (p.near_lo <= c[k] - dn <= p.near_hi and hi12 >= dn + p.far and dlo[k] > dn and key not in v3_done
                and not _adr_blocks(1, c[k], dhi[k], dlo[k], adr[k])):
            v3_done.add(key)
            out["V3"].append(_plan(1, t, "limit", dn - p.sl, 0.0, mkt, p, dn + p.offset, 12,
                                   _tp_level(1, dhi[k], dlo[k], adr[k])))
    return out.dropna(subset=["open"])


def vectors(m5: pd.DataFrame) -> np.ndarray:
    """Climax-vector (Traders Reality): volume ≥ 2 × gemiddelde van de 10 vorige candles, of range × volume ≥ het
    hoogste van de 10 vorige. +1 = bull (close > open), −1 = bear, 0 = geen."""
    v = m5["tickvol"].astype(float)
    rv = (m5["high"] - m5["low"]) * v
    avg = v.shift(1).rolling(10).mean()
    mx = rv.shift(1).rolling(10).max()
    climax = ((v >= 2 * avg) | (rv >= mx)) & avg.notna()
    direction = np.sign(m5["close"] - m5["open"]).to_numpy()
    return np.where(climax.to_numpy(), direction, 0).astype(int)


def adr_series(m1: pd.DataFrame, n: int = ADR_N) -> pd.Series:
    """ADR per serverdag = gemiddelde (high − low) van de n vorige serverdagen (zondag niet meegeteld)."""
    day = m1.index.normalize()
    d = m1.groupby(day).agg(high=("high", "max"), low=("low", "min"))
    d = d[d.index.dayofweek != 6]
    return (d["high"] - d["low"]).shift(1).rolling(n).mean()


def features(m1: pd.DataFrame) -> pd.DataFrame:
    """M5 met ATR, vector, ADR van de dag, en dag-high/low t/m die candle."""
    m5 = to_m5(m1)
    m5["atr"] = atr(m5, 14)
    m5["vec"] = vectors(m5)
    day = m5.index.normalize()
    m5["day"] = day
    adr = adr_series(m1)
    m5["adr"] = adr.reindex(day).to_numpy()
    m5["dhi"] = m5.groupby("day")["high"].cummax()
    m5["dlo"] = m5.groupby("day")["low"].cummin()
    m5["t_close"] = m5.index + M5
    mins = m5["t_close"].dt.hour * 60 + m5["t_close"].dt.minute
    m5["in_session"] = (mins >= SESSION[0]) & (mins <= SESSION[1]) & (m5.index.dayofweek < 5)
    return m5


def _adr_blocks(direction: int, close: float, dhi: float, dlo: float, adr: float) -> bool:
    """ADR-filter: geen long als de koers ≥ 90% ADR boven de dag-low staat (spiegel voor short)."""
    return (close - dlo >= ADR_FILTER * adr) if direction > 0 else (dhi - close >= ADR_FILTER * adr)


def _tp_level(direction: int, dhi: float, dlo: float, adr: float) -> float:
    """ADR-high (long) of ADR-low (short), berekend op het signaal."""
    return dlo + adr if direction > 0 else dhi - adr


def _plan(direction, t, kind, anchor, atr_v, mkt, p, entry, valid_bars, tp_lvl):
    dirn = "LONG" if direction > 0 else "SHORT"
    valid = t + valid_bars * M5 if kind != "market" else None
    # geplande TP (voor annuleren als die eerst geraakt wordt), op basis van de geplande entry, zonder spread
    cancel = None
    if kind != "market":
        risk = max(abs(entry - anchor) + 0.1 * atr_v, p.sl)
        cancel = min(tp_lvl, entry + RR * risk) if direction > 0 else max(tp_lvl, entry - RR * risk)
    return OrderPlan(dirn, t, kind, float(anchor), float(atr_v), None if entry is None else float(entry), valid,
                     market=mkt, tp_price=float(tp_lvl), cancel_price=None if cancel is None else float(cancel),
                     max_rr=RR, min_risk=p.sl, min_rr=MIN_RR)


def signals(f: pd.DataFrame, mkt: str, allow: np.ndarray | None = None) -> dict:
    """Orderplannen per variant {"V1": [...], ...}. allow = masker op de M5-candles (periode); None = alles."""
    p = PARAMS[mkt]
    o, h, l, c = (f[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    a, vec, adr = f["atr"].to_numpy(float), f["vec"].to_numpy(int), f["adr"].to_numpy(float)
    dhi, dlo, day = f["dhi"].to_numpy(float), f["dlo"].to_numpy(float), f["day"].to_numpy()
    tc, sess = f["t_close"].to_numpy(), f["in_session"].to_numpy(bool)
    ok = sess & np.isfinite(a) & np.isfinite(adr)
    if allow is not None:
        ok &= allow
    out = {"V1": [], "V2": [], "V3": [], "V4": []}
    v3_done, v4_done = set(), set()
    n = len(f)
    for k in range(12, n):
        # ---- V4: doorbraak door een rond niveau (marktorder op de volgende open) ----
        # Elke doorbraak telt mee voor "de eerste close voorbij L vandaag", ook buiten de sessie of de periode;
        # alleen binnen de sessie en de periode wordt er een order van gemaakt.
        if day[k] == day[k - 1] and np.isfinite(adr[k]):
            for d, lvl in ((1, np.floor((c[k] - p.brk) / p.step) * p.step),      # hoogste L met c ≥ L + brk
                           (-1, np.ceil((c[k] + p.brk) / p.step) * p.step)):     # laagste L met c ≤ L − brk
                crossed = lvl > c[k - 1] if d > 0 else lvl < c[k - 1]
                key = (day[k], round(lvl / p.step), d)
                if not crossed or key in v4_done:
                    continue
                v4_done.add(key)
                if ok[k] and not _adr_blocks(d, c[k], dhi[k], dlo[k], adr[k]):
                    out["V4"].append(_plan(d, pd.Timestamp(tc[k]), "market", lvl - d * p.sl, 0.0, mkt, p, None, 0,
                                           _tp_level(d, dhi[k], dlo[k], adr[k])))
        if not ok[k]:
            continue
        t = pd.Timestamp(tc[k])
        # ---- V1: vector-recovery (mee met de vector), body ≥ 1 ATR ----
        if vec[k] != 0 and abs(c[k] - o[k]) >= a[k]:
            d = vec[k]
            if not _adr_blocks(d, c[k], dhi[k], dlo[k], adr[k]):
                anchor = l[k] if d > 0 else h[k]
                out["V1"].append(_plan(d, t, "limit", anchor, a[k], mkt, p, (o[k] + c[k]) / 2, 24,
                                       _tp_level(d, dhi[k], dlo[k], adr[k])))
        # ---- V2: vector aan het ADR-uiterste -> ommekeer met stoporder ----
        if vec[k] != 0 and dhi[k] - dlo[k] >= ADR_FILTER * adr[k]:
            if vec[k] > 0 and h[k] >= dhi[k]:          # bull-vector maakt nieuwe dag-high -> short
                out["V2"].append(_plan(-1, t, "stop", h[k], a[k], mkt, p, (o[k] + c[k]) / 2, 12,
                                       _tp_level(-1, dhi[k], dlo[k], adr[k])))
            elif vec[k] < 0 and l[k] <= dlo[k]:        # bear-vector maakt nieuwe dag-low -> long
                out["V2"].append(_plan(1, t, "stop", l[k], a[k], mkt, p, (o[k] + c[k]) / 2, 12,
                                       _tp_level(1, dhi[k], dlo[k], adr[k])))
        # ---- V3: kering aan een rond niveau (limiet vóór het niveau) ----
        up = np.ceil(c[k] / p.step) * p.step            # niveau boven -> short
        if up - c[k] < 1e-9:
            up += p.step
        dn = np.floor(c[k] / p.step) * p.step           # niveau onder -> long
        if c[k] - dn < 1e-9:
            dn -= p.step
        lo12, hi12 = l[k - 11:k + 1].min(), h[k - 11:k + 1].max()
        key = (day[k], round(up / p.step), -1)
        if (p.near_lo <= up - c[k] <= p.near_hi and lo12 <= up - p.far and dhi[k] < up and key not in v3_done
                and not _adr_blocks(-1, c[k], dhi[k], dlo[k], adr[k])):
            v3_done.add(key)
            out["V3"].append(_plan(-1, t, "limit", up + p.sl, 0.0, mkt, p, up - p.offset, 12,
                                   _tp_level(-1, dhi[k], dlo[k], adr[k])))
        key = (day[k], round(dn / p.step), 1)
        if (p.near_lo <= c[k] - dn <= p.near_hi and hi12 >= dn + p.far and dlo[k] > dn and key not in v3_done
                and not _adr_blocks(1, c[k], dhi[k], dlo[k], adr[k])):
            v3_done.add(key)
            out["V3"].append(_plan(1, t, "limit", dn - p.sl, 0.0, mkt, p, dn + p.offset, 12,
                                   _tp_level(1, dhi[k], dlo[k], adr[k])))
        # ---- V4: doorbraak door een rond niveau (marktorder op de volgende open) ----
        if day[k] == day[k - 1]:
            lvl_up = np.floor((c[k] - p.brk) / p.step) * p.step      # hoogste niveau met c ≥ L + brk
            if lvl_up > c[k - 1]:
                key = (day[k], round(lvl_up / p.step), 1)
                if key not in v4_done:
                    v4_done.add(key)
                    if not _adr_blocks(1, c[k], dhi[k], dlo[k], adr[k]):
                        out["V4"].append(_plan(1, t, "market", lvl_up - p.sl, 0.0, mkt, p, None, 0,
                                               _tp_level(1, dhi[k], dlo[k], adr[k])))
            lvl_dn = np.ceil((c[k] + p.brk) / p.step) * p.step       # laagste niveau met c ≤ L − brk
            if lvl_dn < c[k - 1]:
                key = (day[k], round(lvl_dn / p.step), -1)
                if key not in v4_done:
                    v4_done.add(key)
                    if not _adr_blocks(-1, c[k], dhi[k], dlo[k], adr[k]):
                        out["V4"].append(_plan(-1, t, "market", lvl_dn + p.sl, 0.0, mkt, p, None, 0,
                                               _tp_level(-1, dhi[k], dlo[k], adr[k])))
    return out
