"""
Laag 1 van het edge-onderzoek: signaalonderzoek (docs/onderzoeksplan_edge.md §3 en §9).

Voor elke gebeurtenis (BOS, CHoCH, sweep, FVG, …) meten we wat de koers daarna doet, zonder
strategie: een vaste beugel in ATR (R21: TP +2 ATR / SL −1 ATR, R11: +1/−1), beweging na N candles,
MFE/MAE. Altijd naast een willekeurige basislijn met hetzelfde uur en dezelfde richting.

Belangrijk:
- Alleen gesloten candles; swings pas na bevestiging; hogere timeframes alleen met gesloten candles.
- Instap = open van de candle ná de gebeurtenis (of de limietprijs bij een retest).
- Raakt één candle zowel TP als SL, dan telt de SL (conservatief).
- Data vanaf 2025 wordt door de aanroeper weggesneden vóór er iets berekend wordt.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from katsu.bos import detect_bos
from katsu.structure import DOWN, UP, atr, find_swings, trend_series

HTF = {"15min": ("1h", "4h"), "1h": ("4h", "1D"), "4h": ("1D", "W-MON")}
HORIZONS = (4, 12, 24, 48)
DISPLACEMENT_ATR = 1.0


class _AnyTrend:
    """Trendwaarde die met elke richting overeenkomt: gebruikt om de bestaande detectors
    (detect_bos) zonder H1-filter te draaien. De filters doen we hier zelf, apart en zichtbaar."""
    def __eq__(self, other):
        return True

    def __ne__(self, other):
        return False

    def __hash__(self):
        return 0


ANY = _AnyTrend()


# ---------------- Periodes ----------------

def explore_mask(times: pd.DatetimeIndex) -> np.ndarray:
    """Verkenningshelft (plan §4): alles vóór 2020 + oneven maanden 2020–2024. Nooit 2025+."""
    y, m = times.year, times.month
    return np.asarray((y < 2020) | ((y >= 2020) & (y <= 2024) & (m % 2 == 1)))


def confirm_mask(times: pd.DatetimeIndex) -> np.ndarray:
    """Bevestigingshelft: even maanden 2020–2024."""
    y, m = times.year, times.month
    return np.asarray((y >= 2020) & (y <= 2024) & (m % 2 == 0))


# ---------------- Hogere timeframes ----------------

def _period(rule: str) -> pd.Timedelta:
    return pd.Timedelta(days=7) if rule.startswith("W") else pd.Timedelta(rule)


def htf_trend(bars: pd.DataFrame, tf: str, rule: str, L: int = 3) -> np.ndarray:
    """
    Trend van de hogere timeframe `rule` op het EINDE van elke candle van `bars`,
    met alleen hogere-timeframe-candles die dan volledig gesloten zijn.
    """
    agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
    hb = bars[["open", "high", "low", "close"]].resample(rule, label="left", closed="left").agg(agg)
    hb = hb.dropna(subset=["open"])
    ts = np.array(trend_series(find_swings(hb, L), len(hb)), dtype=object)
    ends = hb.index + _period(rule)
    t_end = bars.index + pd.Timedelta(tf)
    n = ends.searchsorted(t_end, side="right") - 1
    out = np.full(len(bars), "NEUTRAL", dtype=object)
    ok = n >= 0
    out[ok] = ts[n[ok]]
    return out


# ---------------- Hulpfuncties ----------------

def _arrays(bars):
    return (bars["open"].to_numpy(float), bars["high"].to_numpy(float),
            bars["low"].to_numpy(float), bars["close"].to_numpy(float))


def displacement(bars: pd.DataFrame, a: np.ndarray, k: np.ndarray) -> np.ndarray:
    """Body van candle k ≥ 1 ATR (vast vooraf gekozen)."""
    o, h, lo, c = _arrays(bars)
    return np.abs(c[k] - o[k]) >= DISPLACEMENT_ATR * a[k]


def fvg_recent(bars: pd.DataFrame, k: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Is er een FVG in richting d waarvan de derde candle k of k-1 is?"""
    o, h, lo, c = _arrays(bars)
    out = np.zeros(len(k), bool)
    for i, (kk, dd) in enumerate(zip(k, d)):
        for j in (kk, kk - 1):
            if j < 2:
                continue
            if (dd > 0 and lo[j] > h[j - 2]) or (dd < 0 and h[j] < lo[j - 2]):
                out[i] = True
    return out


