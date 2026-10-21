"""
Nieuwe MT5-data toevoegen voor de vooruit-test (docs/vooruittest_plan.md §3).

Gitchi exporteert in MT5 per markt de M15-candles (Weergave → Symbolen → Balken → Exporteren; tab-gescheiden,
kolommen <DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>). De bestandsnaam moet de markt bevatten,
bv. EURUSD_M15_okt.csv. Dit script voegt ze samen met de bestaande data (vanaf 2023, voor de opwarming), controleert
ze en schrijft per markt <uit>/<MARKT>_M15_vooruit.pkl.
Gebruik: python -m scripts.vooruit_data <htf-map> <uitmap> <csv> [<csv> ...]
"""
import glob
import os
import sys

import pandas as pd

from katsu.data import load_mt5_csv, validate

MARKETS = ("EURUSD", "GBPUSD", "XAUUSD", "XAGUSD", "US500")


def market_of(path: str) -> str:
    name = os.path.basename(path).upper()
    hits = [m for m in MARKETS if m in name]
    if len(hits) != 1:
        raise ValueError(f"kan de markt niet uit de bestandsnaam halen: {path}")
    return hits[0]


def merge(base: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Nieuwe candles winnen bij dezelfde tijd; gesorteerd; zonder dubbele tijden."""
    both = pd.concat([base, new])
    both = both[~both.index.duplicated(keep="last")].sort_index()
    return both


def main(htf, out, *csvs):
    os.makedirs(out, exist_ok=True)
    new = {}
    for c in csvs:
        m = market_of(c)
        new[m] = merge(new.get(m, pd.DataFrame()), load_mt5_csv(c))
    for m, df in new.items():
        f = sorted(glob.glob(os.path.join(htf, f"{m}_M15_*.pkl")))
        base = pd.read_pickle(f[0]) if f else pd.DataFrame()
        base = base[base.index >= "2023-01-01"] if len(base) else base
        merged = merge(base, df)
        rep = validate(merged)
        merged.to_pickle(os.path.join(out, f"{m}_M15_vooruit.pkl"))
        print(f"{m}: {len(df)} nieuwe candles ({df.index[0]} → {df.index[-1]}), samen t/m {merged.index[-1]} · "
              f"controle: dubbel {rep.duplicates}, high<low {rep.high_below_low}, open/close buiten bereik "
              f"{rep.open_close_outside_range}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], *sys.argv[3:])
