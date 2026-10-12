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


def sl_check(m1: pd.DataFrame, sym: str, d: int, fill: float, sl: float, tp: float, fill_idx: int) -> dict:
    """
    Was een iets ruimere SL beter geweest? Volgt de koers vanaf de vulling tot het einde van de episode en zoekt
    het moment waarop de TP geraakt wordt. Nodige SL = grootste beweging tegen je in vóór dat moment (de candle
    van de TP telt mee: bij twijfel eerst de SL). extra_sl_pips = hoeveel pips ruimer de SL had moeten zijn
    (0 = de oorspronkelijke SL hield stand; None = de TP werd in de episode nooit geraakt).
    sl_marge_pips = hoeveel pips er tot de oorspronkelijke SL overbleven op het slechtste moment vóór de TP (of tot
    het einde als de TP nooit kwam): klein = het scheelde weinig.
    """
    seg = m1.iloc[fill_idx:]
    sp = np.maximum(seg["spread"].to_numpy(float) * POINT[sym], MIN_SPREAD[sym])
    if d > 0:
        adv = seg["low"].to_numpy(float); fav = seg["high"].to_numpy(float)
    else:
        adv = seg["high"].to_numpy(float) + sp; fav = seg["low"].to_numpy(float) + sp
    pip = PIP[sym]
    worst = np.maximum.accumulate(-d * (adv - fill) / pip)          # grootste beweging tegen je in tot en met candle i
    hit = np.nonzero(d * (fav - tp) >= 0)[0]
    sl_dist = d * (fill - sl) / pip
    if len(hit) == 0:
        return {"sl_afstand_pips": sl_dist, "extra_sl_pips": None, "tp_na_minuten": None,
                "sl_marge_pips": sl_dist - worst[-1]}
    need = worst[hit[0]]
    return {"sl_afstand_pips": sl_dist, "extra_sl_pips": max(0.0, need - sl_dist), "tp_na_minuten": int(hit[0]),
            "sl_marge_pips": sl_dist - need}