# ---------------- Gebeurtenissen ----------------
# Elke detector geeft een DataFrame met minstens: k (candle van de gebeurtenis), d (+1/−1).

def bos_events(bars: pd.DataFrame, tf: str, L: int) -> pd.DataFrame:
    """BOS met de structuur mee: hergebruikt katsu.bos.detect_bos zonder H1-filter."""
    s = detect_bos(bars, tf, lambda t: ANY, L=L)
    return pd.DataFrame({"k": [x.bos_index for x in s], "d": [1 if x.direction == "LONG" else -1 for x in s]})


def choch_events(bars: pd.DataFrame, L: int, sweep_window: int = 12) -> pd.DataFrame:
    """
    CHoCH: de structuur op de setup-timeframe is dalend (laatste 2 highs én lows dalend) en een candle
    sluit met de body boven de laatste bevestigde swing high (nog intact) -> LONG. Short gespiegeld.
    Kolommen `level` / `level_index`: de gebroken swing (prijs en positie).
    Kolom `sweep`: werd in de `sweep_window` candles ervoor een (bevestigde, intacte) swing low
    geprikt met een wick en sloot die candle erboven?
    """
    o, h, lo, c = _arrays(bars)
    sw = find_swings(bars, L)
    ts = trend_series(sw, len(bars))
    out = []
    for direction, want, highs, lows, cc, hh, ll in (
            (1, DOWN, [s for s in sw if s.kind == "HIGH"], [s for s in sw if s.kind == "LOW"], c, h, lo),
            (-1, UP, [s for s in sw if s.kind == "LOW"], [s for s in sw if s.kind == "HIGH"], -c, -lo, -h)):
        hc = np.array([s.confirmed_at for s in highs]); hp = np.array([s.price for s in highs]) * direction
        hi = np.array([s.index for s in highs])
        lc = np.array([s.confirmed_at for s in lows]); lp = np.array([s.price for s in lows]) * direction
        li = np.array([s.index for s in lows])
        for j in range(1, len(c)):
            if ts[j - 1] != want:
                continue
            kh = np.searchsorted(hc, j - 1, side="right")
            if kh == 0 or cc[j] <= hp[kh - 1]:
                continue
            if np.any(cc[hi[kh - 1] + 1:j] > hp[kh - 1]):
                continue                                   # niveau niet meer intact
            # sweep vooraf: een candle q in de `sweep_window` candles ervoor prikte met de wick onder de
            # laatste swing low die op dat moment (q-1) bevestigd was, en sloot erboven
            swept = False
            for q in range(max(j - sweep_window, 1), j):
                kl = np.searchsorted(lc, q - 1, side="right")
                if kl > 0 and ll[q] < lp[kl - 1] and cc[q] > lp[kl - 1]:
                    swept = True; break
            out.append((j, direction, swept, hp[kh - 1] * direction, int(hi[kh - 1])))
    df = pd.DataFrame(out, columns=["k", "d", "sweep", "level", "level_index"])
    return df.sort_values("k").reset_index(drop=True)


def swing_sweep_events(bars: pd.DataFrame, L: int, lookback: int = 24) -> pd.DataFrame:
    """Wick door de laatste bevestigde, intacte swing low (≤ lookback candles oud), close erboven -> LONG."""
    o, h, lo, c = _arrays(bars)
    sw = find_swings(bars, L)
    out = []
    for direction, kind, cc, ll in ((1, "LOW", c, lo), (-1, "HIGH", -c, -h)):
        ss = [s for s in sw if s.kind == kind]
        conf = np.array([s.confirmed_at for s in ss]); price = np.array([s.price for s in ss]) * direction
        idx = np.array([s.index for s in ss])
        used = set()
        for j in range(1, len(c)):
            k = np.searchsorted(conf, j - 1, side="right")
            if k == 0:
                continue
            lvl, ix = price[k - 1], idx[k - 1]
            if j - ix > lookback or ix in used:
                continue
            if np.any(cc[ix + 1:j] < lvl):
                used.add(ix); continue                     # al doorbroken: geen liquiditeit meer
            if ll[j] < lvl and cc[j] > lvl:
                out.append((j, direction)); used.add(ix)
    return pd.DataFrame(out, columns=["k", "d"]).sort_values("k").reset_index(drop=True)


