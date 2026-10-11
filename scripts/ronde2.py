"""
Ronde 2 (docs/onderzoeksplan_edge.md §11), alleen op de VERKENNINGSHELFT.

Gebruik: python -m scripts.ronde2 <map met htf-pickles> <uitmap>
Schrijft: <uitmap>/ronde2_trades.pkl en research/register_ronde2.csv
"""
import os
import sys

import numpy as np
import pandas as pd

from katsu import ict, trend
from katsu import research as R
from katsu.structure import atr
from scripts.ronde1 import COST, MARKETS, load

RR = 1.5
SWAP = {"EURUSD": lambda p: 0.00008, "GBPUSD": lambda p: 0.00008, "XAUUSD": lambda p: 0.40,
        "XAGUSD": lambda p: 0.005, "US500": lambda p: p * 0.05 / 365}       # voorzichtig, beide richtingen


def week_id(times):
    wk = pd.DatetimeIndex(times).isocalendar()
    return (wk.year * 100 + wk.week).to_numpy()


def part_a(folder):
    rows, m15s, lvs = [], {}, {}
    for mkt in MARKETS:
        m15s[mkt] = load(folder, mkt, "M15")
        lvs[mkt] = ict.day_levels(m15s[mkt])
    for mkt in MARKETS:
        b, lv = m15s[mkt], lvs[mkt]
        a = atr(b, 14).to_numpy()
        explore = R.explore_mask(b.index)
        pool = np.where(explore[: len(b) - 100])[0]
        fams = {"London Judas": ict.judas_events(b, lv), "Silver Bullet": ict.silver_bullet_events(b, lv),
                "Monday range": ict.monday_events(b), "Dagbias-trade": ict.bias_events(b, lv),
                "London close": ict.london_close_events(b, lv)}
        for fam, ev in fams.items():
            if len(ev) == 0:
                continue
            ev = ev[explore[ev.k.to_numpy(int)]].reset_index(drop=True)
            day = b.index[ev.k.to_numpy(int)].normalize()
            ev["bias_mee"] = lv.bias.reindex(day).to_numpy() == ev.d.to_numpy()
            ev["smal"] = ((lv.asia_h - lv.asia_l) < 0.3 * lv.adr5).reindex(day).to_numpy()
            ev["ma_wo"] = np.asarray(day.dayofweek <= 2)
            if fam == "London Judas" and mkt in ("EURUSD", "GBPUSD"):
                other = "GBPUSD" if mkt == "EURUSD" else "EURUSD"
                ob, olv = m15s[other], lvs[other]
                smt = []
                for kk, dd, dy in zip(ev.k, ev.d, day):
                    tt = b.index[kk]
                    if dy not in olv.index:
                        smt.append(False); continue
                    w = ob[(ob.index >= dy + pd.Timedelta(hours=9)) & (ob.index <= tt)]
                    lvl = olv.at[dy, "asia_l"] if dd > 0 else olv.at[dy, "asia_h"]
                    swept = (w.low < lvl).any() if dd > 0 else (w.high > lvl).any()
                    smt.append(bool(not swept) and np.isfinite(lvl))
                ev["smt"] = smt
            lim = ev.limit.to_numpy() if "limit" in ev else None
            vb = ev.valid_bar.to_numpy() if "valid_bar" in ev else None
            m = ict.measure_trades(b, a, ev.k.to_numpy(), ev.d.to_numpy(), ev.anchor.to_numpy(),
                                   ev.exit_bar.to_numpy(), rr=RR, limit=lim, valid_bar=vb, cost=COST[mkt])
            ev = pd.concat([ev, m], axis=1)
            ok = ev.status == "ok"
            ra = (ev.risk / a[ev.k.to_numpy(int)]).to_numpy()
            bl = ict.baseline_trades(b, a, ev.k[ok].to_numpy(), ev.d[ok].to_numpy(), ra[ok.to_numpy()], pool,
                                     rr=RR, per_event=5, seed=21, cost=COST[mkt])
            ev["base_R"] = np.nan
            ev.loc[ok, "base_R"] = np.nanmean(bl.R.to_numpy().reshape(-1, 5), axis=1)
            ev["market"], ev["fam"], ev["time"] = mkt, fam, b.index[ev.k.to_numpy(int)]
            rows.append(ev)
            print(f"A {mkt} {fam}: {int(ok.sum())} trades", flush=True)
    return pd.concat(rows, ignore_index=True)


VARIANTS_A = {"London Judas": ["alle", "bias_mee", "smal", "ma_wo", "smal+bias", "smt"],
              "Silver Bullet": ["alle", "bias_mee"], "Monday range": ["alle", "bias_mee"],
              "Dagbias-trade": ["alle"], "London close": ["alle"]}


