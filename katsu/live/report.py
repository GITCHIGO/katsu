"""
Resultaten (spec §5 'Resultaten') en de controle backtest ↔ broker (werkregel 5) voor het dashboard.

Resultaten komen uit de ECHTE brokercijfers (winst + commissie + swap van MT5, in de rekeningmunt). R = netto geld /
geld dat op het spel stond bij de vulling (MT5 rekent dat uit: verlies als de SL geraakt wordt).

Controle: dezelfde rijen als de vooruit-test (scripts/vooruittest.rows_for) op de candles uit MT5, vanaf de start van
KATSU Live, met één trade tegelijk per setup per pair. Per signaal en per trade naast elkaar.
Een trade is 'gelijk' als hij in beide bestaat en (beide lopen nog) of (beide dicht met dezelfde uitkomst — TP, SL of
tijd — en minder dan 0,25R verschil). Overeenkomst = gelijk / alle trades (backtest of live). Doel ≥ 90 %.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from katsu.live.orders import PIP
from katsu.live.scan import SETUPS, signal_from_row
from katsu.presets import PRESETS, preset_mask

R_TOL = 0.25
TIME_EXIT = {"MAX_DUUR", "EINDE_DAG", "EINDE_DATA"}


def _closed(orders):
    return [o for o in orders if o.get("state") == "gesloten" and o.get("r_net") is not None]


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"trades": 0, "winst": 0, "verlies": 0, "winrate": None, "gem_R": None, "totaal_R": 0.0, "pips": 0.0,
                "winst_geld": 0.0, "verlies_geld": 0.0, "netto": 0.0}
    net = np.array([o["net"] for o in rows], float)
    r = np.array([o["r_net"] for o in rows], float)
    w = net > 0
    return {"trades": n, "winst": int(w.sum()), "verlies": int((~w).sum()), "winrate": float(w.mean()),
            "gem_R": float(r.mean()), "totaal_R": float(r.sum()), "pips": float(sum(o["pips"] or 0 for o in rows)),
            "winst_geld": float(net[w].sum()), "verlies_geld": float(net[~w].sum()), "netto": float(net.sum())}


def results(orders: list[dict], since: pd.Timestamp | None = None) -> dict:
    """orders: dicts (asdict van LiveOrder). since: alleen trades die sindsdien gesloten zijn."""
    closed = _closed(orders)
    if since is not None:
        closed = [o for o in closed if pd.Timestamp(o["exit_time"]) >= since]
    closed.sort(key=lambda o: o["exit_time"])
    out = {"algemeen": summarize(closed), "setups": {},
           "lopend": sum(o.get("state") == "gevuld" for o in orders),
           "trades": closed[::-1]}
    for name, p in PRESETS.items():
        rows = [o for o in closed if o["setup"] == name]
        s = summarize(rows)
        s["per_pair"] = {m: summarize([o for o in rows if o["market"] == m]) for m in p["markt"]}
        cum, curve = 0.0, []
        for o in rows:
            cum += o["r_net"]
            curve.append((o["exit_time"], cum))
        s["curve"] = curve
        out["setups"][name] = s
    return out


def _exit_kind(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return "tijd" if x in TIME_EXIT else x


def control(orders: list[dict], bars_by_market: dict, start: pd.Timestamp, rows_for=None, setup_trades=None) -> dict:
    if rows_for is None or setup_trades is None:
        from scripts.vooruittest import rows_for, setup_trades
    lo = start - pd.Timedelta(days=3)
    df = rows_for(bars_by_market, lambda t: np.asarray(t >= lo), np.random.default_rng(20261021))
    res = {"start": str(start), "signalen": {}, "trades": [], "overeenkomst": None, "n_trades": 0, "n_gelijk": 0}
    if len(df) == 0:
        df = pd.DataFrame(columns=["t_sig"])
    df = df[df.t_sig >= start] if len(df) else df
    bt_sig, bt_tr = {}, {}
    for name in PRESETS:
        if len(df) == 0:
            break
        sel = df[preset_mask(df, name)]
        for _, r in sel.iterrows():
            bt_sig[signal_from_row(r, name).key] = r
        for _, r in setup_trades(df, name).iterrows():
            bt_tr[signal_from_row(r, name).key] = r
    live = {o["key"]: o for o in orders if pd.Timestamp(o["t_sig"]) >= start}
    both = set(bt_sig) & set(live)
    union = set(bt_sig) | set(live)
    res["signalen"] = {"backtest": len(bt_sig), "live": len(live), "gelijk": len(both),
                       "pct": (len(both) / len(union)) if union else None,
                       "alleen_backtest": sorted(set(bt_sig) - set(live)), "alleen_live": sorted(set(live) - set(bt_sig))}
    live_tr = {k: o for k, o in live.items() if o.get("fill_px") is not None}
    rows = []
    for k in sorted(set(bt_tr) | set(live_tr), key=lambda x: x.split("|")[2]):
        b, o = bt_tr.get(k), live_tr.get(k)
        setup, mkt, t, d = k.split("|")[:4]
        row = {"key": k, "setup": SETUPS[setup][0], "markt": mkt, "t_sig": t, "richting": d,
               "bt_fill": None, "bt_uit": None, "bt_R": None, "live_fill": None, "live_uit": None, "live_R": None,
               "slippage_pips": None, "commissie": None, "swap": None, "status": ""}
        if b is not None:
            lopend = b["uitkomst"] == "EINDE_DATA"
            row.update(bt_fill=float(b["fill_px"]), bt_uit="loopt" if lopend else b["uitkomst"],
                       bt_R=None if lopend else float(b["r_net"]))
        if o is not None:
            row.update(live_fill=o["fill_px"], live_uit="loopt" if o["state"] == "gevuld" else o.get("exit_reason"),
                       live_R=o.get("r_net"), commissie=o.get("commission"), swap=o.get("swap"))
        if b is not None and o is not None:
            s = 1 if d == "LONG" else -1
            row["slippage_pips"] = s * (o["fill_px"] - float(b["fill_px"])) / PIP[mkt]     # + = slechter dan backtest
            if row["bt_uit"] == "loopt" and row["live_uit"] == "loopt":
                row["status"] = "gelijk (loopt)"
            elif "loopt" in (row["bt_uit"], row["live_uit"]):
                row["status"] = "verschil: één loopt nog"
            elif _exit_kind(row["bt_uit"]) != _exit_kind(row["live_uit"]):
                row["status"] = f"verschil: uitkomst {row['bt_uit']} vs {row['live_uit']}"
            elif row["live_R"] is None or abs(row["live_R"] - row["bt_R"]) > R_TOL:
                row["status"] = "verschil: R"
            else:
                row["status"] = "gelijk"
        else:
            row["status"] = "alleen backtest" if o is None else "alleen live"
        rows.append(row)
    res["trades"] = rows
    res["n_trades"] = len(rows)
    res["n_gelijk"] = sum(r["status"].startswith("gelijk") for r in rows)
    res["overeenkomst"] = (res["n_gelijk"] / len(rows)) if rows else None
    return res
