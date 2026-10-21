"""
Live-scan (spec §2): na elke gesloten M15-candle dezelfde rijen bouwen als de vooruit-test (scripts/vooruittest.rows_for)
op de gesloten candles uit MT5, en de nieuwe signalen van de drie vastgelegde setups (katsu/presets.py) teruggeven.

Een signaal telt alleen als de backtest op dat moment nog niets met de order gedaan zou hebben (status 'geen_data' of
'niet_gevuld'). Na een onderbreking (VPS herstart) worden gemiste signalen dus alleen nog geplaatst als de order in de
backtest op dit moment nog zou openstaan; anders worden ze gelogd als 'gemist'.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from katsu.presets import PRESETS, preset_mask

STEP = pd.Timedelta("15min")
HISTORY_MONTHS = 24          # getest: 18 en 24 maanden geven exact dezelfde setups als de backtest vanaf 2023
SETUPS = {                   # code, magic number (MT5), soort
    "Test #1 (FVG)": ("T1", 710101),
    "AMD-extra (#386)": ("AMD", 710102),
    "Zone GBPUSD": ("ZONE", 710103),
}
SHORT = {"EURUSD": "EUR", "GBPUSD": "GBP", "XAUUSD": "XAU"}
OPEN_STATUS = ("geen_data", "niet_gevuld")
FEATURES = ("soort", "richting", "sweep_dag", "fvg_nummer", "trend_m15", "trend_h1", "trend_h4", "trend_d1", "sessie",
            "weekdag", "volatiliteit", "amd_variant", "zone_tf", "zone_entry", "sweep_azie", "kosten", "nfp_dag")


@dataclass
class Signal:
    key: str                     # uniek en elke scan hetzelfde: setup|markt|t_sig|richting|limiet
    setup: str
    market: str
    direction: str               # LONG / SHORT
    t_sig: pd.Timestamp          # einde van de signaalcandle (servertijd)
    kind: str                    # limit / market
    anchor: float
    atr: float
    limit: float | None
    tp_plan: float | None        # vaste TP (oude high); bij zones: voorlopig, definitief bij de vulling
    cancel: float | None
    max_rr: float | None
    valid_until: pd.Timestamp | None   # tijdsgrens (AMD, zones)
    valid_bars: int | None             # FVG: geldig voor zoveel M15-candles na de signaalcandle
    close_eod: bool                    # AMD: sluiten op de dagclose
    tp_mode: str                       # vast / zone_bij_vulling
    leg_high: float | None
    features: dict = field(default_factory=dict)

    @property
    def group(self) -> tuple:
        return (self.setup, self.market)

    def as_dict(self) -> dict:
        d = asdict(self)
        for k in ("t_sig", "valid_until"):
            d[k] = None if d[k] is None else str(d[k])
        return d


def _f(x):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if np.isfinite(x) else None


def signal_from_row(r, setup: str) -> Signal:
    kind = str(r["plan_kind"])
    limit = _f(r.get("plan_limit"))
    t_sig = pd.Timestamp(r["t_sig"])
    soort = r["soort"]
    tp_mode = "zone_bij_vulling" if r.get("plan_tp_mode") == "zone_bij_vulling" else "vast"
    valid_bars = None
    valid_until = None
    if soort in ("FVG", "IFVG"):
        valid_bars = int(r["plan_valid_bars"])          # backtest: index s + 480 (telt candles, niet tijd)
    elif kind != "market":
        valid_until = pd.Timestamp(r["plan_valid_until"])
    lim_txt = "mkt" if limit is None else f"{limit:.6f}"
    return Signal(
        key=f"{setup}|{r['markt']}|{t_sig:%Y-%m-%d %H:%M}|{r['plan_richting']}|{lim_txt}",
        setup=setup, market=r["markt"], direction=str(r["plan_richting"]), t_sig=t_sig, kind=kind,
        anchor=float(r["plan_anchor"]), atr=float(r["plan_atr"]), limit=limit,
        tp_plan=None if tp_mode == "zone_bij_vulling" else _f(r.get("plan_tp")),
        cancel=_f(r.get("plan_cancel")), max_rr=_f(r.get("plan_max_rr")),
        valid_until=valid_until, valid_bars=valid_bars, close_eod=bool(pd.notna(r.get("plan_close_eod")) and bool(r.get("plan_close_eod"))),
        tp_mode=tp_mode, leg_high=_f(r.get("plan_leg_high")),
        features={k: str(r[k]) for k in FEATURES if k in r and pd.notna(r[k])})


def closed_bars(bars: pd.DataFrame, server_now: pd.Timestamp) -> pd.DataFrame:
    """Alleen gesloten candles (werkregel 4): de candle die nog loopt valt weg."""
    return bars[bars.index + STEP <= server_now]


def scan(bars_by_market: dict, since: pd.Timestamp, until: pd.Timestamp, rows_for=None):
    """
    Nieuwe signalen met since < t_sig <= until. bars_by_market: alleen gesloten M15-candles.
    Geeft (signalen, gemist, alle rijen in het venster).
    """
    if rows_for is None:
        from scripts.vooruittest import rows_for
    lo = since - pd.Timedelta(days=3)       # ruim: AMD filtert per dag, FVG op de signaalcandle
    df = rows_for(bars_by_market, lambda t: np.asarray(t >= lo), np.random.default_rng(20261021))
    if len(df) == 0:
        return [], [], df
    win = df[(df.t_sig > since) & (df.t_sig <= until)]
    signals, missed = [], []
    for name in PRESETS:
        sel = win[preset_mask(win, name)]
        for _, r in sel.sort_values("t_sig", kind="stable").iterrows():
            sg = signal_from_row(r, name)
            (signals if r["status"] in OPEN_STATUS else missed).append(sg)
    return signals, missed, win
