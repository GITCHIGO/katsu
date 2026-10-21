"""De drie vastgelegde setups: filters doen wat ze moeten doen, en komen overeen met de dashboard-presets."""
import re

import pandas as pd

from katsu.presets import PRESETS, preset_mask


def _row(**kw):
    base = {"markt": "EURUSD", "soort": "FVG", "sweep_dag": "nee", "fvg_nummer": "eerste", "trend_m15": "tegen",
            "trend_h1": "neutraal", "sessie": "Londen", "weekdag": "di", "nfp_dag": "nee", "volatiliteit": "hoog",
            "amd_variant": "n.v.t.", "trend_d1": "mee", "kosten": "<0,1R", "zone_tf": "n.v.t.", "zone_entry": "n.v.t.",
            "sweep_azie": "nee", "trend_h4": "mee"}
    base.update(kw)
    return base


def test_test1_filters():
    df = pd.DataFrame([_row(), _row(fvg_nummer="tweede"), _row(trend_m15="mee"), _row(markt="US500"),
                       _row(soort="IFVG"), _row(volatiliteit="normaal")])
    assert list(preset_mask(df, "Test #1 (FVG)")) == [True, False, False, False, False, False]
    # andere markten testen kan apart
    assert list(preset_mask(df, "Test #1 (FVG)", markets=["US500"])) == [False, False, False, True, False, False]


def test_amd_en_zone():
    df = pd.DataFrame([_row(soort="AMD", amd_variant="C2-E1", sweep_dag="ja", markt="XAUUSD"),
                       _row(soort="AMD", amd_variant="C2-E2", sweep_dag="ja", markt="XAUUSD"),
                       _row(soort="Zone", markt="GBPUSD", zone_tf="M15", zone_entry="rand", sweep_dag="ja",
                            sweep_azie="ja", trend_m15="tegen", trend_h4="neutraal", sessie="New York"),
                       _row(soort="Zone", markt="GBPUSD", zone_tf="H1", zone_entry="rand", sweep_dag="ja",
                            sweep_azie="ja", trend_m15="tegen", trend_h4="neutraal")])
    assert list(preset_mask(df, "AMD-extra (#386)")) == [True, False, False, False]
    assert list(preset_mask(df, "Zone GBPUSD")) == [False, False, True, False]


def test_zelfde_als_dashboard():
    """De presets in dashboard/page.html moeten letterlijk dezelfde waarden bevatten."""
    page = open("dashboard/page.html", encoding="utf8").read()
    block = page[page.index("const PRESETS = ["):page.index("let activePreset")]
    for name, p in PRESETS.items():
        seg = block[block.index(name):]
        seg = seg[:seg.index("} },") + 1] if "} }," in seg else seg
        for col, vals in p["f"].items():
            m = re.search(col + r': \[([^\]]*)\]', seg)
            assert m, (name, col)
            assert re.findall(r'"([^"]*)"', m.group(1)) == vals, (name, col)
        mk = re.search(r'markt: \[([^\]]*)\]', seg)
        assert re.findall(r'"([^"]*)"', mk.group(1)) == p["markt"], name
