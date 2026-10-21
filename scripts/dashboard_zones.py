"""
Zones (spec v0.7b) in het bouwstenen-dashboard (docs/dashboard_spec.md §12): soort "Zone", met kenmerken
zone_tf (M15/H1/H4), zone_entry (rand/38,2), zone_fvg (ja/nee) en de bestaande kenmerken waar die bestaan.
Uitvoering op M15 (zoals de andere soorten in het dashboard). Beide periodes (verkenning en 2025).
Gebruik: python -m scripts.dashboard_zones <htf-map> <dashboard-map>
"""
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

from katsu import research as R
from katsu.amd import amd_day_labels, amd_day_map, amd_setups
from katsu.dashboard_events import bin_label, day_context, nfp_day, rel_trend, session_label
from katsu.execution import M1
from katsu.structure import atr, find_swings, trend_series
from katsu.zones import find_zones, make_zone_plan_b, zone_entry
from scripts.dashboard_build import BASE_MARKETS, EXTRA_MARKETS, INS, PIP, free, placebo_plan, plan_cols
from scripts.dashboard_amd import PERIODS
from scripts.zones_test import TFS, resample, sim_b
from katsu.execution import simulate

ENTRY_LABEL = {"rand": "rand", "38.2": "38,2"}


def zone_rows(m15, mkt, mask, rng):
    a15 = atr(m15, 14).to_numpy()
    h1 = R.htf_trend(m15, "15min", "1h"); h4 = R.htf_trend(m15, "15min", "4h"); d1 = R.htf_trend(m15, "15min", "1D")
    tm = np.array(trend_series(find_swings(m15, 3), len(m15)), dtype=object)
    ctx = day_context(m15)
    med = pd.Series(a15).rolling(20 * 96, min_periods=96).median().shift(1).to_numpy()
    dmap = amd_day_map(amd_setups(m15, "open", "market"), m15)
    ins = replace(INS[mkt], min_sl_atr=0.0)
    insf = free(ins)
    M, Mf = M1(m15, ins), M1(m15, insf)
    ok = mask(m15.index) & np.isfinite(a15)
    slot = (m15.index.hour * 60 + m15.index.minute).to_numpy()
    pool = {k: np.nonzero(ok & (slot == k))[0] for k in np.unique(slot)}
    rows = []
    for tf, rule in TFS.items():
        bars = resample(m15, rule)
        a = atr(bars, 14).to_numpy()
        for z in find_zones(bars, a):
            t_sig = bars.index[z.k] + pd.Timedelta(rule)
            if not mask(pd.DatetimeIndex([t_sig]))[0]:
                continue
            kq = int(m15.index.searchsorted(t_sig) - 1)              # laatste gesloten M15-candle
            if kq < 0 or not np.isfinite(a15[kq]):
                continue
            d = 1 if z.direction == "LONG" else -1
            be = t_sig - pd.Timedelta(hours=1)
            pl, ph = ctx.prev_l.iat[kq], ctx.prev_h.iat[kq]
            al, ah = ctx.asia_l.iat[kq], ctx.asia_h.iat[kq]
            el, eh = ctx.asia_end_l_sofar.iat[kq], ctx.asia_end_h_sofar.iat[kq]
            sw_day = (ctx.day_l_sofar.iat[kq] < pl) if d > 0 else (ctx.day_h_sofar.iat[kq] > ph)
            sw_asia = (el < al) if d > 0 else (eh > ah)
            base = {"soort": "Zone", "zone_tf": tf, "zone_fvg": "ja" if z.fvg else "nee", "amd_variant": "n.v.t.",
                    "richting": "long" if d > 0 else "short", "markt": mkt,
                    "breuk": "n.v.t.", "sweep_swing": "n.v.t.", "order_block": "ja", "fvg_nummer": "n.v.t.",
                    "sweep_dag": "onbekend" if np.isnan(pl) else ("ja" if sw_day else "nee"),
                    "sweep_azie": "vóór einde Azië" if np.isnan(al) else ("ja" if sw_asia else "nee"),
                    "trend_m15": rel_trend(np.array([tm[kq]]), np.array([d]))[0],
                    "trend_h1": rel_trend(np.array([h1[kq]]), np.array([d]))[0],
                    "trend_h4": rel_trend(np.array([h4[kq]]), np.array([d]))[0],
                    "trend_d1": rel_trend(np.array([d1[kq]]), np.array([d]))[0],
                    "sessie": session_label(np.array([be.hour]))[0], "uur": be.hour,
                    "weekdag": ["ma", "di", "wo", "do", "vr", "za", "zo"][be.dayofweek],
                    "silver_bullet": "ja" if t_sig.hour in (10, 17, 21) else "nee",
                    "gat_atr": "onbekend", "displacement": "onbekend", "candle3_vol": "onbekend",
                    "volatiliteit": bin_label([a15[kq] / med[kq]], [0.8, 1.25], ["laag", "normaal", "hoog"])[0],
                    "nfp_dag": "ja" if nfp_day(pd.DatetimeIndex([t_sig]))[0] else "nee",
                    "amd_dag": amd_day_labels(pd.DatetimeIndex([t_sig]), np.array([d]), dmap)[0],
                    "t_sig": t_sig, "atr": z.atr}
            for entry in ("rand", "38.2"):
                px = zone_entry(z, entry)
                risk = abs(px - z.bottom); rr = abs(z.leg_high - px) / risk if risk > 0 else np.nan
                mid = (pl + ph) / 2
                row = dict(base)
                row.update({"zone_entry": ENTRY_LABEL[entry], "risk_plan": risk,
                            "sl_atr": bin_label([risk / z.atr], [1, 2, 3], ["<1", "1–2", "2–3", ">3"])[0],
                            "rr_plan": bin_label([rr], [1, 1.5, 2], ["<1", "1–1,5", "1,5–2", "≥2"])[0],
                            "premium_discount": "onbekend" if np.isnan(mid) else
                            ("mee" if (px < mid if d > 0 else px > mid) else "tegen")})
                tr = sim_b(z, bars, entry, mkt, rule, M, ins)
                trf = sim_b(z, bars, entry, mkt, rule, Mf, insf)
                g = tr.status == "gesloten"
                row.update({"status": tr.status, "uitkomst": tr.exit_reason, "r_net": tr.r_net,
                            "r_free": trf.r_net if trf.status == "gesloten" else np.nan,
                            "pips": tr.r_net * tr.risk / PIP[mkt] if g else np.nan,
                            "fill_time": tr.entry_time, "exit_time": tr.exit_time if g else pd.NaT,
                            "risk_pips": tr.risk / PIP[mkt] if g else np.nan,
                            "risk_pips_free": trf.risk / PIP[mkt] if trf.status == "gesloten" and trf.risk else np.nan,
                            "r_placebo": np.nan, "r_placebo_free": np.nan,
                        "fill_px": tr.fill, "sl_px": tr.sl, "tp_px": tr.tp, "exit_px": tr.exit_price,
                        **plan_cols(make_zone_plan_b(z, bars, entry, mkt, rule)), "plan_tp_mode": "zone_bij_vulling",
                        "plan_leg_high": z.leg_high, "plan_max_rr": 2.0})
                if g:
                    kf = int(m15.index.searchsorted(tr.entry_time, side="right") - 1)
                    cand = pool.get(int(slot[kf]), np.array([], int))
                    cand = cand[(np.abs(cand - kf) >= 96 * 5) & (cand + 1 < len(m15))]
                    if len(cand):
                        i = int(cand[rng.integers(len(cand))]); tp_dist = abs(tr.tp - tr.fill)
                        pt = simulate(placebo_plan(d, ins, M, m15, i, tr.risk, tp_dist, a15[i], mkt), M, ins)
                        pf = simulate(placebo_plan(d, insf, Mf, m15, i, trf.risk if trf.risk else tr.risk, tp_dist,
                                                   a15[i], mkt), Mf, insf)
                        row["r_placebo"] = pt.r_net if pt.status == "gesloten" else np.nan
                        row["r_placebo_free"] = pf.r_net if pf.status == "gesloten" else np.nan
                rows.append(row)
    if not rows:                                       # geen setups in het venster (KATSU Live: vaak)
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    lab = {"gesloten": "gevuld", "niet_gevuld": "niet gevuld", "geannuleerd": "TP eerst (geannuleerd)"}
    out["vulling"] = out.status.map(lambda x: lab.get(x, x))
    out["jaar"] = out.t_sig.dt.year
    wk = out.t_sig.dt.isocalendar(); out["week"] = (wk.year * 100 + wk.week).astype(int)
    return out


def main(folder, dash, markets=BASE_MARKETS, suffix=""):
    rng = np.random.default_rng(20261020)
    for per, (loader, mask) in PERIODS.items():
        parts = []
        for mkt in markets:
            parts.append(zone_rows(loader(folder, mkt), mkt, mask, rng))
            print(per, mkt, "zone-rijen", len(parts[-1]), flush=True)
        pd.concat(parts, ignore_index=True).to_pickle(os.path.join(dash, f"dashboard_zones_{per}{suffix}.pkl"))


if __name__ == "__main__":
    extra = len(sys.argv) > 3 and sys.argv[3] == "extra"
    main(*sys.argv[1:3], markets=EXTRA_MARKETS if extra else BASE_MARKETS, suffix="_extra" if extra else "")
