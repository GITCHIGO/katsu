"""
Ronde 2, deel A: ICT-tijdmodellen uit het boek (docs/onderzoeksplan_edge.md §11).

Servertijd van IC Markets = New York + 7 uur (het hele jaar). Alle vensters hieronder in servertijd:
  Azië-range        03:00–07:00   (20:00–00:00 NY)
  midnight open     07:00         (00:00 NY)
  London-range      09:00–12:00   (02:00–05:00 NY)
  Silver Bullet     sweep 16:30–17:00, FVG 17:00–18:00   (09:30–10:00 en 10:00–11:00 NY)
  London close      17:00         (10:00 NY)
  einde handelsdag  23:00         (16:00 NY)
Alle detectors werken op M15-candles en gebruiken alleen candles die op het signaalmoment gesloten zijn.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ASIA = (3 * 60, 7 * 60)
MNO = 7 * 60
LONDON = (9 * 60, 12 * 60)
SB_SWEEP = (16 * 60 + 30, 17 * 60)
SB_FVG = (17 * 60, 18 * 60)
LC = 17 * 60
DAY_END = 23 * 60


def _minutes(idx: pd.DatetimeIndex) -> np.ndarray:
    return np.asarray(idx.hour * 60 + idx.minute)


# ---------------- Dagniveaus en dagbias ----------------

def day_levels(m15: pd.DataFrame) -> pd.DataFrame:
    """
    Per serverdatum: Azië- en London-range, midnight open, dag-high/low/close, ADR5 en de dagbias.
    Dagbias (boek H12): gisteren boven de high van eergisteren maar eronder gesloten -> -1 (SHORT);
    gisteren onder de low van eergisteren maar erboven gesloten -> +1 (LONG); beide of geen -> 0.
    """
    t = m15.index
    mins = _minutes(t)
    date = t.normalize()
    df = pd.DataFrame({"h": m15.high.to_numpy(), "l": m15.low.to_numpy(), "o": m15.open.to_numpy(),
                       "c": m15.close.to_numpy(), "date": date, "m": mins})
    g = df.groupby("date")
    out = pd.DataFrame({"d_high": g.h.max(), "d_low": g.l.min(), "d_close": g.c.last()})
    asia = df[(df.m >= ASIA[0]) & (df.m < ASIA[1])].groupby("date")
    out["asia_h"], out["asia_l"] = asia.h.max(), asia.l.min()
    lon = df[(df.m >= LONDON[0]) & (df.m < LONDON[1])].groupby("date")
    out["london_h"], out["london_l"] = lon.h.max(), lon.l.min()
    out["mno"] = df[df.m == MNO].groupby("date").o.first()
    rng = out.d_high - out.d_low
    out["adr5"] = rng.shift(1).rolling(5).mean()
    h1, h2, l1, l2, c1 = (out.d_high.shift(1), out.d_high.shift(2), out.d_low.shift(1),
                          out.d_low.shift(2), out.d_close.shift(1))
    short = (h1 > h2) & (c1 < h2)
    long_ = (l1 < l2) & (c1 > l2)
    out["bias"] = np.where(short & ~long_, -1, np.where(long_ & ~short, 1, 0))
    out["prev_high"], out["prev_low"] = h1, l1
    return out


def _exit_bars(t: pd.DatetimeIndex) -> np.ndarray:
    """Per candle: index van de laatste candle van dezelfde serverdag die vóór 23:00 begint."""
    mins = _minutes(t)
    date = np.asarray(t.normalize())
    idx = np.arange(len(t))
    ok = mins < DAY_END
    s = pd.Series(np.where(ok, idx, -1)).groupby(date).transform("max").to_numpy()
    return s


# ---------------- Gebeurtenissen ----------------
# Elke detector geeft een DataFrame met: k (signaalcandle), d (+1/-1), anchor (SL-basis zonder buffer),
# exit_bar (laatste candle), eventueel limit (limietprijs) en valid_bar (laatste candle waarop de
# limiet mag vullen), plus variant-kolommen.

def judas_events(m15: pd.DataFrame, lv: pd.DataFrame) -> pd.DataFrame:
    """London Judas: in 09:00–12:00 de eerste candle die door de Azië-low prikt en erboven sluit -> LONG
    (spiegel SHORT). Sluit een candle eerst onder de Azië-low, dan is die kant vervallen (run)."""
    t = m15.index; mins = _minutes(t); dates = t.normalize()
    h, lo, c = m15.high.to_numpy(), m15.low.to_numpy(), m15.close.to_numpy()
    exitb = _exit_bars(t)
    out = []
    win = np.where((mins >= LONDON[0]) & (mins < LONDON[1]))[0]
    by_day = pd.Series(win).groupby(np.asarray(dates[win])).apply(list)
    for day, ks in by_day.items():
        if day not in lv.index or np.isnan(lv.at[day, "asia_l"]):
            continue
        al, ah = lv.at[day, "asia_l"], lv.at[day, "asia_h"]
        done_l = done_h = False
        for k in ks:
            if not done_l:
                if c[k] < al:
                    done_l = True
                elif lo[k] < al:
                    out.append((k, 1, lo[k], exitb[k])); done_l = True
            if not done_h:
                if c[k] > ah:
                    done_h = True
                elif h[k] > ah:
                    out.append((k, -1, h[k], exitb[k])); done_h = True
    return pd.DataFrame(out, columns=["k", "d", "anchor", "exit_bar"])


def silver_bullet_events(m15: pd.DataFrame, lv: pd.DataFrame) -> pd.DataFrame:
    """
    Silver Bullet: sweep van de London-high/low tussen 16:30 en 17:00 (wick erdoor, close terug), daarna
    de eerste M15-FVG in de tegenrichting met derde candle tussen 17:00 en 17:45 -> limiet op het midden,
    geldig t/m de candle van 17:45. SL-basis = extreme sinds de sweep.
    """
    t = m15.index; mins = _minutes(t); dates = np.asarray(t.normalize())
    h, lo, c = m15.high.to_numpy(), m15.low.to_numpy(), m15.close.to_numpy()
    exitb = _exit_bars(t)
    out = []
    sweep_idx = np.where((mins >= SB_SWEEP[0]) & (mins < SB_SWEEP[1]))[0]
    for day in pd.unique(dates[sweep_idx]):
        if day not in lv.index or np.isnan(lv.at[day, "london_l"]):
            continue
        ll, lh = lv.at[day, "london_l"], lv.at[day, "london_h"]
        ks = sweep_idx[dates[sweep_idx] == day]
        for d in (1, -1):
            sw = [k for k in ks if (d > 0 and lo[k] < ll and c[k] > ll) or (d < 0 and h[k] > lh and c[k] < lh)]
            if not sw:
                continue
            s = sw[0]
            fvg = [j for j in range(s + 1, min(s + 8, len(c)))
                   if dates[j] == day and SB_FVG[0] <= mins[j] < SB_FVG[1] and j >= 2 and
                   ((d > 0 and lo[j] > h[j - 2]) or (d < 0 and h[j] < lo[j - 2]))]
            if not fvg:
                continue
            j = fvg[0]
            ce = (lo[j] + h[j - 2]) / 2 if d > 0 else (h[j] + lo[j - 2]) / 2
            anchor = lo[s:j + 1].min() if d > 0 else h[s:j + 1].max()
            last = max(q for q in range(j, min(j + 8, len(c))) if dates[q] == day and mins[q] < SB_FVG[1])
            out.append((j, d, anchor, exitb[j], ce, last))
    return pd.DataFrame(out, columns=["k", "d", "anchor", "exit_bar", "limit", "valid_bar"])


def monday_events(m15: pd.DataFrame) -> pd.DataFrame:
    """Di–vr: de eerste M15-candle die boven de maandag-high prikt en eronder sluit -> SHORT (spiegel LONG).
    Een close voorbij het niveau maakt die kant voor de week ongeldig."""
    t = m15.index; dow = np.asarray(t.dayofweek)
    h, lo, c = m15.high.to_numpy(), m15.low.to_numpy(), m15.close.to_numpy()
    week = np.asarray((t - pd.to_timedelta(t.dayofweek, unit="D")).normalize())
    exitb = _exit_bars(t)
    out = []
    for wk in pd.unique(week):
        sel = np.where(week == wk)[0]
        mon = sel[dow[sel] == 0]
        if len(mon) == 0:
            continue
        mh, ml = h[mon].max(), lo[mon].min()
        done_h = done_l = False
        for k in sel[dow[sel] >= 1]:
            if not done_h:
                if c[k] > mh:
                    done_h = True
                elif h[k] > mh:
                    out.append((k, -1, h[k], exitb[k])); done_h = True
            if not done_l:
                if c[k] < ml:
                    done_l = True
                elif lo[k] < ml:
                    out.append((k, 1, lo[k], exitb[k])); done_l = True
    return pd.DataFrame(out, columns=["k", "d", "anchor", "exit_bar"]).sort_values("k").reset_index(drop=True)


def bias_events(m15: pd.DataFrame, lv: pd.DataFrame) -> pd.DataFrame:
    """Dagbias als trade: instap op de midnight open (open van de 07:00-candle) in de richting van de bias;
    SL-basis = high van gisteren (SHORT) / low van gisteren (LONG). k = de candle vóór 07:00."""
    t = m15.index; mins = _minutes(t); dates = np.asarray(t.normalize())
    exitb = _exit_bars(t)
    out = []
    for e in np.where(mins == MNO)[0]:
        day = dates[e]
        if e == 0 or day not in lv.index:
            continue
        b = lv.at[day, "bias"]
        if b == 0:
            continue
        anchor = lv.at[day, "prev_high"] if b < 0 else lv.at[day, "prev_low"]
        out.append((e - 1, int(b), anchor, exitb[e]))
    return pd.DataFrame(out, columns=["k", "d", "anchor", "exit_bar"])


def london_close_events(m15: pd.DataFrame, lv: pd.DataFrame) -> pd.DataFrame:
    """Om 17:00 (10:00 NY): is de range sinds de midnight open groter dan ADR5, fade dan de dagrichting
    op de open van de 17:00-candle. SL-basis = extreme van de dag in de richting van de beweging."""
    t = m15.index; mins = _minutes(t); dates = np.asarray(t.normalize())
    h, lo, c = m15.high.to_numpy(), m15.low.to_numpy(), m15.close.to_numpy()
    exitb = _exit_bars(t)
    out = []
    for e in np.where(mins == LC)[0]:
        day = dates[e]
        if day not in lv.index or np.isnan(lv.at[day, "adr5"]) or np.isnan(lv.at[day, "mno"]):
            continue
        sel = np.where((dates == day) & (mins >= MNO) & (mins < LC))[0]
        if len(sel) == 0:
            continue
        hi, lw = h[sel].max(), lo[sel].min()
        if hi - lw <= lv.at[day, "adr5"]:
            continue
        move = c[e - 1] - lv.at[day, "mno"]
        if move == 0:
            continue
        d = -1 if move > 0 else 1
        out.append((e - 1, d, hi if d < 0 else lw, exitb[e]))
    return pd.DataFrame(out, columns=["k", "d", "anchor", "exit_bar"])


# ---------------- Trademeting met natuurlijke SL ----------------

def measure_trades(bars: pd.DataFrame, a: np.ndarray, k, d, anchor, exit_bar, rr: float = 1.5,
                   limit=None, valid_bar=None, buffer_atr: float = 0.1, min_sl_atr: float = 0.5,
                   cost: float = 0.0) -> pd.DataFrame:
    """
    Speelt elke trade los af op `bars` (M15):
    - instap: marktorder op de open van candle k+1, of limiet (eerste candle t/m valid_bar die de prijs raakt;
      gevuld op de limiet of een betere open; op de vulcandle telt de TP niet);
    - SL = anchor ∓ buffer (buffer_atr × ATR van candle k); te krap (< min_sl_atr × ATR) -> overgeslagen;
    - TP = rr × risico; SL eerst bij twijfel; gap door de SL -> gevuld op de open;
    - niets geraakt -> sluiten op de close van exit_bar.
    Kolommen: status ('ok', 'sl_te_klein', 'niet_gevuld', 'geen_data'), R (bruto), R_net, win, risk (prijs).
    """
    o, h, lo, c = (bars[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    n = len(c)
    rows = []
    for i in range(len(k)):
        kk, dd, an, xb = int(k[i]), int(d[i]), float(anchor[i]), int(exit_bar[i])
        at = a[kk]
        if not np.isfinite(at) or at <= 0 or kk + 1 >= n or xb <= kk:
            rows.append(("geen_data", np.nan, np.nan, np.nan, np.nan)); continue
        if limit is None:
            e0, ep, skip = kk + 1, o[kk + 1], False
        else:
            lp, vb = float(limit[i]), int(valid_bar[i])
            e0 = None
            for j in range(kk + 1, min(vb, n - 1) + 1):
                if (dd > 0 and lo[j] <= lp) or (dd < 0 and h[j] >= lp):
                    e0 = j; ep = min(lp, o[j]) if dd > 0 else max(lp, o[j]); break
            if e0 is None:
                rows.append(("niet_gevuld", np.nan, np.nan, np.nan, np.nan)); continue
            skip = True
        sl = an - dd * buffer_atr * at
        risk = dd * (ep - sl)
        if risk < min_sl_atr * at:
            rows.append(("sl_te_klein", np.nan, np.nan, np.nan, np.nan)); continue
        tp = ep + dd * rr * risk
        res = None
        for j in range(e0, min(xb, n - 1) + 1):
            adv = lo[j] if dd > 0 else h[j]
            fav = h[j] if dd > 0 else lo[j]
            if dd * (adv - sl) <= 0:
                px = o[j] if (j != e0 and dd * (o[j] - sl) <= 0) else sl
                res = dd * (px - ep) / risk; break
            if dd * (fav - tp) >= 0 and not (skip and j == e0):
                res = rr; break
        if res is None:
            res = dd * (c[min(xb, n - 1)] - ep) / risk
        rows.append(("ok", res, res - cost / risk, float(res > 0), risk))
    return pd.DataFrame(rows, columns=["status", "R", "R_net", "win", "risk"])


def baseline_trades(bars: pd.DataFrame, a: np.ndarray, k, d, risk_atr, pool: np.ndarray, rr: float = 1.5,
                    per_event: int = 5, seed: int = 1, cost: float = 0.0) -> pd.DataFrame:
    """
    Per trade `per_event` willekeurige candles uit `pool` met hetzelfde serveruur en -kwartier, zelfde
    richting, dezelfde SL-afstand in ATR, marktorder op de volgende open, sluiten om 23:00 dezelfde dag.
    Precies per_event rijen per trade, in volgorde (NaN als er niets vergelijkbaars is).
    """
    rng = np.random.default_rng(seed)
    t = bars.index; mins = _minutes(t)
    o = bars.open.to_numpy(float)
    exitb = _exit_bars(t)
    groups = pd.Series(pool).groupby(mins[pool]).apply(np.array).to_dict()
    bk, bd, ba, bx, ok = [], [], [], [], []
    for kk, dd, ra in zip(k, d, risk_atr):
        g = groups.get(mins[int(kk)])
        if g is None or not np.isfinite(ra):
            bk += [0] * per_event; bd += [dd] * per_event; ba += [0.0] * per_event; bx += [1] * per_event
            ok += [False] * per_event; continue
        for j in rng.choice(g, size=per_event):
            at = a[j]
            # anker zo dat SL (anker ∓ 0,1 ATR) op dezelfde afstand in ATR ligt als bij de echte trade
            ba.append(o[min(j + 1, len(o) - 1)] - dd * (ra - 0.1) * at)
            bk.append(j); bd.append(dd); bx.append(exitb[j]); ok.append(True)
    out = measure_trades(bars, a, np.array(bk), np.array(bd), np.array(ba), np.array(bx), rr=rr,
                         min_sl_atr=0.0, cost=cost)
    out.loc[~np.array(ok), ["R", "R_net", "win"]] = np.nan
    return out
