"""
Bouwt de data voor het bouwstenen-dashboard (docs/dashboard_spec.md): alle setups op de verkenningsdata met
kenmerken, uitkomst met echte kosten, zonder kosten, en een vergelijkingstrade (placebo).
Gebruik: python -m scripts.dashboard_build <htf-map> <uitmap> [verkenning|2025]
  verkenning = verkenningshelft (vóór 2020 + oneven maanden 2020–24)
  2025       = 1 jan 2025 t/m einde data (besluit Gitchi 12 okt 2026; zonder zijn screenshotdagen)
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
from katsu.execution import Instrument
from scripts.gfvg_test import INS as _INS_BASE
from scripts.eindtest_gfvg import final_mask, load_full
from scripts.ronde1 import load

# Extra markten (dashboard §13). Kosten zoals in ronde 1 (zilver) en ronde 3 (US500); max. looptijd 14 dagen.
EXTRA_INS = {
    "XAGUSD": Instrument("XAGUSD", tick=0.001, point=0.001, min_spread=0.010, slip=0.005, commission=0.002,
                         swap=0.005, rollover_min_spread=0.02, max_hold_days=14),
    "US500": Instrument("US500", tick=0.01, point=0.01, min_spread=0.30, slip=0.25, commission=0.0,
                        swap_pct_long=0.03, swap_pct_short=0.03, rollover_min_spread=1.0, max_hold_days=14),
}
INS = {**_INS_BASE, **EXTRA_INS}
BASE_MARKETS = ("EURUSD", "GBPUSD", "XAUUSD")
EXTRA_MARKETS = ("XAGUSD", "US500")
PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.1, "XAGUSD": 0.01, "US500": 1.0}
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


def period_data(folder, mkt, period):
    """Candles en masker (welke candles setups/placebo's mogen leveren) voor een periode.
    period mag ook een functie(DatetimeIndex) -> bool-array zijn (vooruit-test: een eigen venster)."""
    if callable(period):
        return load_full(folder, mkt), period
    if period == "verkenning":
        bars = load(folder, mkt, "M15")
        return bars, R.explore_mask
    if period == "2025":
        return load_full(folder, mkt), final_mask          # vanaf 2023 voor opwarming, signalen vanaf 2025
    raise ValueError(period)


def plan_cols(p, valid_bars=None):
    """Het orderplan zelf in de rij (voor KATSU Live: zelfde plan als de backtest). Verandert geen uitkomst."""
    return {"plan_kind": p.kind, "plan_richting": p.direction, "plan_signal_time": p.signal_time,
            "plan_anchor": p.anchor, "plan_atr": p.atr, "plan_limit": p.limit_price, "plan_valid_until": p.valid_until,
            "plan_valid_bars": valid_bars, "plan_tp": p.tp_price, "plan_cancel": p.cancel_price, "plan_max_rr": p.max_rr}


def run_market(folder, mkt, rng, period="verkenning", bars=None):
    """bars: candles rechtstreeks meegeven (KATSU Live); dan moet period een masker-functie zijn."""
    if bars is None:
        bars, mask = period_data(folder, mkt, period)
    else:
        mask = period
    a = atr(bars, 14).to_numpy()
    h1 = R.htf_trend(bars, "15min", "1h"); h4 = R.htf_trend(bars, "15min", "4h"); d1 = R.htf_trend(bars, "15min", "1D")
    ev = build_events(bars)
    ev = ev[mask(bars.index[ev.s.to_numpy(int)]) & np.isfinite(a[ev.s.to_numpy(int)])].reset_index(drop=True)
    if len(ev) == 0:                                   # geen setups in het venster (KATSU Live: vaak)
        return pd.DataFrame()
    ev["atr"] = a[ev.s.to_numpy(int)]
    ev = features(bars, ev, a, h1, h4, d1, PIP[mkt])
    ins = replace(INS[mkt], min_sl_atr=0.0)
    insf = free(ins)
    M, Mf = M1(bars, ins), M1(bars, insf)
    # kandidaten voor de placebo: candles van de verkenningsdata, per uur:kwartier
    ok = mask(bars.index) & np.isfinite(a)
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
               "fill_time": tr.entry_time, "exit_time": tr.exit_time if tr.status == "gesloten" else pd.NaT,
               "risk_pips": (tr.risk / PIP[mkt]) if tr.status == "gesloten" else np.nan,
               "risk_pips_free": (trf.risk / PIP[mkt]) if trf.status == "gesloten" and trf.risk else np.nan,
               "fill_px": tr.fill, "sl_px": tr.sl, "tp_px": tr.tp, "exit_px": tr.exit_price,
               **plan_cols(p, VALID_BARS)}
        cand = pool.get(int(slot[int(r.s)]), np.array([], int)) if tr.status == "gesloten" else None
        # placebo alleen als er een kandidaat bestaat buiten 5 dagen van de echte setup (bij US500 zijn sommige
        # kwartieren bijna leeg; zonder deze controle bleef de lus eindeloos zoeken). Zelfde loting als vroeger.
        if tr.status == "gesloten" and np.any((np.abs(cand - int(r.s)) >= 96 * 5) & (cand + 1 < len(bars))):
            i = int(cand[rng.integers(len(cand))])
            while abs(i - int(r.s)) < 96 * 5 or i + 1 >= len(bars):  # niet binnen 5 dagen van de echte setup
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


def main(folder, outdir, period="verkenning", markets=BASE_MARKETS, suffix=""):
    os.makedirs(outdir, exist_ok=True)
    rng = np.random.default_rng(20261012)
    allm = []
    for mkt in markets:
        t0 = time.time()
        df = run_market(folder, mkt, rng, period)
        allm.append(df)
        g = df[df.status == "gesloten"]
        print(f"{mkt}: setups {len(df)}, gevuld {len(g)}, gem R {g.r_net.mean():+.3f}, zonder kosten {g.r_free.mean():+.3f}, "
              f"placebo {g.r_placebo.mean():+.3f}, placebo zonder kosten {g.r_placebo_free.mean():+.3f} ({time.time() - t0:.0f}s)", flush=True)
    pd.concat(allm, ignore_index=True).to_pickle(os.path.join(outdir, f"dashboard_events_{period}{suffix}.pkl"))


if __name__ == "__main__":
    extra = len(sys.argv) > 4 and sys.argv[4] == "extra"
    main(*sys.argv[1:4], markets=EXTRA_MARKETS if extra else BASE_MARKETS, suffix="_extra" if extra else "")
