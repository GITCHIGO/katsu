"""
KATSU Live — hoofdprogramma (spec §2). Start op de VPS met:
    python -m katsu.live.runner C:\\katsu\\config.toml

Ritme:
- elke 10 s: orderbeheer (vullingen, sluitingen, geldigheid, SL/TP aanwezig, noodknop);
- 10 s na het sluiten van elke M15-candle: gesloten candles ophalen (24 maanden), nieuwe setups zoeken, orders;
- elk uur: controle backtest ↔ broker herberekenen;
- 23:00 Belgische tijd: dagoverzicht op Discord.
Een fout in één ronde stopt het programma niet: ze gaat naar het log en Discord, de volgende ronde probeert opnieuw.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from katsu.live.broker import Broker, server_now, server_to_be
from katsu.live.config import MARKETS, load_config, paths
from katsu.live.notify import Discord, Logbook, format_event
from katsu.live.orders import Manager
from katsu.live.report import control, results
from katsu.live.scan import HISTORY_MONTHS, STEP, closed_bars, scan
from katsu.live.web import Snapshot, make_app
from scripts.dashboard_build import INS

BARS_COUNT = 52_000            # ±24 maanden M15 (+ marge); MT5 'Max. bars in chart' moet hoger staan
TICK_S = 10
SCAN_DELAY = pd.Timedelta(seconds=10)


def next_scan_time(now: pd.Timestamp) -> pd.Timestamp:
    """10 s na het einde van de lopende M15-candle (of van de net gesloten, als die 10 s nog niet voorbij zijn)."""
    t = now.floor("15min") + SCAN_DELAY
    return t if now < t else t + STEP


class Runner:
    def __init__(self, cfg, broker=None, now_fn=server_now):
        self.cfg = cfg
        self.p = paths(cfg)
        self.broker = broker or Broker(cfg.terminal, cfg.login, cfg.password, cfg.server, cfg.symbols)
        self.now_fn = now_fn
        self.log = Logbook(self.p["log"])
        self.discord = Discord(cfg.webhook)
        self.snap = Snapshot()
        self.account = None
        self.connected = False
        self.mgr: Manager | None = None
        self.bars: dict = {}
        self.next_scan: pd.Timestamp | None = None
        self.last_scan_done: pd.Timestamp | None = None
        self.control: dict = {}
        self.control_time: pd.Timestamp | None = None
        self.errors: list = []
        self.summary_day: str | None = None
        self.started: pd.Timestamp | None = None
        self.disconnected_since: pd.Timestamp | None = None
        self.daily_day = None

    # ------------------------------------------------------------ meldingen
    def note(self, kind, text, discord=True, now=None):
        ev = {"time": str(now or self.now_fn()), "kind": kind, "text": text}
        self.log.write(ev)
        if kind == "fout":
            self.errors = ([ev] + self.errors)[:5]
        if discord and kind in self.cfg.discord_kinds:
            self.discord.send(f"{'🚨' if kind == 'fout' else 'ℹ️'} **{kind}** · {text}")

    def flush_events(self):
        for ev in self.mgr.drain():
            self.log.write(asdict(ev))
            if ev.kind == "fout":
                self.errors = ([asdict(ev)] + self.errors)[:5]
            if ev.discord and ev.kind in self.cfg.discord_kinds:
                self.discord.send(format_event(ev))

    # ------------------------------------------------------------ start
    def start(self):
        acc = self.broker.connect()
        if not acc.demo and not self.cfg.allow_live:
            raise SystemExit(f"KATSU weigert: account {acc.login} is GEEN demo-account. (Alleen demo tot de vooruit-test "
                             "iets bewezen heeft; zie spec §6.)")
        self.account = acc
        self.connected = True
        for m in MARKETS:
            self.broker.symbol(m)                       # bestaat het symbool? anders stopt KATSU hier
        self.mgr = Manager(self.broker, {m: INS[m] for m in MARKETS}, self.cfg.lots, self.p["state"], self.cfg.mode)
        meta = os.path.join(self.p["data"], "start.txt")
        if os.path.exists(meta):
            self.started = pd.Timestamp(open(meta).read().strip())
        else:
            self.started = self.now_fn().floor("15min")
            open(meta, "w").write(str(self.started))
        self.note("info", f"KATSU Live gestart · account {acc.login} ({'demo' if acc.demo else 'LIVE'}, {acc.currency}) · "
                          f"stand {self.cfg.mode} · lots {self.cfg.lots}")

    # ------------------------------------------------------------ scan
    def load_bars(self, now) -> dict:
        out = {}
        cut = now - pd.DateOffset(months=HISTORY_MONTHS)
        for m in MARKETS:
            b = closed_bars(self.broker.rates(m, BARS_COUNT), now)
            out[m] = b[b.index >= cut]
        return out

    def do_scan(self, now):
        t0 = time.time()
        self.bars = self.load_bars(now)
        until = now.floor("15min")                          # einde van de laatst gesloten candle
        since = pd.Timestamp(self.mgr.last_scan) if self.mgr.last_scan else until - STEP
        since = max(since, until - pd.Timedelta(days=7))    # na lange stilstand: max. een week terugkijken
        sigs, missed, _ = scan(self.bars, since, until)
        for s in sigs:
            self.mgr.add_signal(s, now)
        for s in missed:
            self.mgr.missed(s, now)
        self.mgr.on_bars(self.bars, now)
        self.mgr.last_scan = str(until)
        self.mgr.save()
        for m, b in self.bars.items():                     # ook bruikbaar voor de vooruit-test (scripts/vooruittest.py)
            b.to_pickle(os.path.join(self.p["bars"], f"{m}_M15_live.pkl"))
        self.last_scan_done = now
        self.note("scan", f"scan tot {until:%d-%m %H:%M} · {len(sigs)} nieuw, {len(missed)} gemist · "
                          f"{time.time() - t0:.1f}s", discord=False, now=now)

    def do_control(self, now):
        if not self.bars:
            return
        orders = [asdict(o) for o in self.mgr.orders.values()]
        self.control = control(orders, self.bars, self.started)
        self.control_time = now
        import json
        with open(self.p["control"], "w", encoding="utf-8") as fh:
            json.dump(self.control, fh, ensure_ascii=False, default=str, indent=1)

    # ------------------------------------------------------------ dagoverzicht
    def daily_summary(self):
        be_now = datetime.now(ZoneInfo("Europe/Brussels"))
        day = be_now.strftime("%Y-%m-%d")
        if be_now.hour < 23 or self.summary_day == day:
            return
        self.summary_day = day
        orders = [asdict(o) for o in self.mgr.orders.values()]
        cur = self.account.currency if self.account else ""

        def be_exit(o):
            return server_to_be(pd.Timestamp(o["exit_time"])) if o.get("exit_time") else None
        today = [o for o in orders if be_exit(o) is not None and be_exit(o).date() == be_now.date()]
        month = [o for o in orders if be_exit(o) is not None and (be_exit(o).year, be_exit(o).month) == (be_now.year, be_now.month)]
        a, am = results(today)["algemeen"], results(month)["algemeen"]
        wr = "—" if am["winrate"] is None else f"{am['winrate']:.0%}"
        lines = [f"📊 **Dagoverzicht {be_now:%d-%m-%Y}** · stand {self.cfg.mode}",
                 f"Vandaag: {a['trades']} trades · netto {a['netto']:+.2f} {cur} · {a['totaal_R']:+.2f}R",
                 f"Deze maand: {am['trades']} trades · winrate {wr} · netto {am['netto']:+.2f} {cur} · {am['totaal_R']:+.2f}R",
                 f"Open: {sum(o['state'] == 'gevuld' for o in orders)} trades · "
                 f"{sum(o['state'] in ('geplaatst', 'wacht') for o in orders)} orders"]
        if self.control.get("overeenkomst") is not None:
            lines.append(f"Controle backtest ↔ MT5: {self.control['overeenkomst']:.0%} ({self.control['n_gelijk']}/{self.control['n_trades']})")
        if "overzicht" in self.cfg.discord_kinds:
            self.discord.send("\n".join(lines))
        self.log.write({"time": str(self.now_fn()), "kind": "overzicht", "text": " | ".join(lines[1:])})

    # ------------------------------------------------------------ momentopname voor het dashboard
    def publish(self, now):
        orders = [asdict(o) for o in self.mgr.orders.values()]
        live_r = {}
        for o in orders:
            if o["state"] == "gevuld" and o.get("risk_px"):
                tk = self.broker.tick(o["market"])
                if tk is not None:
                    p = tk.bid if o["direction"] == "LONG" else tk.ask
                    live_r[o["id"]] = (1 if o["direction"] == "LONG" else -1) * (p - o["fill_px"]) / o["risk_px"]
        today = now.normalize()
        self.snap.set({
            "now": str(now), "connected": self.connected, "mode": self.cfg.mode, "paused": self.mgr.paused,
            "account": None if self.account is None else asdict(self.account),
            "cur": {"EUR": "€", "USD": "$"}.get(self.account.currency, self.account.currency + " ") if self.account else "€",
            "last_scan_done": None if self.last_scan_done is None else str(self.last_scan_done),
            "next_scan": None if self.next_scan is None else str(self.next_scan),
            "orders": [o for o in orders if o["state"] in ("geplaatst", "wacht", "gevuld")]
                      + [o for o in orders if o["state"] == "log"][-10:],
            "live_r": live_r,
            "closed_today": sum(o["state"] == "gesloten" and o.get("exit_time") and pd.Timestamp(o["exit_time"]) >= today
                                for o in orders),
            "results_month": results(orders, since=now.normalize().replace(day=1)),
            "results_all": results(orders),
            "control": self.control, "control_time": None if self.control_time is None else str(self.control_time),
            "errors": self.errors,
        })

    # ------------------------------------------------------------ voor de agent (docs/agent_spec.md)
    def write_status(self, now):
        """Hartslag voor de waakhond en de agent; aan het einde van elke ronde van 10 s."""
        orders = list(self.mgr.orders.values()) if self.mgr else []
        st = {"tijd_server": str(now), "tijd_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "verbonden": self.connected,
              "niet_verbonden_sinds": None if self.disconnected_since is None else str(self.disconnected_since),
              "stand": self.cfg.mode, "gepauzeerd": bool(self.mgr and self.mgr.paused),
              "account": None if self.account is None else asdict(self.account),
              "laatste_scan": None if self.last_scan_done is None else str(self.last_scan_done),
              "open_trades": [o.id for o in orders if o.state == "gevuld"],
              "open_orders": [o.id for o in orders if o.state in ("geplaatst", "wacht")],
              "fouten": self.errors[:5]}
        _write_json(self.p["status"], st)

    def do_daily(self, now):
        """Eén keer per serverdag: accounthistoriek en vooruit-test (zelfde code als scripts/vooruittest.py)."""
        if self.daily_day == now.date() or not self.bars:
            return
        self.daily_day = now.date()
        try:
            self.account = self.broker.account()
            _write_json(self.p["deals"], {"sinds": str(self.started), "deals": self.broker.deals(self.started)})
        except Exception as ex:
            self.note("fout", f"accounthistoriek ophalen mislukt: {ex!r}", discord=False, now=now)
        try:
            import numpy as np
            import scripts.vooruittest as VT
            t0 = pd.Timestamp(VT.START)
            df = VT.rows_for(self.bars, lambda t: np.asarray(t >= t0), np.random.default_rng(20261021))
            rep = VT.report(df, VT.START, None, "vooruit-test (MT5-data van de VPS)") if len(df) else \
                {"label": "vooruit-test", "start": VT.START, "leeg": True}
            rep["berekend"] = str(now)
            _write_json(self.p["forward"], rep)
        except Exception as ex:
            self.note("fout", f"vooruit-test berekenen mislukt: {ex!r}", discord=False, now=now)

    # ------------------------------------------------------------ hoofdlus
    def handle_requests(self, now):
        for r in self.snap.take_requests():
            if r == "kill":
                self.mgr.kill(now)
            elif r == "resume":
                self.mgr.resume(now)

    def once(self, now):
        """Eén ronde van 10 s. Apart zodat ze te testen is."""
        self.handle_requests(now)
        ok = self.broker.connected()
        if ok != self.connected:
            self.note("fout" if not ok else "info", "verbinding met MT5 weg" if not ok else "verbinding met MT5 terug", now=now)
            self.connected = ok
        self.disconnected_since = None if ok else (self.disconnected_since or now)
        if not ok:
            self.write_status(now)
            try:
                self.broker.connect()
            except Exception:
                pass
            return
        if self.next_scan is None:
            self.next_scan = next_scan_time(now)
        if now >= self.next_scan:
            if not self.mgr.paused:
                self.do_scan(now)
            if self.control_time is None or now - self.control_time >= pd.Timedelta(hours=1):
                self.do_control(now)
            self.next_scan = next_scan_time(now)
        self.mgr.step(now)
        self.flush_events()
        self.do_daily(now)
        self.daily_summary()
        self.publish(now)
        self.write_status(now)

    def loop(self):
        while True:
            t0 = time.time()
            now = self.now_fn()
            try:
                self.once(now)
            except Exception as ex:                       # nooit stoppen op één fout
                self.note("fout", f"fout in de ronde van {now:%H:%M:%S}: {ex!r}", now=now)
                self.log.write({"time": str(now), "kind": "traceback", "text": traceback.format_exc()})
                if self.mgr is not None:
                    try:
                        self.flush_events()
                    except Exception:
                        pass
            time.sleep(max(1.0, TICK_S - (time.time() - t0)))


def _write_json(path, obj):
    import json
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, path)


def serve(runner: Runner):
    from werkzeug.serving import make_server
    app = make_app(runner.snap, runner.cfg.dash_password, runner.cfg.dash_secret, runner.log,
                   agent={"vragen": runner.p["vragen"], "repo": runner.cfg.agent_repo})
    srv = make_server(runner.cfg.host, runner.cfg.port, app, threaded=True)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def main(cfg_path: str):
    cfg = load_config(cfg_path)
    r = Runner(cfg)
    r.start()
    r.publish(r.now_fn())
    serve(r)
    print(f"KATSU Live draait · dashboard op poort {cfg.port} · stand {cfg.mode}. Stoppen: Ctrl+C.", flush=True)
    try:
        r.loop()
    except KeyboardInterrupt:
        r.note("info", "KATSU Live gestopt (Ctrl+C). Open orders en trades blijven bij MT5 staan met SL en TP.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else r"C:\katsu\config.toml")
