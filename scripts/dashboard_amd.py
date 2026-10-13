"""
AMD in het bouwstenen-dashboard (docs/dashboard_spec.md §11):
1. AMD-setups (spec v0.6, 4 versies C1/C2 × E1/E2, zonder bias: de D1-trend is een filter) in het dashboardformaat,
   met dezelfde kenmerken waar die bestaan ('n.v.t.' waar niet) en AMD's eigen uitstap (TP overkant Azië-range,
   sluiten op de dagclose).
2. Kenmerk 'amd_dag' voor de FVG/IFVG-setups: bevestigde AMD-beweging (C2) eerder die dag, mee/tegen/geen.
Gebruik: python -m scripts.dashboard_amd <htf-map> <dashboard-map>
"""
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

from katsu import research as R
from katsu.amd import amd_day_labels, amd_day_map, amd_setups, make_amd_plan
from katsu.dashboard_events import bin_label, day_context, nfp_day, rel_trend, session_label
from katsu.execution import M1, simulate
from katsu.structure import atr, find_swings, trend_series
from scripts.dashboard_build import PIP, free, placebo_plan
from scripts.eindtest_gfvg import final_mask, load_full
from scripts.gfvg_test import INS
from scripts.ronde1 import load

VARIANTS = [("range", "market", "C1-E1"), ("range", "fvg", "C1-E2"), ("open", "market", "C2-E1"), ("open", "fvg", "C2-E2")]
PERIODS = {"verkenning": (lambda f, m: load(f, m, "M15"), R.explore_mask),
           "2025": (load_full, final_mask)}


