"""
Bouwt de data voor het bouwstenen-dashboard (docs/dashboard_spec.md): alle setups op de verkenningsdata met
kenmerken, uitkomst met echte kosten, zonder kosten, en een vergelijkingstrade (placebo).
Gebruik: python -m scripts.dashboard_build <htf-map> <uitmap>
"""
import os
import sys
import time
from dataclasses import replace

import numpy as np
import pandas as pd

from katsu import research as R
from katsu.dashboard_events import build_events, features
from katsu.execution import M1, OrderPlan, simulate
from katsu.structure import atr
from scripts.gfvg_test import INS
from scripts.ronde1 import load

PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.1}
VALID_BARS = 480
MAX_RR = 2.0


def free(ins):
    return replace(ins, min_spread=0.0, slip=0.0, commission=0.0, swap=0.0, swap_short=0.0, rollover_min_spread=0.0,
                   point=0.0)


def plan_for(r, bars, mkt):
    step = pd.Timedelta("15min")
    s = int(r.s); sgn = 1.0 if r.d > 0 else -1.0
    risk = sgn * (r.entry - (r.anchor - sgn * 0.1 * r.atr))
    cap = r.entry + sgn * MAX_RR * risk
    tp = None if pd.isna(r.tp) else float(r.tp)
    cancel = cap if tp is None or sgn * (tp - cap) > 0 else tp
    return OrderPlan("LONG" if r.d > 0 else "SHORT", bars.index[s] + step, "limit", float(r.anchor), float(r.atr),
                     float(r.entry), bars.index[min(s + VALID_BARS, len(bars) - 1)] + step, market=mkt,
                     tp_price=tp, cancel_price=cancel, max_rr=MAX_RR if tp is not None else None)


def placebo_plan(d, sym_ins, M, bars, i, risk, tp_dist, atr_i, mkt):
    """Markt-order op de open van candle i+1 met dezelfde SL- en TP-afstand als de echte setup."""
    j = i + 1
    sp = M.sp[j]; slip = sym_ins.slip
    if d > 0:
        fill = M.o[j] + sp + slip; anchor = fill - risk + sp + 0.1 * atr_i
    else:
        fill = M.o[j] - slip; anchor = fill + risk - sp - 0.1 * atr_i
    return OrderPlan("LONG" if d > 0 else "SHORT", bars.index[j], "market", float(anchor), float(atr_i),
                     market=mkt, tp_price=float(fill + d * tp_dist))


def run_market(folder, mkt, rng):
    bars = load(folder, mkt, "M15")
    a = atr(bars, 14).to_numpy()
    h1 = R.htf_trend(bars, "15min", "1h"); h4 = R.htf_trend(bars, "15min", "4h"); d1 = R.htf_trend(bars, "15min", "1D")
    ev = build_events(bars)
    ev = ev[R.explore_mask(bars.index[ev.s.to_numpy(int)]) & np.isfinite(a[ev.s.to_numpy(int)])].reset_index(drop=True)
    ev["atr"] = a[ev.s.to_numpy(int)]
    ev = features(bars, ev, a, h1, h4, d1, PIP[mkt])
    ins = replace(INS[mkt], min_sl_atr=0.0)
    insf = free(ins)
    M, Mf = M1(bars, ins), M1(bars, insf)
    # kandidaten voor de placebo: candles van de verkenningsdata, per uur:kwartier
    ok = R.explore_mask(bars.index) & np.isfinite(a)
    slot = (bars.index.hour * 60 + bars.index.minute).to_numpy()
    pool = {k: np.nonzero(ok & (slot == k))[0] for k in np.unique(slot)}
    rows = []
    for r in ev.itertuples():
        p = plan_for(r, bars, mkt)
        tr = simulate(p, M, ins)
        trf = simulate(replace(p), Mf, insf)
        row = {"status": tr.status, "uitkomst": tr.exit_reason, "r_net": tr.r_net, "r_free": trf.r_net if trf.status == "gesloten" else np.nan,
               "pips": (tr.r_net * tr.risk / PIP[mkt]) if tr.status == "gesloten" else np.nan,
               "duur_min": ((tr.exit_time - tr.entry_time).total_seconds() / 60) if tr.status == "gesloten" else np.nan,
               "kosten_r": ((ins.min_spread + 2 * ins.slip + ins.commission) / tr.risk) if tr.risk and tr.risk > 0 else np.nan,
               "fill_time": tr.entry_time}
        if tr.status == "gesloten":
            cand = pool[int(slot[int(r.s)])]
            i = int(cand[rng.integers(len(cand))])
            while abs(i - int(r.s)) < 96 * 5 or i + 1 >= len(bars):
                i = int(cand[rng.integers(len(cand))])
            tp_dist = abs(tr.tp - tr.fill)
            pt = simulate(placebo_plan(int(r.d), ins, M, bars, i, tr.risk, tp_dist, a[i], mkt), M, ins)
            row["r_placebo"] = pt.r_net if pt.status == "gesloten" else np.nan
            pf = simulate(placebo_plan(int(r.d), insf, Mf, bars, i, trf.risk if trf.risk else tr.risk, tp_dist, a[i], mkt),
                          Mf, insf)
            row["r_placebo_free"] = pf.r_net if pf.status == "gesloten" else np.nan
        else:
            row["r_placebo"] = np.nan; row["r_placebo_free"] = np.nan
        rows.append(row)
    out = pd.concat([ev, pd.DataFrame(rows)], axis=1)
    out["markt"] = mkt
    lab = {"gesloten": "gevuld", "niet_gevuld": "niet gevuld", "geannuleerd": "TP eerst (geannuleerd)"}
    out["vulling"] = out.status.map(lambda x: lab.get(x, x))
    out["kosten"] = np.where(out.kosten_r.isna(), "onbekend", np.where(out.kosten_r < 0.1, "<0,1R",
                                                                         np.where(out.kosten_r < 0.2, "0,1–0,2R", ">0,2R")))
    t = out.t_sig
    out["jaar"] = t.dt.year
    wk = t.dt.isocalendar(); out["week"] = (wk.year * 100 + wk.week).astype(int)
    return out


def main(folder, outdir):
    os.makedirs(outdir, exist_ok=True)
    rng = np.random.default_rng(20261012)
    allm = []
    for mkt in ("EURUSD", "GBPUSD", "XAUUSD"):
        t0 = time.time()
        df = run_market(folder, mkt, rng)
        allm.append(df)
        g = df[df.status == "gesloten"]
        print(f"{mkt}: setups {len(df)}, gevuld {len(g)}, gem R {g.r_net.mean():+.3f}, zonder kosten {g.r_free.mean():+.3f}, "
              f"placebo {g.r_placebo.mean():+.3f}, placebo zonder kosten {g.r_placebo_free.mean():+.3f} ({time.time() - t0:.0f}s)", flush=True)
    pd.concat(allm, ignore_index=True).to_pickle(os.path.join(outdir, "dashboard_events.pkl"))


if __name__ == "__main__":
    main(*sys.argv[1:3])
