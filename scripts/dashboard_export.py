"""
Zet de dashboard-data om naar compacte bestanden voor de pagina (één per markt, base64 van gzip-JSON).
Kolomgewijs: elke categorie als codes + woordenlijst, getallen als gehele getallen (R × 1000, pips × 10).
Gebruik: python -m scripts.dashboard_export <dashboard_events.pkl> <uitmap>
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
    "markt": ["EURUSD", "GBPUSD", "XAUUSD"], "soort": ["FVG", "IFVG"], "richting": ["long", "short"],
    "breuk": ["geen", "BOS", "CHoCH", "breuk uit neutraal"], "sweep_swing": ["ja", "nee"],
    "sweep_dag": ["ja", "nee", "onbekend"], "sweep_azie": ["ja", "nee", "vóór einde Azië"],
    "order_block": ["ja", "nee"], "fvg_nummer": ["eerste", "tweede", "derde+"],
    "trend_m15": ["mee", "tegen", "neutraal"], "trend_h1": ["mee", "tegen", "neutraal"],
    "trend_h4": ["mee", "tegen", "neutraal"], "trend_d1": ["mee", "tegen", "neutraal"],
    "premium_discount": ["mee", "tegen", "onbekend"],
    "sessie": ["Azië", "Londen", "overlap", "New York", "nacht"], "uur": [str(h) for h in range(24)],
    "weekdag": ["ma", "di", "wo", "do", "vr", "za", "zo"], "silver_bullet": ["ja", "nee"],
    "gat_atr": ["<0,25", "0,25–0,5", "0,5–1", "1–2", ">2", "onbekend"],
    "displacement": ["<0,5", "0,5–1", "1–2", ">2", "onbekend"], "candle3_vol": ["<25%", "25–50%", "≥50%", "onbekend"],
    "sl_atr": ["<1", "1–2", "2–3", ">3", "onbekend"], "rr_plan": ["<1", "1–1,5", "1,5–2", "2", "onbekend"],
    "kosten": ["<0,1R", "0,1–0,2R", ">0,2R", "onbekend"], "volatiliteit": ["laag", "normaal", "hoog", "onbekend"],
    "nfp_dag": ["ja", "nee"], "vulling": ["gevuld", "TP eerst (geannuleerd)", "niet gevuld", "ongeldig"],
    "uitkomst": ["TP", "SL", "MAX_DUUR", "EINDE_DATA", "—"],
}
NUM = {"r_net": 1000, "r_free": 1000, "r_placebo": 1000, "r_placebo_free": 1000, "pips": 10}
MISSING = -2147483648


def prepare(df):
    df = df.copy()
    df["uur"] = df["uur"].astype(int).astype(str)
    df["vulling"] = df["vulling"].where(df["vulling"].isin(ORDER["vulling"]), "ongeldig")
    df["uitkomst"] = df["uitkomst"].fillna("—")
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
    cols["ts"] = (df["t_sig"].values.astype("datetime64[m]").astype(np.int64)).tolist()
    return {"n": len(df), "order": ORDER, "scale": NUM, "missing": MISSING, "cols": cols}


def main(pkl, outdir):
    os.makedirs(outdir, exist_ok=True)
    df = prepare(pd.read_pickle(pkl))
    for m in ORDER["markt"]:
        body = encode(df[df.markt == m].sort_values("t_sig"))
        blob = base64.b64encode(gzip.compress(json.dumps(body, separators=(",", ":")).encode(), 9)).decode()
        with open(os.path.join(outdir, f"{m}.txt"), "w") as fh:
            fh.write(blob)
        print(m, body["n"], "setups,", round(len(blob) / 1e6, 1), "MB")


if __name__ == "__main__":
    main(*sys.argv[1:3])
