"""
Stap 4: backtest op de in-sample periode (2020–2024), spec §8.

8 varianten (M5/M15 × entry A/B × L=1/3) × 3 slippage-niveaus, goud en EURUSD samen
(1 positie per markt, gezamenlijke dagstop −2R).
De out-of-sample periode (vanaf 1 jan 2025) wordt weggesneden VÓÓR er iets berekend wordt.

Gebruik: python -m scripts.backtest <xau_m1.pkl> <eur_m1.pkl> <uitmap> [sweep|bos|fvg] [label]
Schrijft: <uitmap>/trades_insample.pkl (bouwsteen 1) of trades_insample_bos.pkl (bouwsteen 2),
plus voor bos: diagnose_bos.pkl (zonder kosten + placebo, spec v0.2 §6).
"""
import os
import sys
import time

import pandas as pd

from katsu.backtest import MarketData, in_sample, metrics, placebo, run_variant, summary
from katsu.execution import EURUSD, XAUUSD

SLIPPAGE = {  # spec §5: stress laag / basis / stress hoog
    "laag": {"XAUUSD": 0.10, "EURUSD": 0.00001},
    "basis": {"XAUUSD": 0.25, "EURUSD": 0.00003},
    "hoog": {"XAUUSD": 0.50, "EURUSD": 0.00006},
}
VARIANTS = [(tf, v, L) for tf in ("5min", "15min") for v in ("A", "B") for L in (1, 3)]
# Bouwsteen 3 (FVG): de derde as is de trendfilter i.p.v. de swinglengte (spec v0.3 §6).
VARIANTS_FVG = [(tf, v, f) for tf in ("5min", "15min") for v in ("A", "B") for f in ("T0", "T+")]


def variants(block):
    return VARIANTS_FVG if block == "fvg" else VARIANTS


def main(xau_path, eur_path, outdir, block="sweep", tag=""):
    os.makedirs(outdir, exist_ok=True)
    markets = []
    for name, path, ins in (("XAUUSD", xau_path, XAUUSD), ("EURUSD", eur_path, EURUSD)):
        m1 = in_sample(pd.read_pickle(path))
        assert m1.index.max() < pd.Timestamp("2025-01-01"), "out-of-sample data gelekt"
        markets.append(MarketData(name, m1, ins))
    allt = []
    for tf, v, L in variants(block):
        for lvl, slip in SLIPPAGE.items():
            t0 = time.time()
            out = run_variant(markets, tf, v, L, slip=slip, block=block)
            out["slippage"] = lvl
            allt.append(out)
            s = summary(out, ["market"])
            print(f"{out.variant.iloc[0]:10s} {lvl:5s} "
                  + "  ".join(f"{r.market} n={r.trades} gem={r.gem_r:+.3f}" for r in s.itertuples())
                  + f"  ({time.time() - t0:.0f}s)", flush=True)
    trades = pd.concat(allt, ignore_index=True)
    name = ("trades_insample" if block == "sweep" else f"trades_insample_{block}") + tag + ".pkl"
    trades.to_pickle(os.path.join(outdir, name))
    print("klaar:", len(trades), "rijen")
    diagnose(markets, trades, outdir, block, tag)


def diagnose(markets, trades, outdir, block, tag=""):
    """Spec v0.2 §6: per variant dezelfde setups zonder kosten, en een placebo met dezelfde SL-groottes."""
    rows = []
    for tf, v, L in variants(block):
        fr = run_variant(markets, tf, v, L, block=block, frictionless=True)
        name = fr.variant.iloc[0]
        for r in summary(fr, ["market"]).itertuples():
            rows.append({"variant": name, "market": r.market, "soort": "zonder kosten",
                         "trades": r.trades, "gem_r": r.gem_r, "winrate": r.winrate})
        basis = trades[(trades.variant == name) & (trades.slippage == "basis") & (trades.status == "gesloten")]
        for md in markets:
            g = basis[basis.market == md.name]
            if len(g) < 20:
                continue
            risk_atr = (g.risk / g.atr).to_numpy()
            cap0 = 0.2 if block in ("bos", "fvg") else None          # kostenplafond hoort bij spec v0.2+
            for soort, fric, cap in (("placebo met kosten", False, cap0), ("placebo zonder kosten", True, None)):
                pl = placebo(md, tf, risk_atr, n=3000, seed=7, max_cost_r=cap, frictionless=fric)
                m = metrics(pl[pl.status == "gesloten"].sort_values("entry_time").r_net)
                rows.append({"variant": name, "market": md.name, "soort": soort,
                             "trades": m["trades"], "gem_r": m["gem_r"], "winrate": m["winrate"]})
        print("diagnose", name, flush=True)
    pd.DataFrame(rows).to_pickle(os.path.join(outdir, f"diagnose_{block}{tag}.pkl"))


if __name__ == "__main__":
    main(*sys.argv[1:6])
