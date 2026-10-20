"""
Zet de dashboard-data om naar compacte bestanden voor de pagina (één per markt, base64 van gzip-JSON).
Kolomgewijs: elke categorie als codes + woordenlijst, getallen als gehele getallen (R × 1000, pips × 10).
Gebruik: python -m scripts.dashboard_export <uitmap> <dashboard_events_*.pkl> [...]
(meerdere periodes worden samengevoegd; de pagina kiest zelf van–tot)
"""
import base64
import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

from scripts.gfvg_test import INS

ORDER = {
    "markt": ["EURUSD", "GBPUSD", "XAUUSD"], "soort": ["FVG", "IFVG", "AMD", "Zone"],
    "zone_tf": ["M15", "H1", "H4", "n.v.t."], "zone_entry": ["rand", "38,2", "n.v.t."], "zone_fvg": ["ja", "nee", "n.v.t."], "richting": ["long", "short"],
    "amd_variant": ["C1-E1", "C1-E2", "C2-E1", "C2-E2", "n.v.t."], "amd_dag": ["mee", "tegen", "geen"],
    "breuk": ["geen", "BOS", "CHoCH", "breuk uit neutraal", "n.v.t."], "sweep_swing": ["ja", "nee", "n.v.t."],
    "sweep_dag": ["ja", "nee", "onbekend"], "sweep_azie": ["ja", "nee", "vóór einde Azië"],
    "order_block": ["ja", "nee", "n.v.t."], "fvg_nummer": ["eerste", "tweede", "derde+", "n.v.t."],
    "trend_m15": ["mee", "tegen", "neutraal"], "trend_h1": ["mee", "tegen", "neutraal"],
    "trend_h4": ["mee", "tegen", "neutraal"], "trend_d1": ["mee", "tegen", "neutraal"],
    "premium_discount": ["mee", "tegen", "onbekend"],
    "sessie": ["Azië", "Londen", "overlap", "New York", "nacht"], "uur": [str(h) for h in range(24)],
    "weekdag": ["ma", "di", "wo", "do", "vr", "za", "zo"], "silver_bullet": ["ja", "nee"],
    "gat_atr": ["<0,25", "0,25–0,5", "0,5–1", "1–2", ">2", "onbekend"],
    "displacement": ["<0,5", "0,5–1", "1–2", ">2", "onbekend"], "candle3_vol": ["<25%", "25–50%", "≥50%", "onbekend"],
    "sl_atr": ["<1", "1–2", "2–3", ">3", "onbekend"], "rr_plan": ["<1", "1–1,5", "1,5–2", "≥2", "onbekend"],
    "kosten": ["<0,1R", "0,1–0,2R", ">0,2R", "onbekend"], "volatiliteit": ["laag", "normaal", "hoog", "onbekend"],
    "nfp_dag": ["ja", "nee"], "vulling": ["gevuld", "TP eerst (geannuleerd)", "niet gevuld", "ongeldig"],
    "uitkomst": ["TP", "SL", "MAX_DUUR", "EINDE_DATA", "—"],
}
NUM = {"r_net": 1000, "r_free": 1000, "r_placebo": 1000, "r_placebo_free": 1000, "pips": 10,
       "risk_pips": 10, "risk_pips_free": 10}
MISSING = -2147483648


def prepare(df):
    df = df.copy()
    df["uur"] = df["uur"].astype(int).astype(str)
    df["vulling"] = df["vulling"].where(df["vulling"].isin(ORDER["vulling"]), "ongeldig")
    df["uitkomst"] = df["uitkomst"].fillna("—").replace({"EINDE_DAG": "MAX_DUUR"})
    df["rr_plan"] = df["rr_plan"].replace({"2": "≥2"})              # FVG: precies 2 (plafond); AMD: 2 of meer
    for c, v in (("amd_variant", "n.v.t."), ("amd_dag", "geen"), ("zone_tf", "n.v.t."), ("zone_entry", "n.v.t."),
                 ("zone_fvg", "n.v.t.")):
        if c not in df:
            df[c] = v
        df[c] = df[c].fillna(v)
    cost = {m: (INS[m].min_spread + 2 * INS[m].slip + INS[m].commission) for m in ORDER["markt"]}
    kr = df["markt"].map(cost) / df["risk_plan"].where(df["risk_plan"] > 0)
    df["kosten"] = np.where(kr.isna(), "onbekend", np.where(kr < 0.1, "<0,1R", np.where(kr < 0.2, "0,1–0,2R", ">0,2R")))
    return df


def encode(df):
    cols = {}
    for c, vals in ORDER.items():
        idx = {v: i for i, v in enumerate(vals)}
        codes = df[c].astype(str).map(idx)
        if codes.isna().any():
            raise ValueError(f"onbekende waarde in {c}: {set(df[c][codes.isna()])}")
        cols[c] = codes.astype(int).tolist()
    for c, sc in NUM.items():
        v = df[c].to_numpy(float)
        cols[c] = np.where(np.isfinite(v), np.rint(v * sc), MISSING).astype(np.int64).tolist()
    cols["jaar"] = df["jaar"].astype(int).tolist()
    cols["week"] = df["week"].astype(int).tolist()
    cols["ts"] = _minutes(df["t_sig"])
    for c in ("fill_time", "exit_time"):                      # minuten sinds 1970; ontbrekend = MISSING
        cols[c] = _minutes(df[c]) if c in df else [MISSING] * len(df)
    return {"n": len(df), "order": ORDER, "scale": NUM, "missing": MISSING, "cols": cols}


def _minutes(s):
    t = pd.to_datetime(s)
    v = t.values.astype("datetime64[m]").astype(np.int64)
    return np.where(t.isna().to_numpy(), MISSING, v).astype(np.int64).tolist()


def period_meta(df):
    """Periodegegevens voor de pagina: label, jaren en de maanden waarin setups zitten (JJJJ-MM)."""
    years = sorted(int(y) for y in df["jaar"].unique())
    months = sorted(pd.to_datetime(df["t_sig"]).dt.strftime("%Y-%m").unique().tolist())
    return {"label": f"{years[0]}–{years[-1]}" if len(years) > 1 else str(years[0]), "jaren": years,
            "maanden": months, "einde": str(pd.to_datetime(df["t_sig"]).max().date())}


def main(outdir, *pkls):
    os.makedirs(outdir, exist_ok=True)
    df = prepare(pd.concat([pd.read_pickle(p) for p in pkls], ignore_index=True))
    meta = period_meta(df)
    for m in ORDER["markt"]:
        body = encode(df[df.markt == m].sort_values("t_sig", kind="stable"))
        body["periode"] = meta
        blob = base64.b64encode(gzip.compress(json.dumps(body, separators=(",", ":")).encode(), 9)).decode()
        with open(os.path.join(outdir, f"{m}.txt"), "w") as fh:
            fh.write(blob)
        print(m, body["n"], "setups,", round(len(blob) / 1e6, 1), "MB")


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
