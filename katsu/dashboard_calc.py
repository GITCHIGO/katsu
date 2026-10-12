"""
Rekenregels van het bouwstenen-dashboard, in Python (de pagina is een spiegel; tests vergelijken beide).

- Dollars bij vast lot: netto pips × 10 $ × lot (EURUSD, GBPUSD en goud: 10 $ per pip per lot; goud-pip = 0,1 $).
  Voor varianten zonder pips (zonder kosten, placebo): R × SL-afstand in pips × 10 $ × lot.
- Eén trade tegelijk per markt (benadering): op volgorde van vulling; een trade telt alleen als de vorige trade in
  dezelfde markt al gesloten is (vultijd ≥ sluittijd van de vorige).
- t-waarde geclusterd per week: se = √(Σ_week (Σ (x − gemiddelde))²) / n.
"""
import numpy as np
import pandas as pd

USD_PER_PIP_PER_LOT = 10.0


def usd(df: pd.DataFrame, lots: dict, col: str = "r_net") -> pd.Series:
    lot = df["markt"].map(lots).astype(float)
    if col == "r_net":
        return df["pips"] * USD_PER_PIP_PER_LOT * lot
    risk = df["risk_pips_free"] if col in ("r_free", "r_placebo_free") else df["risk_pips"]
    return df[col] * risk * USD_PER_PIP_PER_LOT * lot


def one_at_a_time(df: pd.DataFrame) -> pd.DataFrame:
    """Gevulde trades (gesorteerd op vultijd); per markt pas een nieuwe als de vorige gesloten is."""
    g = df[(df["vulling"] == "gevuld") & df["r_net"].notna()].sort_values("fill_time", kind="stable")
    keep, last = [], {}
    for idx, m, f, x in zip(g.index, g["markt"], g["fill_time"], g["exit_time"]):
        if m in last and f < last[m]:
            continue
        last[m] = x if pd.notna(x) else f
        keep.append(idx)
    return g.loc[keep]


def clustered_t(x: np.ndarray, week: np.ndarray) -> float:
    x = np.asarray(x, float); n = len(x)
    if n < 2:
        return float("nan")
    d = pd.Series(x - x.mean()).groupby(np.asarray(week)).sum().to_numpy()
    se = np.sqrt((d ** 2).sum()) / n
    return float(x.mean() / se) if se > 0 else float("nan")


def max_drawdown(x: np.ndarray) -> float:
    c = np.cumsum(np.asarray(x, float))
    peak = np.maximum.accumulate(np.concatenate([[0.0], c]))[1:]
    return float((peak - c).max()) if len(c) else 0.0
