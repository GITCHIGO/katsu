"""
Koppeling met MT5 (spec §1): het officiële Python-pakket `MetaTrader5` (alleen Windows; de terminal moet open en
ingelogd zijn). Alles wat KATSU Live van de broker nodig heeft gaat via de klasse `Broker` hieronder; de tests
gebruiken `katsu/live/fake.py` (nep-MT5) met dezelfde methodes.

Tijden: MT5 geeft candle- en ticktijden in servertijd (IC Markets: New York + 7 u). We werken overal in servertijd,
zonder tijdzone, zoals de backtestdata.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

try:                                                    # Python 3.9+; op Windows: pip install tzdata
    from zoneinfo import ZoneInfo
except ImportError:                                     # pragma: no cover
    ZoneInfo = None


# ------------------------------------------------------------------ tijd

def server_now(utc: datetime | None = None) -> pd.Timestamp:
    """Servertijd IC Markets = New York + 7 u (zomer- en wintertijd volgen New York)."""
    utc = utc or datetime.now(timezone.utc)
    ny = utc.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
    return pd.Timestamp(ny) + pd.Timedelta(hours=7)


def server_to_be(t: pd.Timestamp) -> pd.Timestamp:
    """Servertijd -> Belgische tijd (echte tijdzones, ook in de weken dat de VS en Europa anders omschakelen)."""
    ny = (pd.Timestamp(t) - pd.Timedelta(hours=7)).tz_localize("America/New_York", ambiguous=True,
                                                                 nonexistent="shift_forward")
    return ny.tz_convert("Europe/Brussels").tz_localize(None)


# ------------------------------------------------------------------ gegevens van de broker

@dataclass
class Account:
    login: int
    server: str
    demo: bool
    currency: str
    balance: float
    equity: float


@dataclass
class Tick:
    time: pd.Timestamp
    bid: float
    ask: float


@dataclass
class SymbolInfo:
    name: str
    digits: int
    point: float
    tick_size: float
    volume_min: float
    volume_step: float
    volume_max: float
    contract_size: float
    stops_level: int          # minimale afstand SL/TP in points
    filling_mode: int


@dataclass
class Result:
    ok: bool
    ticket: int | None = None
    price: float | None = None
    retcode: int | None = None
    message: str = ""


@dataclass
class PendingInfo:
    ticket: int
    symbol: str
    magic: int
    comment: str
    price: float
    sl: float
    tp: float
    volume: float


@dataclass
class PositionInfo:
    ticket: int               # = ticket van de order die de positie opende (hedging-account)
    symbol: str
    magic: int
    comment: str
    direction: str
    price_open: float
    sl: float
    tp: float
    volume: float
    time: pd.Timestamp
    profit: float
    swap: float


@dataclass
class ClosedInfo:
    fill_price: float
    fill_time: pd.Timestamp
    exit_price: float
    exit_time: pd.Timestamp
    reason: str               # SL / TP / HAND / KATSU (door KATSU gesloten) / ANDERS
    profit: float
    commission: float
    swap: float


def rates_to_frame(rates) -> pd.DataFrame:
    """MT5-candles -> zelfde kolommen als de backtestdata (open, high, low, close, tickvol, spread)."""
    df = pd.DataFrame(rates)
    if len(df) == 0:
        return pd.DataFrame(columns=["open", "high", "low", "close", "tickvol", "spread"])
    df.index = pd.to_datetime(df["time"], unit="s")
    df.index.name = "time"
    df = df.rename(columns={"tick_volume": "tickvol"})
    return df[["open", "high", "low", "close", "tickvol", "spread"]].astype(
        {"open": float, "high": float, "low": float, "close": float, "tickvol": np.int64, "spread": np.int64})


# ------------------------------------------------------------------ echte MT5

class Broker:
    """Dunne laag rond het pakket MetaTrader5. Alleen aanroepen vanuit één thread (de runner)."""

    REASONS = {3: "HAND", 4: "SL", 5: "TP"}            # DEAL_REASON_CLIENT/MOBILE/WEB=0..2, EXPERT=3, SL=4, TP=5

    def __init__(self, terminal_path: str | None = None, login: int | None = None, password: str | None = None,
                 server: str | None = None, symbols: dict | None = None):
        import MetaTrader5 as mt5                        # pragma: no cover  (alleen op de VPS)
        self.mt5 = mt5
        self.args = {k: v for k, v in (("path", terminal_path), ("login", login), ("password", password),
                                       ("server", server)) if v}
        self.symbols = symbols or {}                     # KATSU-naam -> brokernaam (bv. "XAUUSD": "XAUUSD")

    # ---- verbinding
    def sym(self, market: str) -> str:
        return self.symbols.get(market, market)

    def connect(self) -> Account:
        if not self.mt5.initialize(**self.args):
            raise ConnectionError(f"MT5 start niet: {self.mt5.last_error()}")
        for m in self.symbols or ():
            self.mt5.symbol_select(self.sym(m), True)
        return self.account()

    def connected(self) -> bool:
        ti = self.mt5.terminal_info()
        return bool(ti and ti.connected)

    def account(self) -> Account:
        a = self.mt5.account_info()
        if a is None:
            raise ConnectionError(f"geen accountinfo: {self.mt5.last_error()}")
        return Account(a.login, a.server, a.trade_mode == self.mt5.ACCOUNT_TRADE_MODE_DEMO, a.currency, a.balance,
                       a.equity)

    def shutdown(self):
        self.mt5.shutdown()

    # ---- data
    def rates(self, market: str, count: int) -> pd.DataFrame:
        r = self.mt5.copy_rates_from_pos(self.sym(market), self.mt5.TIMEFRAME_M15, 0, count)
        if r is None:
            raise ConnectionError(f"geen candles voor {market}: {self.mt5.last_error()}")
        return rates_to_frame(r)

    def tick(self, market: str) -> Tick | None:
        t = self.mt5.symbol_info_tick(self.sym(market))
        if t is None or t.bid <= 0:
            return None
        return Tick(pd.Timestamp(t.time, unit="s"), float(t.bid), float(t.ask))

    def symbol(self, market: str) -> SymbolInfo:
        s = self.mt5.symbol_info(self.sym(market))
        if s is None:
            raise ValueError(f"symbool {self.sym(market)} bestaat niet bij deze broker")
        return SymbolInfo(market, s.digits, s.point, s.trade_tick_size, s.volume_min, s.volume_step, s.volume_max,
                          s.trade_contract_size, s.trade_stops_level, s.filling_mode)

    def risk_money(self, market: str, direction: str, volume: float, price: float, sl: float) -> float | None:
        t = self.mt5.ORDER_TYPE_BUY if direction == "LONG" else self.mt5.ORDER_TYPE_SELL
        v = self.mt5.order_calc_profit(t, self.sym(market), volume, price, sl)
        return None if v is None else abs(float(v))

    # ---- orders
    def _send(self, req: dict) -> Result:
        r = self.mt5.order_send(req)
        if r is None:
            return Result(False, message=f"order_send gaf niets terug: {self.mt5.last_error()}")
        ok = r.retcode in (self.mt5.TRADE_RETCODE_DONE, self.mt5.TRADE_RETCODE_PLACED)
        return Result(ok, r.order or r.deal or None, r.price or None, r.retcode, r.comment)

    def _filling(self, market: str, pending: bool) -> int:
        if pending:
            return self.mt5.ORDER_FILLING_RETURN
        fm = self.symbol(market).filling_mode
        if fm & 1:
            return self.mt5.ORDER_FILLING_FOK
        if fm & 2:
            return self.mt5.ORDER_FILLING_IOC
        return self.mt5.ORDER_FILLING_RETURN

    def place_pending(self, market, direction, price, sl, tp, volume, magic, comment) -> Result:
        t = self.mt5.ORDER_TYPE_BUY_LIMIT if direction == "LONG" else self.mt5.ORDER_TYPE_SELL_LIMIT
        return self._send({"action": self.mt5.TRADE_ACTION_PENDING, "symbol": self.sym(market), "type": t,
                           "price": price, "sl": sl, "tp": tp, "volume": volume, "magic": magic,
                           "comment": comment[:31], "type_time": self.mt5.ORDER_TIME_GTC,
                           "type_filling": self._filling(market, True)})

    def place_market(self, market, direction, sl, tp, volume, magic, comment) -> Result:
        tk = self.tick(market)
        if tk is None:
            return Result(False, message="geen koers")
        long = direction == "LONG"
        r = self._send({"action": self.mt5.TRADE_ACTION_DEAL, "symbol": self.sym(market),
                        "type": self.mt5.ORDER_TYPE_BUY if long else self.mt5.ORDER_TYPE_SELL,
                        "price": tk.ask if long else tk.bid, "sl": sl, "tp": tp, "volume": volume,
                        "deviation": 20, "magic": magic, "comment": comment[:31],
                        "type_time": self.mt5.ORDER_TIME_GTC, "type_filling": self._filling(market, False)})
        return r

    def cancel_order(self, ticket: int) -> Result:
        return self._send({"action": self.mt5.TRADE_ACTION_REMOVE, "order": int(ticket)})

    def set_sltp(self, market: str, position: int, sl: float, tp: float) -> Result:
        return self._send({"action": self.mt5.TRADE_ACTION_SLTP, "symbol": self.sym(market), "position": int(position),
                           "sl": sl, "tp": tp})

    def close_position(self, market: str, position: int, comment: str = "KATSU sluit") -> Result:
        ps = self.mt5.positions_get(ticket=int(position))
        if not ps:
            return Result(False, message="positie niet gevonden")
        p = ps[0]
        long = p.type == self.mt5.POSITION_TYPE_BUY
        tk = self.tick(market)
        return self._send({"action": self.mt5.TRADE_ACTION_DEAL, "symbol": p.symbol, "position": p.ticket,
                           "type": self.mt5.ORDER_TYPE_SELL if long else self.mt5.ORDER_TYPE_BUY,
                           "price": tk.bid if long else tk.ask, "volume": p.volume, "deviation": 20,
                           "magic": p.magic, "comment": comment[:31], "type_time": self.mt5.ORDER_TIME_GTC,
                           "type_filling": self._filling(market, False)})

    # ---- toestand bij de broker
    def pending_orders(self, magics) -> list[PendingInfo]:
        out = []
        for o in self.mt5.orders_get() or ():
            if o.magic in magics:
                out.append(PendingInfo(o.ticket, o.symbol, o.magic, o.comment, o.price_open, o.sl, o.tp,
                                       o.volume_current))
        return out

    def positions(self, magics) -> list[PositionInfo]:
        out = []
        for p in self.mt5.positions_get() or ():
            if p.magic in magics:
                out.append(PositionInfo(p.identifier, p.symbol, p.magic, p.comment,
                                        "LONG" if p.type == self.mt5.POSITION_TYPE_BUY else "SHORT", p.price_open,
                                        p.sl, p.tp, p.volume, pd.Timestamp(p.time, unit="s"), p.profit, p.swap))
        return out

    def closed_position(self, position: int) -> ClosedInfo | None:
        """Gegevens van een gesloten positie uit de historiek (None als ze nog open is of niet bestaat)."""
        deals = self.mt5.history_deals_get(position=int(position)) or ()
        ins = [d for d in deals if d.entry == self.mt5.DEAL_ENTRY_IN]
        outs = [d for d in deals if d.entry in (self.mt5.DEAL_ENTRY_OUT, self.mt5.DEAL_ENTRY_OUT_BY)]
        if not ins or not outs:
            return None
        din, dout = ins[0], outs[-1]
        reason = self.REASONS.get(dout.reason, "ANDERS")
        if dout.reason == 3 and str(dout.comment).startswith("KATSU"):
            reason = "KATSU"
        elif dout.reason in (0, 1, 2):
            reason = "HAND"
        return ClosedInfo(din.price, pd.Timestamp(din.time, unit="s"), dout.price, pd.Timestamp(dout.time, unit="s"),
                          reason, float(sum(d.profit for d in deals)), float(sum(d.commission for d in deals)),
                          float(sum(d.swap for d in deals)))

    def deals(self, since: pd.Timestamp) -> list[dict]:
        """Alle deals op het account sinds `since` (servertijd), ook met de hand of van andere programma's."""
        t0 = (pd.Timestamp(since) - pd.Timedelta(days=2)).to_pydatetime()
        t1 = (server_now() + pd.Timedelta(days=2)).to_pydatetime()
        out = []
        for d in self.mt5.history_deals_get(t0, t1) or ():
            t = pd.Timestamp(d.time, unit="s")
            if t < pd.Timestamp(since):
                continue
            out.append({"ticket": d.ticket, "order": d.order, "positie": d.position_id, "tijd": str(t), "symbool": d.symbol,
                        "type": d.type, "entry": d.entry, "volume": d.volume, "prijs": d.price, "winst": d.profit,
                        "commissie": d.commission, "swap": d.swap, "magic": d.magic, "commentaar": d.comment,
                        "reden": d.reason})
        return out

    def order_was_filled(self, ticket: int) -> int | None:
        """Positie-ID als een (verdwenen) limietorder gevuld werd, anders None."""
        deals = self.mt5.history_deals_get(position=int(ticket)) or ()
        return int(ticket) if any(d.entry == self.mt5.DEAL_ENTRY_IN for d in deals) else None
