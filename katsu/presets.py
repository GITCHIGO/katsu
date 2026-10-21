"""
De drie vastgelegde setups voor de vooruit-test (docs/vooruittest_plan.md). Zelfde filters als de presets in het
dashboard (dashboard/page.html, PRESETS) — wie hier iets wijzigt, wijzigt ook daar en schrijft een nieuwe planversie.
Een setup = soort + filters op de dashboardkenmerken + markten. Waarden zoals ze in de dashboarddata staan.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PRESETS = {
    "Test #1 (FVG)": {
        "markt": ["EURUSD", "GBPUSD", "XAUUSD"],
        "f": {"soort": ["FVG"], "sweep_dag": ["nee", "onbekend"], "fvg_nummer": ["eerste", "derde+"],
              "trend_m15": ["tegen"], "trend_h1": ["tegen", "neutraal"], "sessie": ["Azië", "Londen", "overlap"],
              "weekdag": ["ma", "di", "wo", "do", "vr"], "nfp_dag": ["nee"], "volatiliteit": ["hoog", "onbekend"]},
    },
    "AMD-extra (#386)": {
        "markt": ["EURUSD", "XAUUSD"],
        "f": {"soort": ["AMD"], "amd_variant": ["C1-E2", "C2-E1"], "sweep_dag": ["ja", "onbekend"],
              "trend_d1": ["mee", "neutraal"], "kosten": ["<0,1R", "onbekend"]},
    },
    "Zone GBPUSD": {
        "markt": ["GBPUSD"],
        "f": {"soort": ["Zone"], "zone_tf": ["M15", "H4", "n.v.t."], "zone_entry": ["rand", "n.v.t."],
              "sweep_dag": ["ja", "onbekend"], "sweep_azie": ["ja"], "trend_m15": ["tegen", "neutraal"],
              "trend_h4": ["tegen", "neutraal"], "trend_d1": ["mee", "neutraal"],
              "sessie": ["Azië", "Londen", "overlap", "New York"]},
    },
}


def preset_mask(df: pd.DataFrame, name: str, markets: list[str] | None = None) -> np.ndarray:
    """True voor de rijen die bij de setup horen. markets=None: de vastgelegde markten van de setup."""
    p = PRESETS[name]
    m = df["markt"].isin(markets if markets is not None else p["markt"]).to_numpy().copy()
    for col, vals in p["f"].items():
        m &= df[col].astype(str).isin(vals).to_numpy()
    return m