def register_a(ev):
    out = []
    ev = ev[ev.status == "ok"].copy()
    ev["jaar"] = ev.time.dt.year
    for (mkt, fam), g in ev.groupby(["market", "fam"]):
        for v in VARIANTS_A[fam]:
            if v == "alle":
                s = g
            elif v == "smal+bias":
                s = g[g.smal.astype(bool) & g.bias_mee.astype(bool)]
            elif v == "smt":
                if "smt" not in g or g.smt.isna().all():
                    continue
                s = g[g.smt.fillna(False).astype(bool)]
            else:
                s = g[g[v].fillna(False).astype(bool)]
            s = s[s.base_R.notna()]
            diff = (s.R - s.base_R).to_numpy()
            m, se = R.clustered_t(diff, week_id(s.time))
            yrs = s.groupby("jaar").R_net.mean()
            out.append({"deel": "A", "markt": mkt, "model": fam, "variant": v, "trades": len(s),
                        "winrate": s.win.mean(), "gem_R_netto": s.R_net.mean(), "basis_R": s.base_R.mean(),
                        "edge": m, "t": m / se if se else np.nan,
                        "voor_2020": s[s.jaar < 2020].R_net.mean(), "2020_24": s[s.jaar >= 2020].R_net.mean(),
                        "jaren_positief": float((yrs > 0).mean()) if len(yrs) else np.nan})
    reg = pd.DataFrame(out)
    sup = [int(((reg.model == r.model) & (reg.variant == r.variant) & (reg.markt != r.markt) &
                (np.sign(reg.t) == np.sign(r.t)) & (reg.t.abs() >= 1)).sum()) for r in reg.itertuples()]
    reg["andere_markten_mee"] = sup
    need = np.where(reg.andere_markten_mee >= 1, 3.0, 3.5)
    halves = (reg.voor_2020.isna() | (reg.voor_2020 > 0)) & (reg["2020_24"] > 0)
    reg["poort"] = (reg.trades >= 100) & (reg.gem_R_netto >= 0.10) & (reg.t >= need) & halves & \
        (reg.jaren_positief > 0.5)
    return reg


def part_b(folder):
    rows, alltr = [], []
    for mkt in MARKETS:
        h1 = load(folder, mkt, "H1")
        agg = {"open": "first", "high": "max", "low": "min", "close": "last"}
        d1 = h1[["open", "high", "low", "close"]].resample("1D").agg(agg).dropna()
        d1 = d1[d1.index.dayofweek < 5]
        for name, fn in (("Donchian 20/10", lambda: trend.donchian(d1, 20, 10, COST[mkt], SWAP[mkt])),
                         ("Donchian 55/20", lambda: trend.donchian(d1, 55, 20, COST[mkt], SWAP[mkt])),
                         ("Dips RSI2<10", lambda: trend.dips(d1, 10, COST[mkt], SWAP[mkt])),
                         ("Dips RSI2<5", lambda: trend.dips(d1, 5, COST[mkt], SWAP[mkt]))):
            tr = fn()
            tr = tr[R.explore_mask(pd.DatetimeIndex(tr.entry_time))]
            tr["market"], tr["model"] = mkt, name
            alltr.append(tr)
    tr = pd.concat(alltr, ignore_index=True)
    tr["jaar"] = tr.entry_time.dt.year
    for (model, mkt), g in list(tr.groupby(["model", "market"])) + \
            [((m, "ALLE 5"), g) for m, g in tr.groupby("model")]:
        x = g.R_net.to_numpy()
        se = x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan
        yrs = g.groupby("jaar").R_net.mean()
        rows.append({"deel": "B", "markt": mkt, "model": model, "variant": "-", "trades": len(g),
                     "winrate": float((g.R_net > 0).mean()), "gem_R_netto": x.mean(), "basis_R": np.nan,
                     "edge": x.mean(), "t": x.mean() / se if se else np.nan,
                     "voor_2020": g[g.jaar < 2020].R_net.mean(), "2020_24": g[g.jaar >= 2020].R_net.mean(),
                     "jaren_positief": float((yrs > 0).mean())})
    reg = pd.DataFrame(rows)
    reg["andere_markten_mee"] = np.nan
    halves = (reg.voor_2020.isna() | (reg.voor_2020 > 0)) & (reg["2020_24"] > 0)
    reg["poort"] = (reg.trades >= 100) & (reg.gem_R_netto >= 0.10) & (reg.t >= 2.5) & halves & \
        (reg.jaren_positief > 0.5)
    return reg, tr


def main(folder, outdir):
    os.makedirs(outdir, exist_ok=True)
    ev = part_a(folder)
    ev.to_pickle(os.path.join(outdir, "ronde2_A_trades.pkl"))
    regA = register_a(ev)
    regB, trB = part_b(folder)
    trB.to_pickle(os.path.join(outdir, "ronde2_B_trades.pkl"))
    reg = pd.concat([regA, regB], ignore_index=True)
    reg.to_csv("research/register_ronde2.csv", index=False, float_format="%.4f")
    with pd.option_context("display.width", 250, "display.max_rows", 200):
        print(reg.round(3).to_string(index=False))
    print(f"{len(reg)} combinaties; {int(reg.poort.sum())} door de poort")


if __name__ == "__main__":
    main(*sys.argv[1:3])
