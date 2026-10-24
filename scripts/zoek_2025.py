"""
Spec v0.9 (docs/spec_v0.9_zoeken.md): automatisch zoeken op 2025 in de rijen van het bouwstenen-dashboard,
controle op jan – 9 okt 2026. Gebruik: python -m scripts.zoek_2025 <map met EURUSD.txt GBPUSD.txt XAUUSD.txt> <uit.json>
"""
from __future__ import annotations

import base64
import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

from katsu.dashboard_calc import clustered_t

MARKETS = ["EURUSD", "GBPUSD", "XAUUSD"]
SKIP = {"markt", "soort", "vulling", "uitkomst"}       # geen filters (markt apart, soort = vertrekpunt)
MIN_TRADES, MAX_STEPS = 80, 8


def load(folder):
    parts, order = [], None
    for m in MARKETS:
        d = json.loads(gzip.decompress(base64.b64decode(open(os.path.join(folder, m + ".txt")).read().strip())))
        order, miss, sc = d["order"], d["missing"], d["scale"]
        df = pd.DataFrame(d["cols"])
        for c in ("r_net", "r_free", "r_placebo_free"):
            df[c] = np.where(df[c] == miss, np.nan, df[c] / sc[c])
        for c in ("fill_time", "exit_time"):
            df[c] = np.where(df[c] == miss, np.nan, df[c]).astype(float)
        parts.append(df)
    df = pd.concat(parts, ignore_index=True)
    key = np.where(np.isnan(df["fill_time"]), df["ts"], df["fill_time"])
    df = df.iloc[np.argsort(key, kind="stable")].reset_index(drop=True)
    t = pd.to_datetime((df["ts"] - 1) * 60, unit="s")           # maand van het signaal (zoals het dashboard)
    df["periode"] = np.where(t >= "2026-01-01", "2026", np.where(t >= "2025-01-01", "2025", "voor_2025"))
    return df, order


def one_at_a_time(df: pd.DataFrame) -> pd.DataFrame:
    """Gevulde trades; per markt pas een nieuwe als de vorige gesloten is (rijen staan op vulvolgorde)."""
    g = df[(df["vulling"] == 0) & df["r_net"].notna()]
    last, keep = {}, []
    m, f, x = g["markt"].to_numpy(), g["fill_time"].to_numpy(), g["exit_time"].to_numpy()
    for i in range(len(g)):
        if f[i] < last.get(m[i], -np.inf):
            continue
        last[m[i]] = x[i] if not np.isnan(x[i]) else f[i]
        keep.append(i)
    return g.iloc[keep]


def stats(df: pd.DataFrame) -> dict:
    tr = one_at_a_time(df)
    if len(tr) < 2:
        return {"n": len(tr), "gem": np.nan, "t": np.nan}
    x = tr["r_net"].to_numpy()
    return {"n": int(len(tr)), "gem": float(x.mean()), "t": clustered_t(x, tr["week"].to_numpy()),
            "win": float((x > 0).mean()), "zonder_kosten": float(tr["r_free"].mean()),
            "placebo_zk": float(tr["r_placebo_free"].mean()), "totaal": float(x.sum()),
            "per_markt": {MARKETS[k]: [int(len(v)), round(float(v["r_net"].mean()), 3)] for k, v in tr.groupby("markt")}}


def describe(allowed: dict, order: dict) -> dict:
    return {f: [order[f][c] for c in sorted(v)] for f, v in allowed.items()}


def search(df, order, soort: str, counter: list):
    """Greedy: elke stap de 'chip uit' met de hoogste t op 2025 (≥ MIN_TRADES trades), max MAX_STEPS stappen."""
    base = df[(df["soort"] == order["soort"].index(soort)) & (df["periode"] == "2025")]
    allowed = {"markt": set(range(len(MARKETS)))}
    cur = base
    best = stats(cur); counter[0] += 1
    steps = []
    feats = [f for f in order if f not in SKIP]
    for _ in range(MAX_STEPS):
        cand = None
        options = [("markt", k) for k in sorted(allowed["markt"])] if len(allowed["markt"]) > 1 else []
        for f in feats:
            present = set(np.unique(cur[f]))
            vals = allowed.get(f, present)
            if len(vals & present) <= 1:
                continue
            options += [(f, v) for v in sorted(vals & present) if order[f][v] != "onbekend"]
        for f, v in options:
            sub = cur[cur[f] != v]
            s = stats(sub); counter[0] += 1
            if s["n"] >= MIN_TRADES and np.isfinite(s["t"]) and s["t"] > best["t"] and (cand is None or s["t"] > cand[2]["t"]):
                cand = (f, v, s)
        if cand is None:
            break
        f, v, s = cand
        allowed.setdefault(f, set(np.unique(cur[f])))
        allowed[f] = allowed[f] - {v}
        cur = cur[cur[f] != v]
        best = s
        steps.append(f"{f} ≠ {order[f][v]}  → 2025: n {s['n']}, gem {s['gem']:+.3f}R, t {s['t']:.2f}")
    return allowed, steps, best


def apply(df, order, soort, allowed, periode):
    sub = df[(df["soort"] == order["soort"].index(soort)) & (df["periode"] == periode)]
    for f, vals in allowed.items():
        sub = sub[sub[f].isin(list(vals))]
    return sub


def main(folder, out):
    df, order = load(folder)
    counter = [0]
    res = {}
    for soort in ("FVG", "IFVG", "AMD", "Zone"):
        allowed, steps, s25 = search(df, order, soort, counter)
        s26 = stats(apply(df, order, soort, allowed, "2026"))
        sbg = stats(apply(df, order, soort, allowed, "voor_2025"))
        ok = (s26["n"] >= 30 and s26["gem"] >= 0.10 and s26.get("zonder_kosten", -9) > s26.get("placebo_zk", 9)
              and sbg.get("gem", -9) > -0.05)
        res[soort] = {"filters": describe(allowed, order), "stappen": steps, "2025": s25, "2026": s26,
                      "voor_2025": sbg, "geslaagd": bool(ok)}
    res["_pogingen"] = counter[0]
    with open(out, "w") as fh:
        json.dump(res, fh, indent=1, ensure_ascii=False, default=float)
    print(json.dumps(res, indent=1, ensure_ascii=False, default=float))


if __name__ == "__main__":
    main(*sys.argv[1:3])
