"""
Backtest (spec §7–8): dezelfde detectie- en uitvoeringscode als live, toegepast op historische data.

Per variant (setup-timeframe × entry A/B × swinglengte L) en per slippage-niveau:
1. setups zoeken per markt (signals.detect_setups, H1-trend als filter),
2. van elke setup een orderplan maken (execution.make_plan),
3. alle markten samen afspelen met 1 positie per markt en een gezamenlijke dagstop
   (execution.run_portfolio),
4. de context van elke setup loggen (spec §7) — alleen meten, geen filter.

Niets in deze module mag naar de out-of-sample periode kijken: de aanroeper geeft de data al
afgesneden mee (zie scripts/backtest.py).
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from katsu.bos import detect_bos, make_bos_plan
from katsu.fvg import detect_fvg, make_fvg_plan
from katsu.data import resample
from katsu.execution import (M1, Instrument, OrderPlan, entry_level_variant_b, make_plan,
                             planned_cost_r, run_portfolio)
from katsu.signals import LONG, Setup, detect_setups, h1_trend_lookup, multi_tf_trend
from katsu.structure import atr

SERVER_OFFSET_H = 1           # servertijd = Brussel + 1 uur
TF_NAMES = {"5min": "M5", "15min": "M15"}


# ---------------- Kerncijfers ----------------

def metrics(r) -> dict:
    """
    Kerncijfers van een reeks netto R-resultaten, in tijdsvolgorde.
    - winrate: aandeel trades met netto R > 0
    - pf (profit factor): som van de winsten / som van de verliezen (inf zonder verliezen)
    - max_dd: grootste daling van de cumulatieve R vanaf een eerdere top (de start telt als top 0)
    - max_verliesreeks: langste reeks opeenvolgende trades met netto R <= 0
    """
    r = np.asarray(list(r), dtype=float)
    n = len(r)
    if n == 0:
        return {"trades": 0, "winrate": np.nan, "gem_r": np.nan, "totaal_r": 0.0,
                "pf": np.nan, "max_dd": 0.0, "max_verliesreeks": 0}
    wins, losses = r[r > 0].sum(), -r[r <= 0].sum()
    cum = np.concatenate([[0.0], np.cumsum(r)])
    dd = float(np.max(np.maximum.accumulate(cum) - cum))
    streak = best = 0
    for x in r:
        streak = streak + 1 if x <= 0 else 0
        best = max(best, streak)
    return {"trades": n, "winrate": float((r > 0).mean()), "gem_r": float(r.mean()),
            "totaal_r": float(r.sum()), "pf": float(wins / losses) if losses > 0 else np.inf,
            "max_dd": dd, "max_verliesreeks": best}


# ---------------- Context per setup (spec §7) ----------------

def session_be(hour: int) -> str:
    """Sessie op basis van het Brusselse uur (vaste indeling, alleen voor de rapportage)."""
    if hour < 8:
        return "Azië"
    if hour < 14:
        return "Londen"
    if hour < 18:
        return "Londen+NY"
    return "NY"


def has_fvg(setup: Setup, bars: pd.DataFrame) -> bool:
    """Zit er een FVG in de CHoCH-beweging (zelfde definitie als entry-variant B)?"""
    h = bars["high"].to_numpy(float); lo = bars["low"].to_numpy(float)
    for i in range(setup.sweep_index + 1, setup.choch_index):
        if setup.direction == LONG and lo[i + 1] > h[i - 1]:
            return True
        if setup.direction != LONG and h[i + 1] < lo[i - 1]:
            return True
    return False


def setup_context(setup: Setup, bars: pd.DataFrame, atr_series: pd.Series, atr_pct: pd.Series,
                  trends: dict) -> dict:
    t_be = setup.signal_time - pd.Timedelta(hours=SERVER_OFFSET_H)
    a = float(atr_series.iloc[setup.choch_index])
    c = float(bars["close"].iloc[setup.choch_index])
    return {
        "uur_be": t_be.hour, "dag_be": t_be.day_name(), "sessie": session_be(t_be.hour),
        "ochtend": 6 <= t_be.hour < 12,
        "atr": a, "atr_pct": float(atr_pct.iloc[setup.choch_index]),
        "sweep_diepte_atr": abs(setup.swept_level - setup.sweep_extreme) / a if a > 0 else np.nan,
        "sweep_body_pct": setup.sweep_body_pct,
        "candles_sweep_choch": setup.choch_index - setup.sweep_index,
        "afstand_entry_sl_atr": abs(c - setup.sweep_extreme) / a if a > 0 else np.nan,
        "fvg_in_choch": has_fvg(setup, bars),
        **{f"trend_{k}": v for k, v in trends.items()},
    }


def bos_context(setup, bars: pd.DataFrame, atr_series: pd.Series, atr_pct: pd.Series,
                trends: dict) -> dict:
    """Context van een BOS-setup (spec v0.2 §2, zelfde velden waar ze bestaan)."""
    t_be = setup.signal_time - pd.Timedelta(hours=SERVER_OFFSET_H)
    i = setup.bos_index
    a = float(atr_series.iloc[i])
    c = float(bars["close"].iloc[i])
    return {
        "uur_be": t_be.hour, "dag_be": t_be.day_name(), "sessie": session_be(t_be.hour),
        "ochtend": 6 <= t_be.hour < 12,
        "atr": a, "atr_pct": float(atr_pct.iloc[i]),
        "breuk_voorbij_niveau_atr": abs(c - setup.level) / a if a > 0 else np.nan,
        "niveau_tot_hl_atr": abs(setup.level - setup.hl_price) / a if a > 0 else np.nan,
        "candles_niveau_bos": i - setup.level_index,
        **{f"trend_{k}": v for k, v in trends.items()},
    }


def fvg_context(setup, bars: pd.DataFrame, atr_series: pd.Series, atr_pct: pd.Series,
                trends: dict) -> dict:
    """Context van een FVG-setup (spec v0.3)."""
    t_be = setup.signal_time - pd.Timedelta(hours=SERVER_OFFSET_H)
    i = setup.index
    a = float(atr_series.iloc[i])
    return {
        "uur_be": t_be.hour, "dag_be": t_be.day_name(), "sessie": session_be(t_be.hour),
        "ochtend": 6 <= t_be.hour < 12,
        "atr": a, "atr_pct": float(atr_pct.iloc[i]),
        "fvg_grootte_atr": (setup.top - setup.bottom) / a if a > 0 else np.nan,
        **{f"trend_{k}": v for k, v in trends.items()},
    }


# ---------------- Voorbereiding per markt ----------------

class MarketData:
    """Alles wat per markt maar één keer berekend moet worden."""

    def __init__(self, name: str, m1: pd.DataFrame, ins: Instrument):
        self.name, self.m1, self.ins = name, m1, ins
        self.h1_trend = h1_trend_lookup(resample(m1, "1h"), 3)
        self.ctx_trend = multi_tf_trend(m1)
        self.bars: dict = {}
        self._setups: dict = {}

    def tf_bars(self, tf: str):
        if tf not in self.bars:
            b = resample(self.m1, tf)
            a = atr(b, 14)
            pct = a.rolling(2000, min_periods=200).rank(pct=True)   # ATR t.o.v. de laatste ~2000 candles
            self.bars[tf] = (b, a, pct)
        return self.bars[tf]

    def setups(self, tf: str, L, block: str = "sweep") -> list:
        """block = "sweep" (bouwsteen 1), "bos" (bouwsteen 2) of "fvg" (bouwsteen 3).
        Bij "fvg" is L de trendfilter ("T0" of "T+"), want een FVG heeft geen swings nodig."""
        key = (tf, L, block)
        if key not in self._setups:
            b, _, _ = self.tf_bars(tf)
            if block == "sweep":
                self._setups[key] = detect_setups(b, tf, self.h1_trend, L=L)
            elif block == "bos":
                self._setups[key] = detect_bos(b, tf, self.h1_trend, L=L)
            elif block == "fvg":
                self._setups[key] = detect_fvg(b, tf, self.ctx_trend, filt=L)
            else:
                raise ValueError(f"onbekende bouwsteen: {block}")
        return self._setups[key]


# ---------------- Eén variant ----------------

def run_variant(markets: list[MarketData], tf: str, variant: str, L: int,
                slip: dict | None = None, day_stop_r: float = -2.0,
                block: str = "sweep", frictionless: bool = False) -> pd.DataFrame:
    """
    Speelt één variant af over alle markten samen. `slip` = {markt: slippage in prijs}
    (zonder: de basis uit het Instrument). Geeft één rij per setup: context + uitkomst.

    frictionless=True is een DIAGNOSE (spec v0.2 §6): dezelfde setups die het kostenplafond bij
    basiskosten halen, maar afgespeeld zonder spread, slippage en commissie. Zo zie je of er
    vóór kosten een voorsprong is. Nooit een kiesbare variant.
    """
    plans, ctx_rows, data, inss = [], {}, {}, {}
    for md in markets:
        # stresstest: slechtere uitvoering, maar het kostenplafond beslist op de basis-slippage
        ins = replace(md.ins, slip=slip[md.name], cap_slip=md.ins.slip) if slip else md.ins
        d = M1(md.m1, ins)
        if frictionless:
            ins_run = replace(ins, point=0.0, min_spread=0.0, slip=0.0, commission=0.0, swap=0.0, rollover_min_spread=0.0)
            inss[md.name], data[md.name] = ins_run, M1(md.m1, ins_run)
        else:
            inss[md.name], data[md.name] = ins, d
        b, a, pct = md.tf_bars(tf)
        for s in md.setups(tf, L, block):
            if block in ("bos", "fvg"):
                if block == "bos":
                    p = make_bos_plan(s, tf, a, variant, ins)
                    ctx = bos_context(s, b, a, pct, md.ctx_trend(s.signal_time))
                else:
                    p = make_fvg_plan(s, tf, a, variant, ins)
                    ctx = fvg_context(s, b, a, pct, md.ctx_trend(s.signal_time))
                if frictionless and p.max_cost_r is not None:
                    _, cr = planned_cost_r(p, d, ins)
                    if cr is None or cr > p.max_cost_r:
                        continue                       # zou bij echte kosten overgeslagen zijn
                    p = replace(p, max_cost_r=None)
                plans.append(p)
            else:
                plans.append(make_plan(s, b, tf, a, variant, ins))
                ctx = setup_context(s, b, a, pct, md.ctx_trend(s.signal_time))
                if variant == "B":
                    ctx["limiet"] = entry_level_variant_b(s, b)
            ctx_rows[(md.name, s.signal_time, s.direction)] = ctx
    out = run_portfolio(plans, data, inss, day_stop_r=day_stop_r, server_offset_h=SERVER_OFFSET_H)
    if out.empty:
        return out
    ctx = pd.DataFrame([ctx_rows[k] for k in zip(out.market, out.signal_time, out.direction)])
    out = pd.concat([out.reset_index(drop=True), ctx], axis=1)
    if block == "fvg":
        name = f"FVG-{TF_NAMES.get(tf, tf)}-{variant}-{L}"
    else:
        prefix = "BOS-" if block == "bos" else ""
        name = f"{prefix}{TF_NAMES.get(tf, tf)}-{variant}-L{L}"
    out.insert(0, "variant", name)
    out["jaar"] = (out.signal_time - pd.Timedelta(hours=SERVER_OFFSET_H)).dt.year
    return out


def summary(trades: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Kerncijfers per groep, alleen over echt getradeerde (gesloten) setups."""
    t = trades[trades.status == "gesloten"].sort_values("entry_time")
    rows = []
    for key, g in t.groupby(by, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        rows.append({**dict(zip(by, key)), **metrics(g.r_net)})
    return pd.DataFrame(rows)


IN_SAMPLE_END = pd.Timestamp("2025-01-01")   # spec §8: alles hiervoor = in-sample


def in_sample(m1: pd.DataFrame) -> pd.DataFrame:
    """Snijdt de out-of-sample periode weg (servertijd < 1 jan 2025)."""
    return m1[m1.index < IN_SAMPLE_END]


# ---------------- Placebo (spec v0.2 §6) ----------------

def placebo(md: MarketData, tf: str, risk_atr: np.ndarray, n: int = 3000, seed: int = 1,
            max_cost_r: float | None = None, frictionless: bool = False) -> pd.DataFrame:
    """
    Willekeurige instapmomenten (01–21u BE) en richting, met een SL-afstand getrokken uit
    `risk_atr` (de echte SL-groottes van de variant, in ATR), marktorder, TP 2R, zelfde motor.
    Zonder dagstop (elke placebo-trade telt). Dient als maatstaf: een echte edge moet hier
    duidelijk boven zitten.
    """
    rng = np.random.default_rng(seed)
    ins = md.ins
    if frictionless:
        ins = replace(ins, point=0.0, min_spread=0.0, slip=0.0, commission=0.0, swap=0.0, rollover_min_spread=0.0)
    b, a, _ = md.tf_bars(tf)
    hrs = (b.index - pd.Timedelta(hours=SERVER_OFFSET_H)).hour
    ok = np.where(a.notna().to_numpy() & (hrs >= 1) & (hrs < 21))[0]
    pick = np.sort(rng.choice(ok, min(n, len(ok)), replace=False))
    plans = []
    for k in pick:
        t = b.index[k] + pd.Timedelta(tf)
        at = float(a.iloc[k]); px = float(b["close"].iloc[k])
        dist = float(rng.choice(risk_atr)) * at
        long = rng.random() < 0.5
        plans.append(OrderPlan(LONG if long else "SHORT", t, "market",
                               px - dist if long else px + dist, at, market=md.name,
                               max_cost_r=max_cost_r))
    return run_portfolio(plans, {md.name: M1(md.m1, ins)}, {md.name: ins}, day_stop_r=-1e9,
                         server_offset_h=SERVER_OFFSET_H)
