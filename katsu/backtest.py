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
from katsu.data import resample
from katsu.execution import M1, Instrument, entry_level_variant_b, make_plan, run_portfolio
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

    def setups(self, tf: str, L: int, block: str = "sweep") -> list:
        """block = "sweep" (bouwsteen 1, sweep + CHoCH) of "bos" (bouwsteen 2)."""
        key = (tf, L, block)
        if key not in self._setups:
            b, _, _ = self.tf_bars(tf)
            if block == "sweep":
                self._setups[key] = detect_setups(b, tf, self.h1_trend, L=L)
            elif block == "bos":
                self._setups[key] = detect_bos(b, tf, self.h1_trend, L=L)
            else:
                raise ValueError(f"onbekende bouwsteen: {block}")
        return self._setups[key]


# ---------------- Eén variant ----------------

def run_variant(markets: list[MarketData], tf: str, variant: str, L: int,
                slip: dict | None = None, day_stop_r: float = -2.0,
                block: str = "sweep") -> pd.DataFrame:
    """
    Speelt één variant af over alle markten samen. `slip` = {markt: slippage in prijs}
    (zonder: de basis uit het Instrument). Geeft één rij per setup: context + uitkomst.
    """
    plans, ctx_rows, data, inss = [], {}, {}, {}
    for md in markets:
        ins = replace(md.ins, slip=slip[md.name]) if slip else md.ins
        inss[md.name] = ins
        data[md.name] = M1(md.m1, ins)
        b, a, pct = md.tf_bars(tf)
        for s in md.setups(tf, L, block):
            if block == "bos":
                plans.append(make_bos_plan(s, tf, a, variant, ins))
                ctx = bos_context(s, b, a, pct, md.ctx_trend(s.signal_time))
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
    prefix = "BOS-" if block == "bos" else ""
    out.insert(0, "variant", f"{prefix}{TF_NAMES.get(tf, tf)}-{variant}-L{L}")
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
