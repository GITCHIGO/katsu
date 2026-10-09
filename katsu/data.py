"""
Koersdata inladen, controleren en omzetten naar andere timeframes.

Regels (zie docs/spec_v0.1.md):
- Tijden blijven in MT5-servertijd (IC Markets: Brussel + 1 uur).
- Een candle krijgt als tijd het BEGIN van de periode (M5 van 10:05 = 10:05:00–10:09:59).
- Er wordt nooit een candle gebruikt die nog niet gesloten is.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

COLUMNS = ["open", "high", "low", "close", "tickvol", "spread"]


def load_mt5_csv(path: str) -> pd.DataFrame:
    """Leest een MT5-export (tab-gescheiden, kolommen <DATE> <TIME> <OPEN> ...)."""
    raw = pd.read_csv(path, sep="\t")
    raw.columns = [c.strip("<>").lower() for c in raw.columns]
    idx = pd.to_datetime(raw["date"] + " " + raw["time"], format="%Y.%m.%d %H:%M:%S")
    df = raw[COLUMNS].copy()
    df.index = idx
    df.index.name = "time"
    return df


@dataclass
class DataReport:
    rows: int
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    duplicates: int
    high_below_low: int
    open_close_outside_range: int
    unsorted: bool
    gaps_over_3h_weekdays: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (self.duplicates == 0 and self.high_below_low == 0
                and self.open_close_outside_range == 0 and not self.unsorted)


def validate(df: pd.DataFrame) -> DataReport:
    """Controleert de data op fouten die een backtest stil zouden vervalsen."""
    oc_out = ((df.open > df.high) | (df.open < df.low) |
              (df.close > df.high) | (df.close < df.low)).sum()
    t = df.index.to_series()
    gap = t.diff()
    # Gaten van meer dan 3 uur die niet het gewone weekend zijn.
    weekend = (t.dt.dayofweek == 0) & (gap < pd.Timedelta(days=3.5))
    gaps = gap[(gap > pd.Timedelta(hours=3)) & ~weekend]
    return DataReport(
        rows=len(df),
        start=df.index.min() if len(df) else None,
        end=df.index.max() if len(df) else None,
        duplicates=int(df.index.duplicated().sum()),
        high_below_low=int((df.high < df.low).sum()),
        open_close_outside_range=int(oc_out),
        unsorted=not df.index.is_monotonic_increasing,
        gaps_over_3h_weekdays=[(ts, g) for ts, g in gaps.items()],
    )


def resample(m1: pd.DataFrame, tf: str) -> pd.DataFrame:
    """
    Zet M1 om naar een hogere timeframe ('5min', '15min', '1h').
    Label = begintijd van de candle. Lege periodes (markt dicht) verdwijnen.
    """
    agg = {"open": "first", "high": "max", "low": "min", "close": "last",
           "tickvol": "sum", "spread": "max"}
    out = m1.resample(tf, label="left", closed="left").agg(agg).dropna(subset=["open"])
    return out


def last_closed_index(bars: pd.DataFrame, tf: str, now: pd.Timestamp) -> int:
    """
    Index van de laatste candle die op tijdstip `now` volledig gesloten is.
    Een candle met begintijd b is gesloten vanaf b + duur.
    Geeft -1 als er nog geen enkele gesloten candle is.
    """
    duration = pd.Timedelta(tf)
    closed_starts = bars.index[bars.index + duration <= now]
    if len(closed_starts) == 0:
        return -1
    return int(bars.index.get_loc(closed_starts[-1]))