def amd_rows(bars, mkt, mask, rng):
    a = atr(bars, 14).to_numpy()
    o, h, lo, c = (bars[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    h1 = R.htf_trend(bars, "15min", "1h"); h4 = R.htf_trend(bars, "15min", "4h"); d1 = R.htf_trend(bars, "15min", "1D")
    m15 = np.array(trend_series(find_swings(bars, 3), len(bars)), dtype=object)
    ctx = day_context(bars)
    med = pd.Series(a).rolling(20 * 96, min_periods=96).median().shift(1).to_numpy()
    ins = replace(INS[mkt], min_sl_atr=0.0, max_hold_days=None, close_eod=True)
    insf = free(ins)
    M, Mf = M1(bars, ins), M1(bars, insf)
    ok = mask(bars.index) & np.isfinite(a)
    slot = (bars.index.hour * 60 + bars.index.minute).to_numpy()
    pool = {k: np.nonzero(ok & (slot == k))[0] for k in np.unique(slot)}
    rows = []
    for conf, ent, name in VARIANTS:
        for s in amd_setups(bars, conf, ent, day_mask=mask):
            k = s.k_conf; A = a[k]
            if not np.isfinite(A):
                continue
            d = 1 if s.direction == "LONG" else -1
            t_sig = bars.index[k] + pd.Timedelta("15min"); be = t_sig - pd.Timedelta(hours=1)
            entry = c[k] if s.entry is None else s.entry            # E1: benadering met de close (voor de kenmerken)
            risk = abs(entry - s.anchor); rr = abs(s.tp - entry) / risk if risk > 0 else np.nan
            pl, ph = ctx.prev_l.iat[k], ctx.prev_h.iat[k]
            sw_day = (ctx.day_l_sofar.iat[k] < pl) if d > 0 else (ctx.day_h_sofar.iat[k] > ph)
            mid = (pl + ph) / 2
            row = {"soort": "AMD", "amd_variant": name, "richting": "long" if d > 0 else "short", "markt": mkt,
                   "breuk": "n.v.t.", "sweep_swing": "n.v.t.", "order_block": "n.v.t.", "fvg_nummer": "n.v.t.",
                   "sweep_dag": "onbekend" if np.isnan(pl) else ("ja" if sw_day else "nee"), "sweep_azie": "ja",
                   "trend_m15": rel_trend(np.array([m15[k]]), np.array([d]))[0],
                   "trend_h1": rel_trend(np.array([h1[k]]), np.array([d]))[0],
                   "trend_h4": rel_trend(np.array([h4[k]]), np.array([d]))[0],
                   "trend_d1": rel_trend(np.array([d1[k]]), np.array([d]))[0],
                   "premium_discount": "onbekend" if np.isnan(mid) else ("mee" if (entry < mid if d > 0 else entry > mid) else "tegen"),
                   "sessie": session_label(np.array([be.hour]))[0], "uur": be.hour,
                   "weekdag": ["ma", "di", "wo", "do", "vr", "za", "zo"][be.dayofweek],
                   "silver_bullet": "ja" if t_sig.hour in (10, 17, 21) else "nee",
                   "gat_atr": bin_label([(s.fvg[3] - s.fvg[2]) / A if s.fvg else np.nan], [0.25, 0.5, 1, 2],
                                        ["<0,25", "0,25–0,5", "0,5–1", "1–2", ">2"])[0],
                   "displacement": "onbekend", "candle3_vol": "onbekend",
                   "risk_plan": risk, "sl_atr": bin_label([risk / A], [1, 2, 3], ["<1", "1–2", "2–3", ">3"])[0],
                   "rr_plan": bin_label([rr], [1, 1.5, 2], ["<1", "1–1,5", "1,5–2", "≥2"])[0],
                   "volatiliteit": bin_label([A / med[k]], [0.8, 1.25], ["laag", "normaal", "hoog"])[0],
                   "nfp_dag": "ja" if nfp_day(pd.DatetimeIndex([t_sig]))[0] else "nee", "amd_dag": "mee",
                   "t_sig": t_sig, "atr": A}
            p = make_amd_plan(s, bars, a, mkt)
            tr = simulate(p, M, ins); trf = simulate(p, Mf, insf)
            g = tr.status == "gesloten"
            row.update({"status": tr.status, "uitkomst": tr.exit_reason, "r_net": tr.r_net,
                        "r_free": trf.r_net if trf.status == "gesloten" else np.nan,
                        "pips": tr.r_net * tr.risk / PIP[mkt] if g else np.nan,
                        "fill_time": tr.entry_time, "exit_time": tr.exit_time if g else pd.NaT,
                        "risk_pips": tr.risk / PIP[mkt] if g else np.nan,
                        "risk_pips_free": trf.risk / PIP[mkt] if trf.status == "gesloten" and trf.risk else np.nan,
                        "r_placebo": np.nan, "r_placebo_free": np.nan})
            if g:
                cand = pool.get(int(slot[k]), np.array([], int))
                cand = cand[(np.abs(cand - k) >= 96 * 5) & (cand + 1 < len(bars))]
                if len(cand):
                    i = int(cand[rng.integers(len(cand))]); tp_dist = abs(tr.tp - tr.fill)
                    pt = simulate(placebo_plan(d, ins, M, bars, i, tr.risk, tp_dist, a[i], mkt), M, ins)
                    pf = simulate(placebo_plan(d, insf, Mf, bars, i, trf.risk if trf.risk else tr.risk, tp_dist, a[i], mkt),
                                  Mf, insf)
                    row["r_placebo"] = pt.r_net if pt.status == "gesloten" else np.nan
                    row["r_placebo_free"] = pf.r_net if pf.status == "gesloten" else np.nan
            rows.append(row)
    out = pd.DataFrame(rows)
    lab = {"gesloten": "gevuld", "niet_gevuld": "niet gevuld", "geannuleerd": "TP eerst (geannuleerd)"}
    out["vulling"] = out.status.map(lambda x: lab.get(x, x))
    out["jaar"] = out.t_sig.dt.year
    wk = out.t_sig.dt.isocalendar(); out["week"] = (wk.year * 100 + wk.week).astype(int)
    return out


def main(folder, dash):
    rng = np.random.default_rng(20261013)
    for per, (loader, mask) in PERIODS.items():
        ev_path = os.path.join(dash, f"dashboard_events_{per}.pkl")
        ev = pd.read_pickle(ev_path)
        ev["amd_variant"] = "n.v.t."
        ev["amd_dag"] = "geen"
        amd = []
        for mkt in ("EURUSD", "GBPUSD", "XAUUSD"):
            bars = loader(folder, mkt)
            m = ev.markt == mkt
            dmap = amd_day_map(amd_setups(bars, "open", "market"), bars)
            d = np.where(ev.loc[m, "richting"] == "long", 1, -1)
            ev.loc[m, "amd_dag"] = amd_day_labels(pd.DatetimeIndex(ev.loc[m, "t_sig"]), d, dmap)
            amd.append(amd_rows(bars, mkt, mask, rng))
            print(per, mkt, "AMD-setups", len(amd[-1]), "| amd_dag:", ev.loc[m, "amd_dag"].value_counts().to_dict(), flush=True)
        ev.to_pickle(ev_path)
        pd.concat(amd, ignore_index=True).to_pickle(os.path.join(dash, f"dashboard_amd_{per}.pkl"))


if __name__ == "__main__":
    main(*sys.argv[1:3])
