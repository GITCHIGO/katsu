"""
Controle vóór de start (stappenplan stap 5). LEEST ALLEEN: plaatst geen enkele order.
    python -m katsu.live.check C:\\katsu\\config.toml            verbinding, account, symbolen, data
    python -m katsu.live.check C:\\katsu\\config.toml discord    + testbericht naar Discord
Bewaart ook de M15-candles in <data_dir>\\bars (bruikbaar voor de vooruit-test).
"""
from __future__ import annotations

import os
import sys

import pandas as pd

from katsu.live.broker import Broker, server_now, server_to_be
from katsu.live.config import MARKETS, load_config, paths
from katsu.live.notify import Discord
from katsu.live.runner import BARS_COUNT
from katsu.live.scan import closed_bars


def main(cfg_path: str, discord: bool = False) -> int:
    ok = True

    def line(good, text):
        nonlocal ok
        ok &= bool(good)
        print(("  OK    " if good else "  FOUT  ") + text, flush=True)

    print("KATSU Live — controle (alleen lezen)\n")
    cfg = load_config(cfg_path)
    p = paths(cfg)
    line(True, f"config gelezen · stand {cfg.mode} · lots {cfg.lots} · data in {cfg.data_dir}")
    b = Broker(cfg.terminal, cfg.login, cfg.password, cfg.server, cfg.symbols)
    acc = b.connect()
    line(acc.demo or cfg.allow_live, f"account {acc.login} op {acc.server} · {'DEMO' if acc.demo else 'LIVE (!)'} · "
                                     f"{acc.currency} · saldo {acc.balance:,.2f}")
    now = server_now()
    print(f"\n  servertijd volgens KATSU: {now:%Y-%m-%d %H:%M:%S} (België {server_to_be(now):%H:%M})")
    for m in MARKETS:
        print(f"\n  {m} (bij de broker: {b.sym(m)})")
        si = b.symbol(m)
        line(True, f"digits {si.digits} · contract {si.contract_size:g} · lot min {si.volume_min} stap {si.volume_step} · "
                   f"stops level {si.stops_level} · filling {si.filling_mode}")
        line(si.volume_min <= cfg.lots[m], f"jouw lot {cfg.lots[m]} ≥ minimum {si.volume_min}")
        tk = b.tick(m)
        if tk is None:
            line(False, "geen koers (markt dicht of symbool niet in Marktoverzicht)")
        else:
            age = (now - tk.time).total_seconds()
            print(f"        koers bid {tk.bid} ask {tk.ask} · spread {(tk.ask - tk.bid) / si.point:.0f} points · "
                  f"laatste tick {tk.time:%Y-%m-%d %H:%M:%S}")
            if abs(age) < 120:
                line(True, "ticktijd klopt met de berekende servertijd (New York + 7 u)")
            elif age > 0:
                print("        (laatste tick ouder dan 2 min: markt waarschijnlijk dicht — tijd niet te controleren)")
            else:
                line(False, f"ticktijd ligt {-age:.0f}s VOOR op de berekende servertijd: servertijd-regel klopt niet")
        bars = closed_bars(b.rates(m, BARS_COUNT), now)
        months = (bars.index[-1] - bars.index[0]).days / 30.4 if len(bars) else 0
        line(months >= 19, f"{len(bars)} gesloten M15-candles · {bars.index[0]:%Y-%m-%d} t/m {bars.index[-1]:%Y-%m-%d %H:%M} "
                           f"· {months:.1f} maanden (nodig: ≥ 19; anders 'Max. bars in chart' verhogen)")
        gaps = bars.index.to_series().diff().dt.total_seconds().div(60)
        weekday_gaps = gaps[(gaps > 15) & (gaps < 60 * 24) & (bars.index.dayofweek < 5)]
        print(f"        gaten in de data op weekdagen (> 15 min, < 1 dag): {len(weekday_gaps)}")
        bars.to_pickle(os.path.join(p["bars"], f"{m}_M15_live.pkl"))
        print(f"        bewaard: {os.path.join(p['bars'], f'{m}_M15_live.pkl')}")
    if discord:
        print()
        d = Discord(cfg.webhook)
        line(d.send("🧪 KATSU Live: testbericht. Als je dit ziet, werkt Discord."),
             "testbericht naar Discord" + (f" — {d.last_error}" if d.last_error else ""))
        w = cfg.webhook.strip()
        print(f"        webhook in config: {len(w)} tekens, begint met {w[:40]!r}, eindigt op …{w[-4:]!r}")
    b.shutdown()
    print("\nALLES OK" if ok else "\nEr zijn FOUTEN — los die eerst op (zie hierboven).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else r"C:\katsu\config.toml",
                  discord=len(sys.argv) > 2 and sys.argv[2] == "discord"))
