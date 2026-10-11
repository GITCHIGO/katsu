"""
Ronde 2, deel B: bekende effecten buiten ICT, op D1 (docs/onderzoeksplan_edge.md §11).

- donchian(): trendvolgen. LONG als de close boven de hoogste high van de vorige N dagen sluit, instap op de
  volgende open, eerste SL 2 × ATR20, uitstap op de volgende open als de close onder de laagste low van de
  vorige M dagen komt (of op de SL). SHORT gespiegeld. Eén positie tegelijk.
- dips(): LONG als close > SMA200 en RSI(2) < drempel; uitstap op de volgende open als de close boven de
  SMA5 komt of na 10 dagen; nood-SL 3 × ATR14.
Raakt een dagcandle de SL, dan wordt gevuld op de SL (of op de open bij een gap erdoor).
Resultaat per trade in R (1R = eerste SL-afstand), met kosten (in prijs) en swap per nacht.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def atr_d(d1: pd.DataFrame, n: int) -> np.ndarray:
    pc = d1.close.shift()
    tr = pd.concat([d1.high - d1.low, (d1.high - pc).abs(), (d1.low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean().to_numpy()


def rsi(close: pd.Series, n: int = 2) -> np.ndarray:
    """RSI van Wilder."""
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(100).to_numpy()


def _run(d1, entry_sig, exit_sig, sl_dist, cost, swap, max_days=None):
    """Gemeenschappelijke trade-lus. entry_sig[i] = +1/-1/0 op de close van dag i (instap open i+1)."""
    o, h, lo, c = (d1[x].to_numpy(float) for x in ("open", "high", "low", "close"))
    t = d1.index
    n = len(c)
    trades = []
    i = 0
    while i < n - 1:
        s = entry_sig[i]
        if s == 0 or not np.isfinite(sl_dist[i]):
            i += 1; continue
        e = i + 1
        ep = o[e]
        sl = ep - s * sl_dist[i]
        risk = sl_dist[i]
        exit_px = exit_i = None; reason = None
        j = e
        while j < n:
            adv = lo[j] if s > 0 else h[j]
            if s * (adv - sl) <= 0:
                exit_px = o[j] if (j != e and s * (o[j] - sl) <= 0) else sl
                exit_i, reason = j, "SL"; break
            if exit_sig(j, s, e) and j + 1 < n:
                exit_px, exit_i, reason = o[j + 1], j + 1, "uitstap"; break
            if max_days is not None and j - e + 1 >= max_days and j + 1 < n:
                exit_px, exit_i, reason = o[j + 1], j + 1, "tijd"; break
            j += 1
        if exit_px is None:
            exit_px, exit_i, reason = c[n - 1], n - 1, "einde_data"
        nights = (t[exit_i].normalize() - t[e].normalize()).days
        r = s * (exit_px - ep) / risk
        net = r - (cost + swap(ep) * nights) / risk
        trades.append((t[e], t[exit_i], s, ep, exit_px, risk, reason, nights, r, net))
        if reason == "einde_data":
            break
        i = exit_i if reason == "SL" else exit_i - 1
        i = max(i, e)
    return pd.DataFrame(trades, columns=["entry_time", "exit_time", "d", "entry", "exit", "risk", "reden",
                                         "nachten", "R", "R_net"])


def donchian(d1: pd.DataFrame, N: int, M: int, cost: float = 0.0, swap=lambda p: 0.0) -> pd.DataFrame:
    h, lo, c = d1.high, d1.low, d1.close
    hh = h.shift(1).rolling(N).max().to_numpy(); ll_n = lo.shift(1).rolling(N).min().to_numpy()
    lowM = lo.shift(1).rolling(M).min().to_numpy(); highM = h.shift(1).rolling(M).max().to_numpy()
    cc = c.to_numpy()
    sig = np.where(cc > hh, 1, np.where(cc < ll_n, -1, 0))
    a20 = atr_d(d1, 20)

    def exit_sig(j, s, e):
        return (s > 0 and cc[j] < lowM[j]) or (s < 0 and cc[j] > highM[j])
    return _run(d1, sig, exit_sig, 2 * a20, cost, swap)


def dips(d1: pd.DataFrame, threshold: float = 10, cost: float = 0.0, swap=lambda p: 0.0) -> pd.DataFrame:
    c = d1.close
    sma200 = c.rolling(200).mean().to_numpy(); sma5 = c.rolling(5).mean().to_numpy()
    r2 = rsi(c, 2)
    cc = c.to_numpy()
    sig = np.where((cc > sma200) & (r2 < threshold), 1, 0)
    a14 = atr_d(d1, 14)

    def exit_sig(j, s, e):
        return cc[j] > sma5[j]
    return _run(d1, sig, exit_sig, 3 * a14, cost, swap, max_days=10)
