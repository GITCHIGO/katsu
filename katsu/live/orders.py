"""
Orderbeheer van KATSU Live als toestandsmachine (spec §3 en §7.3).

    signaal ─┬─> geplaatst (limiet bij de broker) ──> gevuld ──> gesloten
             │        │  └─> geannuleerd (verlopen / TP eerst geraakt / noodknop / extern verwijderd)
             │        └─> wacht (geparkeerd: er loopt al een trade van deze setup op dit pair)
             ├─> gevuld (marktorder)
             ├─> wacht ──> geplaatst (zodra de lopende trade dicht is)
             │        └─> geblokkeerd (de koers raakte de limiet terwijl de andere trade liep)
             ├─> geweigerd (ongeldig plan of broker weigert)
             └─> log (stand 'loggen': niets naar de broker)

Waarom 'wacht': in de backtest (katsu/dashboard_calc.one_at_a_time) mogen meerdere limietorders van dezelfde setup
op hetzelfde pair tegelijk openstaan, maar er telt maar één trade tegelijk: een order die zou vullen terwijl een
andere trade loopt, valt weg. Live halen we zo'n order daarom van de broker zodra een trade loopt, en zetten we hem
terug als die trade dicht is — tenzij de koers de limiet ondertussen raakte (dan: geblokkeerd, zoals de backtest).
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from katsu.execution import M1
from katsu.live.levels import sign, sl_price, tp_price, zone_tp_plan
from katsu.live.scan import SETUPS, SHORT, STEP, Signal

ACTIVE = ("wacht", "geplaatst", "gevuld")
PIP = {"EURUSD": 0.0001, "GBPUSD": 0.0001, "XAUUSD": 0.1}
EOD_CLOSE = pd.Timedelta(hours=23, minutes=55)      # AMD: sluiten om 23:55 server (backtest: close van 23:45-candle)
MAX_HOLD = pd.Timedelta(days=14)


@dataclass
class Event:
    time: str
    kind: str          # signaal, geplaatst, gevuld, gesloten, geannuleerd, wacht, geblokkeerd, geweigerd, gemist, fout, info
    text: str
    order: str | None = None
    discord: bool = True


@dataclass
class LiveOrder:
    id: str
    key: str
    setup: str
    market: str
    direction: str
    kind: str
    t_sig: str
    anchor: float
    atr: float
    limit: float | None
    tp_plan: float | None
    cancel: float | None
    max_rr: float | None
    valid_until: str | None
    valid_bars: int | None
    close_eod: bool
    tp_mode: str
    leg_high: float | None
    lot: float
    magic: int
    features: dict = field(default_factory=dict)
    state: str = "nieuw"
    reason: str = ""
    ticket: int | None = None
    position: int | None = None
    sl: float | None = None
    tp: float | None = None
    fill_px: float | None = None
    fill_time: str | None = None
    exit_px: float | None = None
    exit_time: str | None = None
    exit_reason: str | None = None
    risk_px: float | None = None
    risk_money: float | None = None
    profit: float | None = None
    commission: float | None = None
    swap: float | None = None
    net: float | None = None
    r_net: float | None = None
    pips: float | None = None
    parked: bool = False                 # van de broker gehaald omdat een andere trade van de groep liep
    close_why: str | None = None         # waarom KATSU zelf sloot (EINDE_DAG, MAX_DUUR, NOODKNOP, DUBBEL, ...)
    checked_bar: str | None = None       # laatste candle die al gecontroleerd werd (annuleren / geblokkeerd)
    history: list = field(default_factory=list)

    @property
    def group(self):
        return (self.setup, self.market)

    @property
    def s(self) -> float:
        return sign(self.direction)

    def label(self) -> str:
        return f"{SETUPS[self.setup][0]} · {self.market} · {self.direction}"


def _ts(x):
    return None if x is None else pd.Timestamp(x)


def _r(x, digits):
    return None if x is None else round(float(x), digits)


class Manager:
    def __init__(self, broker, instruments: dict, lots: dict, store: str | None = None, mode: str = "loggen"):
        if mode not in ("loggen", "orders"):
            raise ValueError("mode moet 'loggen' of 'orders' zijn")
        self.broker = broker
        self.ins = instruments
        self.lots = lots
        self.store = store
        self.mode = mode
        self.orders: dict[str, LiveOrder] = {}
        self.paused = False
        self.last_scan: str | None = None
        self.events: list[Event] = []
        self.magics = {m for _, m in SETUPS.values()}
        self.warned_unknown: set = set()
        if store and os.path.exists(store):
            self.load()

    # ------------------------------------------------------------ opslag (veilige herstart)
    def save(self):
        if not self.store:
            return
        tmp = self.store + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"orders": [asdict(o) for o in self.orders.values()], "paused": self.paused,
                       "last_scan": self.last_scan}, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, self.store)

    def load(self):
        with open(self.store, encoding="utf-8") as fh:
            d = json.load(fh)
        self.orders = {o["id"]: LiveOrder(**o) for o in d.get("orders", [])}
        self.paused = bool(d.get("paused", False))
        self.last_scan = d.get("last_scan")

    # ------------------------------------------------------------ hulp
    def emit(self, now, kind, text, o: LiveOrder | None = None, discord=True):
        ev = Event(str(pd.Timestamp(now)), kind, text, o.id if o else None, discord)
        self.events.append(ev)
        if o is not None:
            o.history.append([ev.time, kind, text])

    def set_state(self, o: LiveOrder, state: str, now, kind: str, text: str, discord=True):
        o.state = state
        o.reason = text
        self.emit(now, kind, f"{o.label()}: {text}", o, discord)

    def active(self, state=None):
        return [o for o in self.orders.values() if o.state in ((state,) if state else ACTIVE)]

    def busy(self, group, exclude: str | None = None) -> bool:
        return any(o.group == group and o.state == "gevuld" and o.id != exclude for o in self.orders.values())

    def _volume(self, market) -> float:
        si = self.broker.symbol(market)
        lot = self.lots[market]
        v = math.floor(lot / si.volume_step + 1e-9) * si.volume_step
        return round(max(si.volume_min, min(v, si.volume_max)), 8)

    def _px(self, market, x):
        return None if x is None else round(float(x), self.broker.symbol(market).digits)

    def _new_id(self, sig: Signal) -> str:
        base = f"{SETUPS[sig.setup][0]}-{SHORT.get(sig.market, sig.market)}-{sig.t_sig:%y%m%d%H%M}"
        n = 1
        while f"{base}-{n}" in self.orders:
            n += 1
        return f"{base}-{n}"

    # ------------------------------------------------------------ nieuwe signalen
    def add_signal(self, sig: Signal, now) -> LiveOrder | None:
        if any(o.key == sig.key for o in self.orders.values()):
            return None                                   # al gezien (zelfde signaal, volgende scan)
        _, magic = SETUPS[sig.setup]
        o = LiveOrder(self._new_id(sig), sig.key, sig.setup, sig.market, sig.direction, sig.kind, str(sig.t_sig),
                      sig.anchor, sig.atr, sig.limit, sig.tp_plan, sig.cancel, sig.max_rr,
                      None if sig.valid_until is None else str(sig.valid_until), sig.valid_bars, sig.close_eod,
                      sig.tp_mode, sig.leg_high, self.lots[sig.market], magic, dict(sig.features))
        self.orders[o.id] = o
        ins = self.ins[o.market]
        entry = o.limit if o.kind != "market" else None
        o.sl = sl_price(o.direction, o.anchor, o.atr, ins)
        what = (f"limiet {self._px(o.market, entry)}" if entry is not None else "marktorder") + \
               f" · SL {self._px(o.market, o.sl)}"
        if self.mode == "loggen":
            self.set_state(o, "log", now, "signaal", f"nieuw signaal (stand loggen: geen order) · {what}")
        elif self.paused:
            self.set_state(o, "geannuleerd", now, "geannuleerd", "scanner gepauzeerd (noodknop) · " + what)
        elif self.busy(o.group):
            if o.kind == "market":
                self.set_state(o, "geblokkeerd", now, "geblokkeerd",
                               "marktorder overgeslagen: er loopt al een trade van deze setup op dit pair")
            else:
                o.parked = True
                self.set_state(o, "wacht", now, "wacht",
                               f"signaal geparkeerd: er loopt al een trade van deze setup op dit pair · {what}")
        else:
            self.place(o, now)
        self.save()
        return o

    def missed(self, sig: Signal, now):
        if any(o.key == sig.key for o in self.orders.values()):
            return
        self.emit(now, "gemist", f"{SETUPS[sig.setup][0]} · {sig.market} · {sig.direction}: signaal van "
                                  f"{sig.t_sig:%d-%m %H:%M} gemist (backtest had de order al gevuld of geannuleerd)")

    # ------------------------------------------------------------ naar de broker
    def place(self, o: LiveOrder, now):
        ins = self.ins[o.market]
        tick = self.broker.tick(o.market)
        if tick is None:
            self.set_state(o, "wacht", now, "fout", "geen koers; opnieuw bij de volgende controle")
            return
        vol = self._volume(o.market)
        long = o.direction == "LONG"
        sl = o.sl
        if o.kind == "market":
            fill_est = tick.ask if long else tick.bid
            marketable = True
        else:
            fill_est = o.limit
            marketable = (tick.ask <= o.limit) if long else (tick.bid >= o.limit)
            if marketable:                                 # backtest: vult op de open als die al voorbij de limiet ligt
                fill_est = tick.ask if long else tick.bid
        tp_plan = o.tp_plan if o.tp_mode == "vast" else fill_est + o.s * 1e6     # zone: voorlopig 2R (plafond)
        tp = tp_price(o.direction, fill_est, sl, ins, tp_plan, o.max_rr if o.tp_mode == "vast" else 2.0)
        if tp is None:
            self.set_state(o, "geweigerd", now, "geweigerd",
                           "ongeldig plan: TP ligt niet voorbij de entry of SL aan de verkeerde kant (backtest: geen trade)")
            return
        o.tp = tp
        cm = o.id
        if marketable:
            r = self.broker.place_market(o.market, o.direction, self._px(o.market, sl), self._px(o.market, tp), vol,
                                         o.magic, cm)
        else:
            r = self.broker.place_pending(o.market, o.direction, self._px(o.market, o.limit), self._px(o.market, sl),
                                          self._px(o.market, tp), vol, o.magic, cm)
        if not r.ok:
            self.set_state(o, "geweigerd", now, "geweigerd", f"broker weigert ({r.retcode}): {r.message}")
            return
        o.ticket = r.ticket
        if marketable:
            o.position = r.ticket
            self.set_state(o, "geplaatst", now, "geplaatst",
                           f"marktorder verstuurd · {vol} lot · SL {self._px(o.market, sl)} · TP {self._px(o.market, tp)}",
                           discord=False)
            for p in self.broker.positions(self.magics):
                if p.ticket == r.ticket:
                    self.on_fill(o, p, now)
        else:
            until = o.valid_until or f"{o.valid_bars} M15-candles"
            self.set_state(o, "geplaatst", now, "geplaatst",
                           f"limiet {self._px(o.market, o.limit)} · SL {self._px(o.market, sl)} · "
                           f"TP {self._px(o.market, tp)} · {vol} lot · geldig tot {until}")

    def cancel(self, o: LiveOrder, now, why: str, state="geannuleerd", kind="geannuleerd"):
        if o.state == "geplaatst" and o.ticket is not None:
            r = self.broker.cancel_order(o.ticket)
            if not r.ok and self.broker.order_was_filled(o.ticket):
                return False                               # net gevuld: de volgende stap pikt de vulling op
        self.set_state(o, state, now, kind, why)
        return True

    # ------------------------------------------------------------ vulling en sluiting
    def _zone_tp(self, o: LiveOrder, fill_time) -> float:
        bars = self.broker.rates(o.market, 3000)
        fill_bar = pd.Timestamp(fill_time).floor("15min")
        seg = bars[(bars.index >= _ts(o.t_sig)) & (bars.index < fill_bar)]
        return zone_tp_plan(o.direction, o.leg_high, seg["high"].to_numpy(), seg["low"].to_numpy())

    def on_fill(self, o: LiveOrder, p, now, already_closed=False):
        ins = self.ins[o.market]
        o.state = "gevuld"
        o.position = p.ticket
        o.fill_px = float(p.price_open)
        o.fill_time = str(p.time)
        o.sl = float(p.sl) if p.sl else o.sl
        tp_plan = self._zone_tp(o, p.time) if o.tp_mode == "zone_bij_vulling" else o.tp_plan
        max_rr = 2.0 if o.tp_mode == "zone_bij_vulling" else o.max_rr
        tp = tp_price(o.direction, o.fill_px, o.sl, ins, tp_plan, max_rr)
        o.risk_px = o.s * (o.fill_px - o.sl)
        o.risk_money = self.broker.risk_money(o.market, o.direction, p.volume, o.fill_px, o.sl)
        self.emit(now, "gevuld", f"{o.label()}: gevuld op {self._px(o.market, o.fill_px)} · SL "
                                 f"{self._px(o.market, o.sl)} · TP {self._px(o.market, tp)}", o)
        if already_closed:
            o.tp = tp if tp is not None else o.tp
            return
        if tp is None:
            self.close(o, now, "TP_ONGELDIG")
            return
        if o.tp is None or abs(tp - o.tp) > ins.tick / 2 or not p.tp:
            r = self.broker.set_sltp(o.market, p.ticket, self._px(o.market, o.sl), self._px(o.market, tp))
            if not r.ok:
                self.emit(now, "fout", f"{o.label()}: TP aanpassen mislukt ({r.message})", o)
        o.tp = tp
        # andere orders van dezelfde setup op dit pair van de broker halen (één trade tegelijk)
        for q in self.active("geplaatst"):
            if q.group == o.group and q.id != o.id:
                if self.cancel(q, now, "geparkeerd: er loopt nu een trade van deze setup op dit pair",
                               state="wacht", kind="wacht"):
                    q.ticket = None
                    q.parked = True

    def close(self, o: LiveOrder, now, why: str):
        if o.close_why is not None:
            return                                         # al gesloten door KATSU, wacht op de historiek
        r = self.broker.close_position(o.market, o.position, comment="KATSU " + why[:20])
        if not r.ok:
            self.emit(now, "fout", f"{o.label()}: sluiten mislukt ({r.message})", o)
            return
        o.close_why = why

    def on_close(self, o: LiveOrder, c, now):
        o.fill_px = o.fill_px or c.fill_price
        o.fill_time = o.fill_time or str(c.fill_time)
        o.exit_px, o.exit_time = c.exit_price, str(c.exit_time)
        o.exit_reason = (o.close_why or "KATSU") if c.reason == "KATSU" else c.reason
        o.profit, o.commission, o.swap = c.profit, c.commission, c.swap
        o.net = c.profit + c.commission + c.swap
        if o.risk_px is None and o.sl is not None:
            o.risk_px = o.s * (o.fill_px - o.sl)
        if o.risk_money is None and o.sl is not None:
            o.risk_money = self.broker.risk_money(o.market, o.direction, o.lot, o.fill_px, o.sl)
        o.r_net = (o.net / o.risk_money) if o.risk_money else None
        o.pips = o.s * (o.exit_px - o.fill_px) / PIP[o.market]
        r_txt = "—" if o.r_net is None else f"{o.r_net:+.2f}R"
        self.set_state(o, "gesloten", now, "gesloten",
                       f"gesloten ({o.exit_reason}) op {self._px(o.market, o.exit_px)} · "
                       f"{r_txt} · {o.pips:+.1f} pips · {o.net:+.2f}")

    @staticmethod
    def deadline(o: LiveOrder) -> pd.Timestamp | None:
        if o.fill_time is None:
            return None
        f = _ts(o.fill_time)
        if o.close_eod:
            return f.normalize() + EOD_CLOSE
        d = f + MAX_HOLD
        if d.dayofweek >= 5:                           # valt in het weekend: vrijdag 23:50 (laatste candle)
            d = (d - pd.Timedelta(days=d.dayofweek - 4)).normalize() + pd.Timedelta(hours=23, minutes=50)
        return d

    # ------------------------------------------------------------ elke 10 seconden
    def step(self, now):
        now = pd.Timestamp(now)
        pend = {p.ticket: p for p in self.broker.pending_orders(self.magics)}
        pos = {p.ticket: p for p in self.broker.positions(self.magics)}
        known = {o.ticket for o in self.orders.values()} | {o.position for o in self.orders.values()}
        for t in (set(pend) | set(pos)) - known - self.warned_unknown:
            self.warned_unknown.add(t)
            self.emit(now, "fout", f"onbekende KATSU-order/positie #{t} bij de broker (niet aangeraakt)")

        for o in self.active("geplaatst"):
            if o.state != "geplaatst":                     # intussen geparkeerd door een vulling in dezelfde groep
                continue
            if o.ticket in pos:
                self.on_fill(o, pos[o.ticket], now)
            elif o.ticket not in pend:
                pid = self.broker.order_was_filled(o.ticket)
                c = self.broker.closed_position(pid) if pid else None
                if pid and c is not None:
                    o.position = pid
                    self.on_fill(o, _closed_as_pos(o, c), now, already_closed=True)
                    self.on_close(o, c, now)
                elif not pid:
                    self.set_state(o, "geannuleerd", now, "geannuleerd", "order verdwenen bij de broker (extern verwijderd?)")
            else:
                self._time_and_tick_checks(o, now)

        for o in self.active("gevuld"):
            if o.position not in pos:
                c = self.broker.closed_position(o.position)
                if c is not None:
                    self.on_close(o, c, now)
                continue
            p = pos[o.position]
            if not p.sl or not p.tp:                       # SL/TP moeten altijd bij de broker staan
                r = self.broker.set_sltp(o.market, p.ticket, self._px(o.market, o.sl), self._px(o.market, o.tp))
                self.emit(now, "fout" if not r.ok else "info", f"{o.label()}: SL/TP ontbrak bij de broker, "
                                                               f"{'opnieuw gezet' if r.ok else 'zetten mislukt'}", o)
            dl = self.deadline(o)
            if dl is not None and now >= dl:
                self.close(o, now, "EINDE_DAG" if o.close_eod else "MAX_DUUR")

        # dubbele vulling in dezelfde groep (twee limieten in dezelfde seconden): de vroegste blijft
        groups = {}
        for o in self.active("gevuld"):
            groups.setdefault(o.group, []).append(o)
        for g in groups.values():
            for o in sorted(g, key=lambda x: (x.fill_time, x.t_sig))[1:]:
                if o.close_why is None:
                    self.emit(now, "geblokkeerd", f"{o.label()}: gelijktijdig gevuld met een andere order van deze "
                                                  "setup; meteen gesloten (backtest: één trade tegelijk)", o)
                self.close(o, now, "DUBBEL")

        for o in self.active("wacht"):
            if o.state != "wacht":
                continue
            if self._time_and_tick_checks(o, now) or self.paused:
                continue
            if not self.busy(o.group):
                tick = self.broker.tick(o.market)
                long = o.direction == "LONG"
                if o.parked and tick is not None and o.limit is not None and \
                        ((long and tick.ask <= o.limit) or (not long and tick.bid >= o.limit)):
                    # koers staat al voorbij de limiet: hij werd geraakt terwijl de andere trade liep
                    self.set_state(o, "geblokkeerd", now, "geblokkeerd",
                                   "limiet geraakt terwijl een andere trade van deze setup liep (backtest: overgeslagen)")
                    continue
                o.parked = False
                self.emit(now, "info", f"{o.label()}: lopende trade is dicht, order terug naar de broker", o, False)
                self.place(o, now)
        self.save()

    def _time_and_tick_checks(self, o: LiveOrder, now) -> bool:
        """Verlopen / TP eerst geraakt / (geparkeerd) limiet geraakt. True als de order daardoor eindigde."""
        if o.valid_until is not None and now >= _ts(o.valid_until):
            return self.cancel(o, now, "verlopen (geen vulling binnen de geldigheid)")
        tick = self.broker.tick(o.market)
        if tick is None:
            return False
        long = o.direction == "LONG"
        if o.cancel is not None and ((long and tick.bid >= o.cancel) or (not long and tick.ask <= o.cancel)):
            return self.cancel(o, now, "TP-niveau eerst geraakt vóór de vulling")
        if o.state == "wacht" and self.busy(o.group) and o.limit is not None and \
                ((long and tick.ask <= o.limit) or (not long and tick.bid >= o.limit)):
            self.set_state(o, "geblokkeerd", now, "geblokkeerd",
                           "koers raakte de limiet terwijl een andere trade van deze setup liep (backtest: overgeslagen)")
            return True
        return False

    # ------------------------------------------------------------ na elke gesloten candle
    def on_bars(self, bars_by_market: dict, now):
        """Controles op gesloten M15-candles (zelfde manier als de backtest): geldigheid in candles (FVG),
        annuleerniveau geraakt, geparkeerde limiet geraakt. Vangt ook pieken tussen twee ticks op."""
        now = pd.Timestamp(now)
        for o in [x for x in self.orders.values() if x.state in ("geplaatst", "wacht")]:
            bars = bars_by_market.get(o.market)
            if bars is None or len(bars) == 0:
                continue
            t_sig = _ts(o.t_sig)
            after = bars[bars.index >= t_sig]
            start = _ts(o.checked_bar)
            new = after if start is None else after[after.index > start]
            if len(new):
                ins = self.ins[o.market]
                sp = M1(new, ins).sp                          # spread zoals de backtest (minimum + rollover)
                long = o.direction == "LONG"
                for i, (t, row) in enumerate(new.iterrows()):
                    if o.cancel is not None and ((long and row.high >= o.cancel) or
                                                 (not long and row.low + sp[i] <= o.cancel)):
                        if self.cancel(o, now, f"TP-niveau eerst geraakt (candle {t:%d-%m %H:%M})"):
                            break
                    if o.state == "wacht" and self.busy(o.group) and o.limit is not None and \
                            ((long and row.low + sp[i] <= o.limit) or (not long and row.high >= o.limit)):
                        self.set_state(o, "geblokkeerd", now, "geblokkeerd",
                                       f"limiet geraakt (candle {t:%d-%m %H:%M}) terwijl een andere trade van deze "
                                       "setup liep (backtest: overgeslagen)")
                        break
                o.checked_bar = str(new.index[-1])
            if o.state in ("geplaatst", "wacht") and o.valid_bars is not None and len(after) >= o.valid_bars:
                self.cancel(o, now, f"verlopen ({o.valid_bars} M15-candles zonder vulling)")
        self.save()

    # ------------------------------------------------------------ noodknop
    def kill(self, now, who="dashboard"):
        self.paused = True
        self.emit(now, "fout", f"NOODKNOP ({who}): alles annuleren en sluiten, scanner gepauzeerd")
        for o in self.active("geplaatst") + self.active("wacht"):
            self.cancel(o, now, "noodknop")
        for o in self.active("gevuld"):
            self.close(o, now, "NOODKNOP")
        self.save()

    def resume(self, now):
        self.paused = False
        self.emit(now, "info", "scanner hervat")
        self.save()

    def drain(self) -> list[Event]:
        ev, self.events = self.events, []
        return ev


def _closed_as_pos(o: LiveOrder, c):
    """Een positie die al dicht was vóór we de vulling zagen: zelfde gegevens als bij een open positie."""
    from katsu.live.broker import PositionInfo
    return PositionInfo(o.ticket, o.market, o.magic, o.id, o.direction, c.fill_price, o.sl or 0.0, o.tp or 0.0,
                        o.lot, c.fill_time, 0.0, 0.0)
