"""
Setups en kenmerken voor het bouwstenen-dashboard (docs/dashboard_spec.md).

Soorten: FVG (elke FVG; "na breuk" is een kenmerk) en IFVG (een FVG die binnen 48 candles met een close doorbroken
wordt en van rol wisselt). Alles in "LONG-ruimte": voor SHORT worden de prijzen gespiegeld (high <-> −low).
Elk kenmerk gebruikt alleen candles die op het signaalmoment gesloten zijn; swings pas na bevestiging.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from katsu.structure import find_swings, trend_series

L_STRUCT = 3
ENTRY_FRAC = 0.382
IFVG_WINDOW = 48
LOOKBACK_SWEEP = 20
LOOKBACK_OB = 10
LOOKBACK_FVG = 20
ASIA_SERVER = (2 * 60, 9 * 60)          # 01:00–08:00 Belgische tijd


def _mirror(bars, d):
    o, h, lo, c = (bars[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    return (o, h, lo, c) if d > 0 else (-o, -lo, -h, -c)


class _Space:
    """Alle hulpreeksen in LONG-ruimte voor één richting."""

    def __init__(self, bars: pd.DataFrame, d: int, L: int = L_STRUCT):
        self.d = d
        self.o, self.h, self.lo, self.c = _mirror(bars, d)
        n = self.n = len(self.c)
        sw = find_swings(pd.DataFrame({"high": self.h, "low": self.lo}), L)
        hi = sorted((s for s in sw if s.kind == "HIGH"), key=lambda s: s.confirmed_at)
        lw = sorted((s for s in sw if s.kind == "LOW"), key=lambda s: s.confirmed_at)
        self.h_conf = np.array([s.confirmed_at for s in hi], int); self.h_idx = np.array([s.index for s in hi], int)
        self.h_px = np.array([s.price for s in hi], float)
        self.l_conf = np.array([s.confirmed_at for s in lw], int); self.l_px = np.array([s.price for s in lw], float)
        self.trend = np.array(trend_series(sw, n), dtype=object)          # UP = met de richting mee
        nxt = np.full(n, n, int); st: list[int] = []
        for i in range(n):
            while st and self.h[i] >= self.h[st[-1]]:
                nxt[st.pop()] = i
            st.append(i)
        self.h_death = nxt[self.h_idx] if len(self.h_idx) else np.array([], int)
        # sweep van een swing low op candle i: wick onder de laatste bevestigde swing low, close erboven
        q = np.searchsorted(self.l_conf, np.arange(n), side="right") - 1
        lvl = np.where(q >= 0, self.l_px[np.maximum(q, 0)], np.nan) if len(self.l_px) else np.full(n, np.nan)
        self.swept = (q >= 0) & (self.lo < lvl) & (self.c > lvl)
        self.fvg = np.zeros(n, bool); self.fvg[2:] = self.lo[2:] > self.h[:-2]
        self.fvg_opp = np.zeros(n, bool); self.fvg_opp[2:] = self.h[2:] < self.lo[:-2]

    def last_high(self, i):
        """Laatste bevestigde swing high op candle i (index in de lijst) of -1."""
        return int(np.searchsorted(self.h_conf, i, side="right")) - 1

    def breaks(self, i):
        """Sluit candle i boven de laatste bevestigde, intacte swing high? Geeft (bool, swing-index)."""
        j = self.last_high(i)
        if j < 0 or self.c[i] <= self.h_px[j]:
            return False, -1
        if self.c[self.h_idx[j] + 1:i].max(initial=-np.inf) > self.h_px[j]:
            return False, -1
        return True, int(self.h_idx[j])

    def target(self, s, leg_high):
        q = int(np.searchsorted(self.h_conf, s, side="right"))
        ok = (self.h_death[:q] > s) & (self.h_px[:q] > leg_high)
        return float(self.h_px[:q][ok].min()) if ok.any() else None

    def ob_anchor(self, start, c1, c2):
        """Laagste low vanaf de laatste tegengestelde candle in [start, c1] t/m c2; geen: laagste low c1..c2."""
        bear = [i for i in range(max(start, 0), c1 + 1) if self.c[i] < self.o[i]]
        a = bear[-1] if bear else c1
        return float(self.lo[a:c2 + 1].min()), bool(bear)


def _events_one_side(bars: pd.DataFrame, d: int, L: int = L_STRUCT) -> list[dict]:
    S = _Space(bars, d, L)
    out = []

    def base(kind, s, c1, top, bottom, anchor, ob, brk, swing_idx, disp_i, body_i):
        entry = top - ENTRY_FRAC * (top - bottom)
        tp = S.target(s, S.h[c1:s + 1].max())
        fvg_nr = int(S.fvg[max(c1 - LOOKBACK_FVG, 2):c1 + 2].sum())
        return {"soort": kind, "d": d, "s": s, "c1": c1, "entry": d * entry, "anchor": d * anchor,
                "tp": None if tp is None else d * tp, "gap": top - bottom, "brk": brk, "swing_idx": swing_idx,
                "ob": ob, "fvg_nr": fvg_nr, "disp": abs(S.c[disp_i] - S.o[disp_i]),
                "body3": abs(S.c[body_i] - S.o[body_i]) / max(S.h[body_i] - S.lo[body_i], 1e-12),
                "sweep": bool(S.swept[max(c1 - LOOKBACK_SWEEP, 0):c1].any()), "trend_m15": S.trend[c1],
                "entry_ls": entry}

    for k in np.nonzero(S.fvg)[0]:                                  # ---- FVG ----
        c1 = k - 2
        brk, sw_i = S.breaks(k - 1)
        if brk:
            origin = sw_i + int(np.argmin(S.lo[sw_i:k]))
            anchor, ob = S.ob_anchor(origin, c1, k - 1)
        else:
            anchor, ob = S.ob_anchor(c1 - LOOKBACK_OB, c1, k - 1)
        out.append(base("FVG", int(k), int(c1), S.lo[k], S.h[k - 2], anchor, ob, brk, sw_i, k - 1, k))
    for k in np.nonzero(S.fvg_opp)[0]:                              # ---- IFVG ----
        top, bottom = S.lo[k - 2], S.h[k]                            # tegengesteld gat in LONG-ruimte
        end = min(k + IFVG_WINDOW, S.n - 1)
        js = np.nonzero(S.c[k + 1:end + 1] > top)[0]
        if not len(js):
            continue
        j = k + 1 + int(js[0])
        brk, sw_i = S.breaks(j)
        anchor = float(S.lo[k - 2:j + 1].min())
        ob = bool((S.c[max(k - 2 - LOOKBACK_OB, 0):k - 1] < S.o[max(k - 2 - LOOKBACK_OB, 0):k - 1]).any())
        out.append(base("IFVG", int(j), int(k - 2), top, bottom, anchor, ob, brk, sw_i, j, j))
    return out


def build_events(bars: pd.DataFrame, L: int = L_STRUCT) -> pd.DataFrame:
    """Alle setups (beide richtingen) met hun ruwe kenmerken; gesorteerd op signaalcandle."""
    ev = pd.DataFrame(_events_one_side(bars, 1, L) + _events_one_side(bars, -1, L))
    if ev.empty:                                       # geen enkele setup (korte of vlakke data, KATSU Live)
        return pd.DataFrame(columns=["s", "d"])
    return ev.sort_values(["s", "d"]).reset_index(drop=True)


# ---------------- kenmerken die van de hele markt afhangen ----------------

def rel_trend(tr: np.ndarray, d: np.ndarray) -> np.ndarray:
    """UP/DOWN/NEUTRAL (oorspronkelijke richting) -> mee/tegen/neutraal t.o.v. de trade."""
    want = np.where(d > 0, "UP", "DOWN"); other = np.where(d > 0, "DOWN", "UP")
    return np.where(tr == want, "mee", np.where(tr == other, "tegen", "neutraal"))


def breuk_label(brk: np.ndarray, trend_m15_mirrored: np.ndarray) -> np.ndarray:
    """Breuk + M15-trend vóór de setup (in LONG-ruimte: UP = mee) -> geen / BOS / CHoCH / breuk uit neutraal."""
    return np.where(~brk, "geen", np.where(trend_m15_mirrored == "UP", "BOS",
                                           np.where(trend_m15_mirrored == "DOWN", "CHoCH", "breuk uit neutraal")))


def session_label(be_hour: np.ndarray) -> np.ndarray:
    h = np.asarray(be_hour)
    return np.select([(h >= 1) & (h < 8), (h >= 8) & (h < 13), (h >= 13) & (h < 17), (h >= 17) & (h < 22)],
                     ["Azië", "Londen", "overlap", "New York"], "nacht")


def bin_label(x, edges, labels):
    x = np.asarray(x, float)
    out = np.array(labels, dtype=object)[np.clip(np.searchsorted(edges, x, side="right"), 0, len(labels) - 1)]
    out[~np.isfinite(x)] = "onbekend"
    return out


def day_context(bars: pd.DataFrame) -> pd.DataFrame:
    """Per candle: low/high van gisteren (serverdag) en de Azië-range van vandaag (alleen bekend na 09:00 server)."""
    t = bars.index; date = t.normalize(); mins = t.hour * 60 + t.minute
    df = pd.DataFrame({"h": bars.high.to_numpy(), "l": bars.low.to_numpy(), "date": date})
    g = df.groupby("date").agg(dh=("h", "max"), dl=("l", "min"))
    prev = g.shift(1)
    asia = df[(mins >= ASIA_SERVER[0]) & (mins < ASIA_SERVER[1])].groupby("date").agg(ah=("h", "max"), al=("l", "min"))
    ctx = pd.DataFrame(index=t)
    ctx["prev_h"] = prev.dh.reindex(date).to_numpy(); ctx["prev_l"] = prev.dl.reindex(date).to_numpy()
    after = np.asarray(mins >= ASIA_SERVER[1])
    ctx["asia_h"] = np.where(after, asia.ah.reindex(date).to_numpy(), np.nan)
    ctx["asia_l"] = np.where(after, asia.al.reindex(date).to_numpy(), np.nan)
    # extremen van vandaag t/m candle i (cumulatief per dag)
    ctx["day_h_sofar"] = df.groupby("date").h.cummax().to_numpy()
    ctx["day_l_sofar"] = df.groupby("date").l.cummin().to_numpy()
    ctx["asia_end_h_sofar"] = _cum_after(df, after, "h", np.maximum)
    ctx["asia_end_l_sofar"] = _cum_after(df, after, "l", np.minimum)
    return ctx


def _cum_after(df, after, col, fn):
    """Cumulatief extreme van `col` per dag, alleen vanaf het einde van de Azië-sessie (anders NaN)."""
    vals = np.where(after, df[col].to_numpy(float), np.nan)
    s = pd.Series(vals)
    grp = df["date"].to_numpy()
    res = s.groupby(grp).cummax() if fn is np.maximum else s.groupby(grp).cummin()
    return res.to_numpy()


def nfp_day(times: pd.DatetimeIndex) -> np.ndarray:
    """Eerste vrijdag van de maand (Belgische datum)."""
    be = times - pd.Timedelta(hours=1)
    return np.asarray((be.dayofweek == 4) & (be.day <= 7))


# ---------------- alles samen: kenmerken als labels ----------------

def features(bars: pd.DataFrame, ev: pd.DataFrame, atr_values, h1, h4, d1, pip: float) -> pd.DataFrame:
    """Voegt de gelabelde kenmerken (spec §4) toe aan de setups. h1/h4/d1 = trend per candle (htf_trend)."""
    a = np.asarray(atr_values, float)
    s = ev.s.to_numpy(int); d = ev.d.to_numpy(int); c1 = ev.c1.to_numpy(int)
    t_sig = bars.index[s] + pd.Timedelta("15min")
    be = t_sig - pd.Timedelta(hours=1)
    ctx = day_context(bars)
    out = ev.copy()
    out["richting"] = np.where(d > 0, "long", "short")
    out["breuk"] = breuk_label(ev.brk.to_numpy(bool), ev.trend_m15.to_numpy(object))
    out["sweep_swing"] = np.where(ev.sweep, "ja", "nee")
    pl, ph = ctx.prev_l.to_numpy()[s], ctx.prev_h.to_numpy()[s]
    dl, dh = ctx.day_l_sofar.to_numpy()[s], ctx.day_h_sofar.to_numpy()[s]
    sw_day = np.where(d > 0, dl < pl, dh > ph)
    out["sweep_dag"] = np.where(np.isnan(pl), "onbekend", np.where(sw_day, "ja", "nee"))
    al, ah = ctx.asia_l.to_numpy()[s], ctx.asia_h.to_numpy()[s]
    el, eh = ctx.asia_end_l_sofar.to_numpy()[s], ctx.asia_end_h_sofar.to_numpy()[s]
    sw_asia = np.where(d > 0, el < al, eh > ah)
    out["sweep_azie"] = np.where(np.isnan(al), "vóór einde Azië", np.where(sw_asia, "ja", "nee"))
    out["order_block"] = np.where(ev.ob, "ja", "nee")
    out["fvg_nummer"] = np.select([ev.fvg_nr == 0, ev.fvg_nr == 1], ["eerste", "tweede"], "derde+")
    tm = ev.trend_m15.to_numpy(object)
    out["trend_m15"] = np.where(tm == "UP", "mee", np.where(tm == "DOWN", "tegen", "neutraal"))
    out["trend_h1"] = rel_trend(np.asarray(h1)[s], d)
    out["trend_h4"] = rel_trend(np.asarray(h4)[s], d)
    out["trend_d1"] = rel_trend(np.asarray(d1)[s], d)
    mid = (pl + ph) / 2
    entry = ev.entry.to_numpy(float)
    disc = np.where(d > 0, entry < mid, entry > mid)
    out["premium_discount"] = np.where(np.isnan(mid), "onbekend", np.where(disc, "mee", "tegen"))
    out["sessie"] = session_label(be.hour)
    out["uur"] = be.hour
    out["weekdag"] = np.array(["ma", "di", "wo", "do", "vr", "za", "zo"], dtype=object)[be.dayofweek]
    srv = t_sig.hour
    out["silver_bullet"] = np.where(np.isin(srv, [10, 17, 21]), "ja", "nee")
    A = a[s]
    out["gat_atr"] = bin_label(ev.gap / A, [0.25, 0.5, 1, 2], ["<0,25", "0,25–0,5", "0,5–1", "1–2", ">2"])
    out["displacement"] = bin_label(ev.disp / A, [0.5, 1, 2], ["<0,5", "0,5–1", "1–2", ">2"])
    out["candle3_vol"] = bin_label(ev.body3, [0.25, 0.5], ["<25%", "25–50%", "≥50%"])
    risk = np.abs(entry - ev.anchor.to_numpy(float))
    out["risk_plan"] = risk
    out["sl_atr"] = bin_label(risk / A, [1, 2, 3], ["<1", "1–2", "2–3", ">3"])
    tp = ev.tp.to_numpy(float)
    rr = np.where(np.isnan(tp), 2.0, np.minimum(np.abs(tp - entry) / risk, 2.0))
    out["rr_plan"] = bin_label(rr, [1, 1.5, 1.999], ["<1", "1–1,5", "1,5–2", "2"])
    med = pd.Series(a).rolling(20 * 96, min_periods=96).median().shift(1).to_numpy()[s]
    out["volatiliteit"] = bin_label(A / med, [0.8, 1.25], ["laag", "normaal", "hoog"])
    out["nfp_dag"] = np.where(nfp_day(t_sig), "ja", "nee")
    out["t_sig"] = t_sig
    out["atr"] = A
    return out
