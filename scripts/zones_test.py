"""
Test zones (docs/spec_v0.7.md §4): 2025 – okt 2026, EURUSD/XAUUSD uitgevoerd op M1, GBPUSD op M15.
Gebruik: python -m scripts.zones_test <htf-map> <uitmap>
"""
import itertools
import os
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

from katsu import research as R
from katsu.dashboard_calc import clustered_t, one_at_a_time
from katsu.execution import M1, simulate
from katsu.structure import atr
from katsu.zones import find_zones, make_zone_plan, make_zone_plan_b, tp_at_fill
from scripts.dashboard_build import free, placebo_plan
from scripts.eindtest_gfvg import final_mask, load_full
from scripts.gfvg_test import INS

MARKETS = ("EURUSD", "GBPUSD", "XAUUSD")
M1_FILES = {"EURUSD": "eur_m1_full.pkl", "XAUUSD": "xau_m1_full.pkl"}
TFS = {"M15": "15min", "H1": "1h", "H4": "4h"}
VARIANTS = list(itertools.product(TFS, ("rand", "38.2"), (False, True)))
PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.1}


def vname(v):
    return f"{v[0]}-{'rand' if v[1] == 'rand' else '38,2'}-{'B1' if v[2] else 'B0'}"


def resample(m15, rule):
    if rule == "15min":
        return m15
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "spread": "max"}
    return m15.resample(rule, label="left", closed="left").agg(agg).dropna(subset=["open"])


def exec_data(research, mkt, m15):
    if mkt in M1_FILES:
        m1 = pd.read_pickle(os.path.join(research, M1_FILES[mkt]))
        return m1[m1.index >= "2024-12-01"]
    return m15[m15.index >= "2024-12-01"]


def sim_b(z, bars, entry, mkt, rule, M, ins):
    """v0.7b: eerst de vulling zoeken (verre TP), dan TP = oude high vlak vóór de vulling, opnieuw simuleren."""
    probe = simulate(make_zone_plan_b(z, bars, entry, mkt, rule), M, ins)
    if probe.status != "gesloten":
        return probe
    i_from = int(M.t.searchsorted(bars.index[z.k] + pd.Timedelta(rule)))
    i_fill = int(M.t.searchsorted(probe.entry_time))
    tp = tp_at_fill(z, M.h, M.lo, i_from, i_fill)
    return simulate(make_zone_plan_b(z, bars, entry, mkt, rule, tp=tp), M, ins)


