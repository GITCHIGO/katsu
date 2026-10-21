"""
Vooruit-test (docs/vooruittest_plan.md): de drie vastgelegde setups (katsu/presets.py) op een venster nieuwe data,
met exact dezelfde code als het dashboard. Rapport: algemeen, per setup, per setup × pair, stopregels, alle trades.
Gebruik: python -m scripts.vooruittest <datamap> <uitmap> [start] [einde] [label]
  start standaard 2026-10-10 (servertijd); einde standaard: einde van de data.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

from katsu.dashboard_calc import clustered_t, one_at_a_time, usd
from katsu.presets import PRESETS, preset_mask
import scripts.dashboard_build as DB
from scripts.dashboard_amd import amd_rows
from scripts.dashboard_export import prepare
from scripts.dashboard_zones import zone_rows
from scripts.eindtest_gfvg import load_full

START = "2026-10-10"
LOTS = {"EURUSD": 0.10, "GBPUSD": 0.10, "XAUUSD": 0.02, "XAGUSD": 0.02, "US500": 1.0}
INFO_MARKETS = ("XAGUSD", "US500")               # test #1 ter info op markten waar hij niet op gekozen is
DIGITS = {"EURUSD": 5, "GBPUSD": 5, "XAUUSD": 2, "XAGUSD": 3, "US500": 2}


def stop_status(n, mean):
    """Stopregels per setup (plan §5)."""
    if n >= 40 and mean < 0:
        return "STOP (na 40 trades onder 0)"
    if n >= 20 and mean < -0.3:
        return "STOP (na 20 trades onder −0,3R)"
    if n >= 150 and mean >= 0.10:
        return "kandidaat voor klein echt geld (na 150 trades ≥ +0,10R; t nakijken)"
    return "loopt"


def build_rows(folder, start, end):
    t0, t1 = pd.Timestamp(start), (pd.Timestamp(end) if end else None)
    mask = lambda t: np.asarray((t >= t0) & ((t < t1) if t1 is not None else True))
    rng = np.random.default_rng(20261021)
    need = {}
    for name, p in PRESETS.items():
        for m in p["markt"]:
            need.setdefault(m, set()).add(p["f"]["soort"][0])
    for m in INFO_MARKETS:
        need.setdefault(m, set()).add("FVG")
    parts = []
    for mkt, kinds in need.items():
        try:
            bars = load_full(folder, mkt)
        except (IndexError, FileNotFoundError):
            print(f"{mkt}: geen data in {folder}, overgeslagen"); continue
        if "FVG" in kinds:
            parts.append(DB.run_market(folder, mkt, rng, mask))
        if "AMD" in kinds:
            parts.append(amd_rows(bars, mkt, mask, rng))
        if "Zone" in kinds:
            parts.append(zone_rows(bars, mkt, mask, rng))
    df = prepare(pd.concat(parts, ignore_index=True))
    df["data_einde"] = df["markt"].map({m: load_full(folder, m).index[-1] for m in df["markt"].unique()})
    return df


def setup_trades(df, name, markets=None):
    g = df[preset_mask(df, name, markets)].copy()
    g = g.sort_values("t_sig", kind="stable")
    tr = one_at_a_time(g)
    tr = tr.assign(setup=name, loopt=tr["uitkomst"].eq("EINDE_DATA"))
    return tr


def summary(tr):
    c = tr[~tr.loopt]
    n = len(c)
    if n == 0:
        return {"trades": 0, "winst": 0, "verlies": 0, "winrate": None, "gem_R": None, "totaal_R": 0.0,
                "gem_win_R": None, "gem_verlies_R": None, "pips": 0.0, "usd": 0.0, "t": None, "lopend": int(tr.loopt.sum())}
    w = c.r_net > 0
    v = usd(c, LOTS)
    return {"trades": n, "winst": int(w.sum()), "verlies": int((~w).sum()), "winrate": float(w.mean()),
            "gem_R": float(c.r_net.mean()), "totaal_R": float(c.r_net.sum()),
            "gem_win_R": float(c.r_net[w].mean()) if w.any() else None,
            "gem_verlies_R": float(c.r_net[~w].mean()) if (~w).any() else None,
            "pips": float(c.pips.sum()), "usd": float(v.sum()),
            "t": float(clustered_t(c.r_net.to_numpy(), c.week.to_numpy())) if n > 2 else None,
            "lopend": int(tr.loopt.sum())}


def report(df, start, end, label):
    setups = {name: setup_trades(df, name) for name in PRESETS}
    info = setup_trades(df, "Test #1 (FVG)", list(INFO_MARKETS))
    alle = pd.concat(setups.values(), ignore_index=True)
    rep = {"label": label, "start": str(start), "einde": str(end or df["data_einde"].max()),
           "lots": LOTS, "algemeen": summary(alle), "setups": {}, "info_test1_extra_markten": {}}
    for name, tr in setups.items():
        s = summary(tr)
        s["stopregel"] = stop_status(s["trades"], s["gem_R"] if s["gem_R"] is not None else 0)
        s["per_pair"] = {m: summary(tr[tr.markt == m]) for m in PRESETS[name]["markt"]}
        rep["setups"][name] = s
    rep["info_test1_extra_markten"] = {m: summary(info[info.markt == m]) for m in INFO_MARKETS}
    cols = ["setup", "markt", "richting", "fill_time", "fill_px", "sl_px", "tp_px", "exit_time", "exit_px", "uitkomst",
            "r_net", "pips", "loopt"]
    lijst = pd.concat([alle, info.assign(setup="Test #1 (info, " + info.markt + ")")], ignore_index=True)
    lijst = lijst.sort_values("fill_time")[cols].copy()
    lijst["usd"] = usd(lijst.assign(**{"risk_pips": np.nan}), LOTS).round(2)
    rep["trades"] = json.loads(lijst.to_json(orient="records", date_format="iso"))
    return rep


if __name__ == "__main__":
    folder, out = sys.argv[1], sys.argv[2]
    start = sys.argv[3] if len(sys.argv) > 3 else START
    end = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
    label = sys.argv[5] if len(sys.argv) > 5 else "vooruit-test"
    os.makedirs(out, exist_ok=True)
    df = build_rows(folder, start, end)
    rep = report(df, start, end, label)
    path = os.path.join(out, f"vooruittest_{start}_{(end or 'einde')}.json")
    with open(path, "w") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1, default=float)
    a = rep["algemeen"]
    print(f"{label}: {a['trades']} trades, winrate {a['winrate']}, gem {a['gem_R']} R · {path}")
    for name, s in rep["setups"].items():
        print(f"  {name}: {s['trades']} trades, winrate {s['winrate']}, gem {s['gem_R']} R, lopend {s['lopend']} · "
              + ", ".join(f"{m} {v['trades']}/{v['winrate']}" for m, v in s["per_pair"].items()))