def level_sweep_events(bars: pd.DataFrame, kind: str) -> pd.DataFrame:
    """
    Sweep van een vast niveau (eerste keer per niveau):
    - "day":  high/low van de vorige serverdag
    - "week": high/low van de vorige serverweek (week begint maandag)
    - "asia": high/low van vandaag tussen 01:00 en 09:00 server; sweep pas vanaf 09:00 tot 21:00
    Wick erdoor en close terug binnen -> ommekeer (low-sweep = LONG, high-sweep = SHORT).
    """
    o, h, lo, c = _arrays(bars)
    t = bars.index
    if kind in ("day", "week"):
        key = t.normalize() if kind == "day" else (t - pd.to_timedelta(t.dayofweek, unit="D")).normalize()
        g = pd.DataFrame({"h": h, "l": lo, "key": key}).groupby("key").agg(h=("h", "max"), l=("l", "min"))
        prev = g.shift(1)
        lvl_h = prev["h"].reindex(key).to_numpy(); lvl_l = prev["l"].reindex(key).to_numpy()
        active = np.ones(len(t), bool)
    elif kind == "asia":
        key = t.normalize()
        hr = t.hour
        in_asia = (hr >= 1) & (hr < 9)
        g = pd.DataFrame({"h": np.where(in_asia, h, np.nan), "l": np.where(in_asia, lo, np.nan), "key": key})
        rng = g.groupby("key").agg(h=("h", "max"), l=("l", "min"))
        lvl_h = rng["h"].reindex(key).to_numpy(); lvl_l = rng["l"].reindex(key).to_numpy()
        active = np.asarray((hr >= 9) & (hr < 21))
    else:
        raise ValueError(kind)
    keys = np.asarray(key)
    out, done_h, done_l = [], set(), set()
    for j in range(len(t)):
        if not active[j]:
            continue
        kk = keys[j]
        if not np.isnan(lvl_l[j]) and kk not in done_l:
            if c[j] < lvl_l[j]:
                done_l.add(kk)                              # close eronder: run, niveau opgebruikt
            elif lo[j] < lvl_l[j]:
                out.append((j, 1)); done_l.add(kk)
        if not np.isnan(lvl_h[j]) and kk not in done_h:
            if c[j] > lvl_h[j]:
                done_h.add(kk)
            elif h[j] > lvl_h[j]:
                out.append((j, -1)); done_h.add(kk)
    return pd.DataFrame(out, columns=["k", "d"]).sort_values("k").reset_index(drop=True)


def fvg_events(bars: pd.DataFrame, retest_window: int = 12, inverse_window: int = 24) -> dict:
    """
    Drie soorten FVG-gebeurtenissen:
    - "vorming": de derde candle k van een FVG (d = richting van de gap), instap open k+1
    - "retest":  eerste aanraking van de rand binnen `retest_window` candles; instap op de rand
                 (kolommen entry_bar, entry_price); op die candle telt alleen de SL, niet de TP
    - "inverse": een close door de hele gap binnen `inverse_window` candles -> andere richting
    """
    o, h, lo, c = _arrays(bars)
    n = len(c)
    form, retest, inverse = [], [], []
    for k in range(2, n):
        if lo[k] > h[k - 2]:
            d, top, bot = 1, lo[k], h[k - 2]
        elif h[k] < lo[k - 2]:
            d, top, bot = -1, lo[k - 2], h[k]
        else:
            continue
        form.append((k, d))
        edge = top if d > 0 else bot
        for m in range(k + 1, min(k + 1 + retest_window, n)):
            if (d > 0 and lo[m] <= edge) or (d < 0 and h[m] >= edge):
                retest.append((k, d, m, edge)); break
        far = bot if d > 0 else top
        for m in range(k + 1, min(k + 1 + inverse_window, n)):
            if (d > 0 and c[m] < far) or (d < 0 and c[m] > far):
                inverse.append((m, -d)); break
    return {"vorming": pd.DataFrame(form, columns=["k", "d"]),
            "retest": pd.DataFrame(retest, columns=["k", "d", "entry_bar", "entry_price"]),
            "inverse": pd.DataFrame(inverse, columns=["k", "d"]).drop_duplicates("k")}


# ---------------- Meting ----------------