def run(folder, outdir, research="/home/claude/katsu_research", seed=20261020, mode="a"):
    os.makedirs(outdir, exist_ok=True)
    rng = np.random.default_rng(seed)
    rows = []
    for mkt in MARKETS:
        m15 = load_full(folder, mkt)
        ins = replace(INS[mkt], min_sl_atr=0.0)
        insf = free(ins)
        ex = exec_data(research, mkt, m15)
        M, Mf = M1(ex, ins), M1(ex, insf)
        Mq, Mqf = M1(m15, ins), M1(m15, insf)                 # placebo op M15 (uitgelijnd met m15)
        a15 = atr(m15, 14).to_numpy()
        ok = final_mask(m15.index) & np.isfinite(a15)
        slot = (m15.index.hour * 60 + m15.index.minute).to_numpy()
        pool = {k: np.nonzero(ok & (slot == k))[0] for k in np.unique(slot)}
        for tf, rule in TFS.items():
            bars = resample(m15, rule)
            a = atr(bars, 14).to_numpy()
            d1 = R.htf_trend(bars, rule, "1D")
            zones = find_zones(bars, a)
            for z in zones:
                t_known = bars.index[z.k] + pd.Timedelta(rule)
                if not final_mask(pd.DatetimeIndex([t_known]))[0]:
                    continue
                trend_ok = d1[z.k] == ("UP" if z.direction == "LONG" else "DOWN")
                for entry in ("rand", "38.2"):
                    if mode == "b":
                        tr = sim_b(z, bars, entry, mkt, rule, M, ins)
                        trf = sim_b(z, bars, entry, mkt, rule, Mf, insf)
                    else:
                        p = make_zone_plan(z, bars, entry, mkt, rule)
                        tr = simulate(p, M, ins)
                        trf = simulate(p, Mf, insf)
                    g = tr.status == "gesloten"
                    row = {"markt": mkt, "tf": tf, "entry": entry, "trend_mee": bool(trend_ok), "richting": z.direction,
                           "fvg": z.fvg, "t_known": t_known, "status": tr.status, "uitkomst": tr.exit_reason,
                           "r_net": tr.r_net, "r_free": trf.r_net if trf.status == "gesloten" else np.nan,
                           "fill_time": tr.entry_time, "exit_time": tr.exit_time if g else pd.NaT,
                           "risk_pips": tr.risk / PIP[mkt] if g else np.nan, "r_placebo_free": np.nan}
                    if g:
                        kf = int(m15.index.searchsorted(tr.entry_time, side="right") - 1)
                        cand = pool.get(int(slot[kf]), np.array([], int))
                        cand = cand[(np.abs(cand - kf) >= 96 * 5) & (cand + 1 < len(m15))]
                        if len(cand):
                            i = int(cand[rng.integers(len(cand))])
                            sgn = 1 if z.direction == "LONG" else -1
                            pf = simulate(placebo_plan(sgn, insf, Mqf, m15, i, trf.risk if trf.risk else tr.risk,
                                                       abs(tr.tp - tr.fill), a15[i], mkt), Mqf, insf)
                            row["r_placebo_free"] = pf.r_net if pf.status == "gesloten" else np.nan
                    rows.append(row)
            print(mkt, tf, len(zones), "zones", flush=True)
    df = pd.DataFrame(rows)
    df["vulling"] = np.where(df.status == "gesloten", "gevuld", df.status)
    wk = df.t_known.dt.isocalendar(); df["week"] = (wk.year * 100 + wk.week).astype(int)
    df["jaar"] = df.t_known.dt.year
    df.to_pickle(os.path.join(outdir, f"zones_trades_{mode}.pkl"))
    return df


def stats(f):
    return {"n": len(f), "win": (f.r_net > 0).mean() if len(f) else np.nan, "R": f.r_net.mean(),
            "t": clustered_t(f.r_net.to_numpy(), f.week.to_numpy()), "vrij": f.r_free.mean(),
            "plac_vrij": f.r_placebo_free.mean()}


LAT = 2.2


def summarize(df):
    out = []
    for v in VARIANTS:
        tf, entry, bias = v
        g = df[(df.tf == tf) & (df.entry == entry)]
        if bias:
            g = g[g.trend_mee]
        g = g.sort_values("fill_time", kind="stable")
        allf = g[g.status == "gesloten"]
        one = one_at_a_time(g)
        s = {"variant": vname(v), "zones": len(g), "gevuld": len(allf), **stats(one)}
        s["R_alle"] = allf.r_net.mean()
        for y in (2025, 2026):
            s[f"R_{y}"] = one[one.jaar == y].r_net.mean(); s[f"n_{y}"] = int((one.jaar == y).sum())
        for m in MARKETS:
            s["R_" + m] = one[one.markt == m].r_net.mean()
        s["poort"] = bool(s["n"] >= 100 and s["R"] >= 0.10 and s["t"] >= LAT and s["R_2025"] > 0 and s["R_2026"] > 0
                          and s["vrij"] > s["plac_vrij"])
        out.append(s)
    return pd.DataFrame(out)


if __name__ == "__main__":
    mode = sys.argv[3] if len(sys.argv) > 3 else "a"
    d = run(*sys.argv[1:3], mode=mode)
    if mode == "b":
        LAT = 2.5                                      # 24 varianten in totaal (spec v0.7 §5)
    r = summarize(d)
    os.makedirs("research", exist_ok=True)
    r.to_csv("research/register_zones.csv" if mode == "a" else "research/register_zones_b.csv", index=False,
             float_format="%.4f")
    print(r.round(3).to_string())
