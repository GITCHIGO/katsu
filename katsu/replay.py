"""
Episodes voor de KATSU Replay (docs/replay_spec.md): stukken M1-data, compact gecodeerd als gzip-JSON (gepubliceerd als base64-tekst, omdat artifacts geen binaire bestanden serveren).

Codering per candle i (prijzen als gehele getallen in 'points'):
  o[i] = open − close(i−1)   (voor i = 0: open − base)
  h[i] = high − max(open, close)      l[i] = min(open, close) − low      c[i] = close − open
  dt[i] = minuten sinds de vorige candle (dt[0] = 0; t0 = servertijd van candle 0 in minuten sinds 1970)
  s[i] = spread in points (zoals MT5 die bewaart)
"""
from __future__ import annotations

import gzip
import json

import numpy as np
import pandas as pd

POINT = {"EURUSD": 0.00001, "XAUUSD": 0.01}
DIGITS = {"EURUSD": 5, "XAUUSD": 2}


def encode(m1: pd.DataFrame, sym: str, eid: str, start_time: pd.Timestamp) -> bytes:
    p = POINT[sym]
    o, h, l, c = (np.rint(m1[x].to_numpy(float) / p).astype(np.int64) for x in ("open", "high", "low", "close"))
    mins = (m1.index.values.astype("datetime64[m]").astype(np.int64))
    prevc = np.r_[o[0], c[:-1]]
    body = {
        "id": eid, "sym": sym, "digits": DIGITS[sym], "point": p,
        "t0": int(mins[0]), "base": int(o[0]), "start": int(np.searchsorted(m1.index.values, np.datetime64(start_time))),
        "dt": np.r_[0, np.diff(mins)].astype(int).tolist(),
        "o": (o - prevc).tolist(), "h": (h - np.maximum(o, c)).tolist(), "l": (np.minimum(o, c) - l).tolist(),
        "c": (c - o).tolist(), "s": m1["spread"].to_numpy().astype(int).tolist(),
    }
    return gzip.compress(json.dumps(body, separators=(",", ":")).encode(), compresslevel=9)


def decode(blob: bytes) -> tuple[dict, pd.DataFrame]:
    d = json.loads(gzip.decompress(blob))
    p = d["point"]
    o = np.empty(len(d["o"]), np.int64); c = np.empty_like(o)
    prev = d["base"]
    for i, (do, dc) in enumerate(zip(d["o"], d["c"])):
        o[i] = prev + do; c[i] = o[i] + dc; prev = c[i]
    h = np.maximum(o, c) + np.array(d["h"]); l = np.minimum(o, c) - np.array(d["l"])
    mins = d["t0"] + np.cumsum(d["dt"])
    idx = pd.to_datetime(mins.astype("datetime64[m]"))
    df = pd.DataFrame({"open": o * p, "high": h * p, "low": l * p, "close": c * p, "spread": d["s"]}, index=idx)
    return d, df.round(d["digits"])


def pick_mondays(index: pd.DatetimeIndex, n: int, rng: np.random.Generator) -> list[pd.Timestamp]:
    """Maandagen in oneven maanden 2020–2024 (dag 1–14, niet de eerste week van januari) met volledige data."""
    days = pd.DatetimeIndex(np.unique(index.normalize()))
    cand = [d for d in days if d.dayofweek == 0 and d.year in range(2020, 2025) and d.month % 2 == 1
            and d.day <= 14 and not (d.month == 1 and d.day < 8)]
    ok = []
    for d in cand:
        fwd = index[(index >= d) & (index < d + pd.Timedelta(days=12))]
        if len(fwd) > 9 * 1300:                      # ~10 handelsdagen aanwezig
            ok.append(d)
    pick = rng.choice(len(ok), size=min(n, len(ok)), replace=False)
    return [ok[i] for i in sorted(pick)]


def episode_frame(m1: pd.DataFrame, monday: pd.Timestamp, hist_days: int = 28, fwd_days: int = 12) -> pd.DataFrame:
    return m1[(m1.index >= monday - pd.Timedelta(days=hist_days)) & (m1.index < monday + pd.Timedelta(days=fwd_days))]
