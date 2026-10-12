"""
Analyse van de KATSU Replay (docs/replay_spec.md): per trade hoe ver hij in de plus en in de min liep
(MFE/MAE) en hoe dicht hij bij zijn TP kwam. Gemeten zoals de uitvoering: long op BID, short op ASK.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PIP = {"EURUSD": 0.0001, "XAUUSD": 0.1}
POINT = {"EURUSD": 0.00001, "XAUUSD": 0.01}
MIN_SPREAD = {"EURUSD": 0.00001, "XAUUSD": 0.10}
COMM = {"EURUSD": 0.00008, "XAUUSD": 0.08}


def excursion(m1: pd.DataFrame, sym: str, d: int, fill: float, tp: float, fill_idx: int, exit_idx: int) -> dict:
    """
    m1 = episode-candles (bid) met kolom 'spread' in points. Bekijkt candles fill_idx..exit_idx (inclusief).
    mfe/mae in pips (positief = in de goede richting / tegen je in), tp_rest = pips die nog ontbraken tot de TP
    op het beste moment (0 of minder = TP bereikt), tp_bereikt = deel van de TP-afstand dat gehaald werd.
    """
    seg = m1.iloc[fill_idx:exit_idx + 1]
    sp = np.maximum(seg["spread"].to_numpy(float) * POINT[sym], MIN_SPREAD[sym])
    if d > 0:
        best, worst = seg["high"].to_numpy(float).max(), seg["low"].to_numpy(float).min()
    else:
        best = (seg["low"].to_numpy(float) + sp).min(); worst = (seg["high"].to_numpy(float) + sp).max()
    pip = PIP[sym]
    mfe = d * (best - fill) / pip
    mae = -d * (worst - fill) / pip
    tp_dist = d * (tp - fill) / pip
    return {"mfe_pips": mfe, "mae_pips": mae, "tp_afstand_pips": tp_dist, "tp_rest_pips": tp_dist - mfe,
            "tp_bereikt": mfe / tp_dist if tp_dist > 0 else np.nan}


def net_pips(sym: str, d: int, fill: float, exit_px: float) -> float:
    return (d * (exit_px - fill) - COMM[sym]) / PIP[sym]
