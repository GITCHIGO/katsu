"""
Diagnose (vraag Gitchi, 12 okt 2026): welke instapdiepte in het gat is het voordeligst?
Elke Gitchi-FVG (zonder trendvoorwaarde, geldig tot ongeldig) apart gesimuleerd met entry op 0%, 10%, ..., 100%
diep in het gat (0% = rand waar de koers eerst komt, 100% = verre rand), met en zonder kosten.
Alle setups apart (geen portefeuille), zodat alleen de entry verschilt. Alleen de VERKENNINGSHELFT.
Telt als 11 × 3 extra pogingen in het register: een "beste" diepte is hier gekozen ná het kijken en moet dus nog
op de bevestigingshelft standhouden.

Gebruik: python -m scripts.gfvg_entrydiepte <htf-map>
Schrijft: research/register_gfvg_entrydiepte.csv
"""
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

from katsu import research as R
from katsu.execution import M1, simulate
from katsu.gfvg import detect_gfvg, make_gfvg_plan
from katsu.structure import atr
from scripts.gfvg_test import INS
from scripts.ronde1 import load

FRACS = [round(x, 1) for x in np.arange(0, 1.01, 0.1)]


def frictionless(ins):
    return replace(ins, min_spread=0.0, slip=0.0, commission=0.0, swap=0.0, swap_short=0.0,
                   rollover_min_spread=0.0, point=0.0)


def main(folder):
    rows = []
    for mkt, ins in INS.items():
        bars = load(folder, mkt, "M15")
        a = atr(bars, 14).to_numpy()
        S = [s for s in detect_gfvg(bars, a) if R.explore_mask(bars.index[[s.signal_index]])[0]]
        d_real, d_free = M1(bars, ins), M1(bars, frictionless(ins))
        for f in FRACS:
            res = {"echt": [], "zonder": []}
            for s in S:
                p = make_gfvg_plan(s, bars, a, "ongeldig", mkt, entry_frac=f)
                if p is None or not np.isfinite(p.atr):
                    continue
                for key, d, i_ in (("echt", d_real, ins), ("zonder", d_free, frictionless(ins))):
                    pp = p if key == "echt" else replace(p, max_cost_r=None)
                    tr = simulate(pp, d, i_)
                    res[key].append((tr.status, tr.entry_time, tr.r_net))
            out = {"markt": mkt, "diepte": f, "setups": len(res["echt"])}
            for key, lst in res.items():
                df = pd.DataFrame(lst, columns=["status", "t", "r"])
                g = df[df.status == "gesloten"]
                wk = g.t.dt.isocalendar()
                m, se = R.clustered_t(g.r.to_numpy(float), (wk.year * 100 + wk.week).to_numpy())
                out.update({f"n_{key}": len(g), f"r_{key}": g.r.mean(), f"t_{key}": m / se if se else np.nan,
                            f"win_{key}": (g.r > 0).mean(),
                            f"vul_{key}": len(g) / max(len(df[df.status.isin(["gesloten", "niet_gevuld", "geannuleerd"])]), 1),
                            f"totaal_{key}": g.r.sum()})
            rows.append(out)
            print(f"{mkt} {f:.1f}: n={out['n_echt']} vul={out['vul_zonder']:.2f} win={out['win_echt']:.2f} "
                  f"echt={out['r_echt']:+.3f} (t {out['t_echt']:+.1f}) zonder={out['r_zonder']:+.3f} "
                  f"(t {out['t_zonder']:+.1f}) totaal_zonder={out['totaal_zonder']:+.0f}R", flush=True)
    pd.DataFrame(rows).to_csv("research/register_gfvg_entrydiepte.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main(sys.argv[1])