def measure(bars: pd.DataFrame, a: np.ndarray, k: np.ndarray, d: np.ndarray,
            entry_bar: np.ndarray | None = None, entry_price: np.ndarray | None = None,
            max_bars: int = 48) -> pd.DataFrame:
    """
    Meet per gebeurtenis (alles in ATR van candle k, in de richting d):
    R21 / R15 / R11 (beugel TP 2, 1,5 of 1 ATR, SL 1 ATR, hoogstens max_bars candles, SL eerst bij twijfel),
    fwd_h (close na h candles t.o.v. de instap), mfe24 / mae24.
    Zonder entry_bar: instap = open van candle k+1 (en die candle telt volledig mee).
    Met entry_bar/entry_price (limiet): op de instapcandle telt alleen de SL.
    Gebeurtenissen zonder volledige toekomst (einde data) krijgen NaN.
    """
    o, h, lo, c = _arrays(bars)
    n = len(c)
    res = np.full((len(k), 5 + len(HORIZONS)), np.nan)
    for i in range(len(k)):
        kk, dd, at = int(k[i]), int(d[i]), a[int(k[i])]
        if not np.isfinite(at) or at <= 0:
            continue
        if entry_bar is None:
            e0, ep, skip_first = kk + 1, None, False
        else:
            e0, ep, skip_first = int(entry_bar[i]), float(entry_price[i]), True
        if e0 + max_bars > n:
            continue
        if ep is None:
            ep = o[e0]
        hh = h[e0:e0 + max_bars]; ll = lo[e0:e0 + max_bars]; cc = c[e0:e0 + max_bars]
        fav = (hh - ep) if dd > 0 else (ep - ll)
        adv = (ep - ll) if dd > 0 else (hh - ep)
        fav = fav / at; adv = adv / at
        last = dd * (cc[-1] - ep) / at
        row = []
        for tp in (2.0, 1.5, 1.0):
            sl_hit = adv >= 1.0
            tp_hit = fav >= tp
            if skip_first:
                tp_hit = tp_hit.copy(); tp_hit[0] = False
            si = int(np.argmax(sl_hit)) if sl_hit.any() else None
            ti = int(np.argmax(tp_hit)) if tp_hit.any() else None
            if si is not None and (ti is None or si <= ti):
                row.append(-1.0)
            elif ti is not None:
                row.append(tp)
            else:
                row.append(last)
        w = min(24, max_bars)
        row += [fav[:w].max(), adv[:w].max()]
        row += [dd * (cc[hz - 1] - ep) / at if hz <= max_bars else np.nan for hz in HORIZONS]
        res[i] = row
    cols = ["R21", "R15", "R11", "mfe24", "mae24"] + [f"fwd{hz}" for hz in HORIZONS]
    return pd.DataFrame(res, columns=cols)


def baseline(bars: pd.DataFrame, a: np.ndarray, ev_k: np.ndarray, ev_d: np.ndarray, pool: np.ndarray,
             strata: np.ndarray | None = None, per_event: int = 5, seed: int = 1) -> pd.DataFrame:
    """
    Willekeurige vergelijking: per gebeurtenis `per_event` candles uit `pool` (indexen) met hetzelfde
    uur (en, als `strata` gegeven is, dezelfde stratumwaarde), zelfde richting, instap op de volgende open.
    Altijd precies per_event rijen per gebeurtenis, in dezelfde volgorde (NaN als er niets vergelijkbaars is).
    """
    rng = np.random.default_rng(seed)
    hours = bars.index.hour.to_numpy()
    key_all = hours.astype(object) if strata is None else np.array(
        [f"{x}|{y}" for x, y in zip(hours, strata)], dtype=object)
    groups: dict = {}
    for p in pool:
        groups.setdefault(key_all[p], []).append(p)
    groups = {g: np.array(v) for g, v in groups.items()}
    bk, bd, ok = [], [], []
    for kk, dd in zip(ev_k, ev_d):
        g = groups.get(key_all[kk])
        if g is None or len(g) == 0:                    # geen vergelijkbare candle: NaN-rijen
            bk.extend([0] * per_event); bd.extend([dd] * per_event); ok.extend([False] * per_event)
            continue
        pick = rng.choice(g, size=per_event, replace=True)
        bk.extend(pick); bd.extend([dd] * per_event); ok.extend([True] * per_event)
    out = measure(bars, a, np.array(bk, int), np.array(bd, int))
    out.loc[~np.array(ok, bool), :] = np.nan
    out["k"] = bk; out["d"] = bd
    return out


def clustered_t(x: np.ndarray, weeks: np.ndarray) -> tuple[float, float]:
    """Gemiddelde en standaardfout met clustering per week (som van afwijkingen per week)."""
    ok = np.isfinite(x)
    x, weeks = x[ok], weeks[ok]
    n = len(x)
    if n < 2:
        return np.nan, np.nan
    m = x.mean()
    s = pd.Series(x - m).groupby(weeks).sum().to_numpy()
    se = np.sqrt((s ** 2).sum()) / n
    return float(m), float(se)
