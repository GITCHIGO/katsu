"""
KATSU Live naspelen op historische data (proef vóór de VPS): het echte orderbeheer (katsu/live/orders.Manager) met
een nep-MT5 die koersen krijgt uit de M15-candles, en daarna de controle backtest ↔ 'broker' (katsu/live/report.control).
Zo zien we vooraf hoeveel trades live naar verwachting gelijk lopen met de backtest.

Signalen: dezelfde rijen als de vooruit-test, op het moment t_sig aangeboden aan het orderbeheer. Dat is gelijk aan
wat de live-scan vindt (getest in tests/test_live.py en met 69 afgekapte scans: geen vooruitkijken).
Koersen per candle: open → eerst de kant die het verst van de close ligt → andere kant → close (ruwe benadering;
binnen één candle weten we de echte volgorde niet — de backtest neemt daar steeds de ongunstigste kant).

Gebruik: python -m scripts.live_replay <htf-map> <start> <einde> [uit.json]
"""
import json
import sys
from dataclasses import asdict

import numpy as np
import pandas as pd

from katsu.execution import M1
from katsu.live.fake import FakeBroker
from katsu.live.orders import Manager
from katsu.live.report import control, results
from katsu.live.scan import signal_from_row
from katsu.presets import PRESETS, preset_mask
from scripts.dashboard_build import INS
from scripts.eindtest_gfvg import load_full
from scripts.vooruittest import needed_kinds, rows_for

LOTS = {"EURUSD": 0.10, "GBPUSD": 0.10, "XAUUSD": 0.02}


def ticks_for(bars, ins):
    """(tijd, bid, ask, geleidelijk?) per candle: open, twee uitersten, close. Spread zoals de backtest (minimum + rollover)."""
    sp = M1(bars, ins).sp
    out = []
    for i, (t, r) in enumerate(bars.iterrows()):
        up_first = (r.close < r.open)                   # rode candle: eerst omhoog, dan omlaag
        ex = [r.high, r.low] if up_first else [r.low, r.high]
        for dt, px in ((0, r.open), (5, ex[0]), (10, ex[1]), (14.98, r.close)):
            out.append((t + pd.Timedelta(minutes=dt), px, px + sp[i], dt > 0))
    return out


def replay(folder, start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    bars = {m: load_full(folder, m) for m in needed_kinds()}
    bars = {m: b[b.index < end] for m, b in bars.items()}
    lo = start - pd.Timedelta(days=3)
    rows = rows_for(bars, lambda t: np.asarray(t >= lo), np.random.default_rng(20261021))
    rows = rows[(rows.t_sig >= start) & (rows.t_sig < end)]
    sigs = []
    for name in PRESETS:
        for _, r in rows[preset_mask(rows, name)].iterrows():
            sigs.append(signal_from_row(r, name))
    sigs.sort(key=lambda s: s.t_sig)
    print(f"{len(sigs)} signalen in het venster", flush=True)

    fb = FakeBroker()
    mgr = Manager(fb, {m: INS[m] for m in LOTS}, LOTS, None, "orders")
    seq = []
    for m, b in bars.items():
        w = b[(b.index >= start - pd.Timedelta(days=1)) & (b.index < end)]
        for t, bid, ask, path in ticks_for(w, INS[m]):
            seq.append((t, 1, m, bid, (ask, path)))
        for t in w.index:
            seq.append((t + pd.Timedelta(minutes=15, seconds=10), 0, m, None, None))   # candle gesloten
    for s in sigs:
        seq.append((s.t_sig + pd.Timedelta(seconds=10), 2, s, None, None))
    seq.sort(key=lambda x: (x[0], x[1]))
    closed = {m: 0 for m in bars}
    events = []
    for t, kind, x, bid, extra in seq:
        if kind == 0:                                   # candle dicht: nep-broker kent de gesloten candles
            closed[x] += 1
            b = bars[x]
            n = int(b.index.searchsorted(t - pd.Timedelta(minutes=15, seconds=10), side="right"))
            fb.bars[x] = b.iloc[:n]
            mgr.on_bars({x: fb.bars[x]}, t)
        elif kind == 2:
            if x.market in fb.ticks:
                mgr.add_signal(x, t)
        else:
            fb.set_price(x, bid, extra[0], t, path=extra[1])
            mgr.step(t)
        events.extend(mgr.drain())
    mgr.step(end)
    orders = [asdict(o) for o in mgr.orders.values()]
    ctl = control(orders, bars, start)
    res = results(orders)
    replay.last = (mgr, fb, bars, events)                      # voor de dashboard-preview
    return orders, ctl, res


if __name__ == "__main__":
    folder, start, end = sys.argv[1:4]
    orders, ctl, res = replay(folder, start, end)
    a = res["algemeen"]
    states = pd.Series([o["state"] for o in orders]).value_counts().to_dict()
    print("orders per toestand:", states)
    print(f"'broker'-trades: {a['trades']} · winrate {a['winrate']} · totaal {a['totaal_R']:+.2f}R")
    print(f"controle: {ctl['n_gelijk']}/{ctl['n_trades']} gelijk = {ctl['overeenkomst']}")
    print(pd.Series([t["status"] for t in ctl["trades"]]).value_counts().to_string())
    if len(sys.argv) > 4:
        with open(sys.argv[4], "w") as fh:
            json.dump({"orders": orders, "controle": ctl}, fh, default=str, ensure_ascii=False, indent=1)
