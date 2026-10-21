"""
Nep-MT5 voor de tests (spec §7.1): zelfde methodes als katsu/live/broker.Broker, zonder terminal.
Prijzen zet de test zelf met set_price(); daarbij vult de nep-broker limietorders en raakt hij SL/TP:
- buy limit vult als ASK <= limiet (op de limiet, of beter als de koers erover sprong);
- sell limit vult als BID >= limiet;
- long: SL als BID <= SL, TP als BID >= TP; short: SL als ASK >= SL, TP als ASK <= TP.
Winst in de rekeningmunt = prijsverschil × contract × lots (rekeningmunt = USD in de nep-broker).
"""
from __future__ import annotations

import itertools

import pandas as pd

from katsu.live.broker import (Account, ClosedInfo, PendingInfo, PositionInfo, Result, SymbolInfo, Tick,
                               rates_to_frame)

CONTRACT = {"EURUSD": 100_000, "GBPUSD": 100_000, "XAUUSD": 100}
DIGITS = {"EURUSD": 5, "GBPUSD": 5, "XAUUSD": 2}


class FakeBroker:
    def __init__(self, demo: bool = True, commission_per_lot: float = 7.0):
        self.demo = demo
        self.commission_per_lot = commission_per_lot     # round turn, helft bij openen, helft bij sluiten
        self.bars: dict[str, pd.DataFrame] = {}
        self.ticks: dict[str, Tick] = {}
        self.pending: dict[int, dict] = {}
        self.open: dict[int, dict] = {}
        self.closed: dict[int, dict] = {}
        self.cancelled: set[int] = set()
        self.ids = itertools.count(1001)
        self.calls: list[tuple] = []                     # logboek van wat KATSU vroeg (voor de tests)
        self.reject_next: str | None = None              # volgende order weigeren met deze tekst
        self.is_connected = True

    # ---- verbinding
    def connect(self) -> Account:
        return self.account()

    def connected(self) -> bool:
        return self.is_connected

    def account(self) -> Account:
        return Account(123, "ICMarketsSC-Demo", self.demo, "USD", 5000.0, 5000.0)

    def shutdown(self):
        pass

    # ---- data
    def rates(self, market: str, count: int) -> pd.DataFrame:
        return self.bars[market].tail(count)

    def tick(self, market: str) -> Tick | None:
        return self.ticks.get(market)

    def symbol(self, market: str) -> SymbolInfo:
        d = DIGITS[market]
        return SymbolInfo(market, d, 10 ** -d, 10 ** -d, 0.01, 0.01, 100.0, CONTRACT[market], 0, 3)

    def risk_money(self, market, direction, volume, price, sl):
        return abs(price - sl) * CONTRACT[market] * volume

    # ---- prijzen (test)
    def set_price(self, market: str, bid: float, ask: float | None = None, time=None, path: bool = False):
        """path=True: de koers bewoog geleidelijk naar dit punt (binnen een candle) → een limiet vult op de limiet
        zelf, niet op dit verdere punt. path=False: sprong (gap, bv. de open van een candle) → vulling op deze koers."""
        ask = bid if ask is None else ask
        t = pd.Timestamp(time) if time is not None else pd.Timestamp("2026-10-21 10:00")
        self.ticks[market] = Tick(t, bid, ask)
        for tk, o in list(self.pending.items()):
            if o["market"] != market:
                continue
            long = o["direction"] == "LONG"
            if long and ask <= o["price"]:
                self._open(tk, o, o["price"] if path else min(o["price"], ask), t)
            elif not long and bid >= o["price"]:
                self._open(tk, o, o["price"] if path else max(o["price"], bid), t)
        for tk, p in list(self.open.items()):
            if p["market"] != market:
                continue
            long = p["direction"] == "LONG"
            px = bid if long else ask
            if p["sl"] and ((long and px <= p["sl"]) or (not long and px >= p["sl"])):
                self._close(tk, p["sl"], t, "SL")
            elif p["tp"] and ((long and px >= p["tp"]) or (not long and px <= p["tp"])):
                self._close(tk, p["tp"], t, "TP")

    def _open(self, ticket, o, price, t):
        self.pending.pop(ticket, None)
        self.open[ticket] = {**o, "price_open": price, "time": t, "commission": -self.commission_per_lot / 2 * o["volume"]}

    def _close(self, ticket, price, t, reason):
        p = self.open.pop(ticket)
        s = 1 if p["direction"] == "LONG" else -1
        profit = s * (price - p["price_open"]) * CONTRACT[p["market"]] * p["volume"]
        self.closed[ticket] = {**p, "exit": price, "exit_time": t, "reason": reason, "profit": profit,
                               "commission": p["commission"] - self.commission_per_lot / 2 * p["volume"]}

    # ---- orders
    def _rej(self):
        if self.reject_next:
            msg, self.reject_next = self.reject_next, None
            return Result(False, retcode=10016, message=msg)
        return None

    def place_pending(self, market, direction, price, sl, tp, volume, magic, comment) -> Result:
        self.calls.append(("pending", market, direction, price, sl, tp, volume, magic))
        if (r := self._rej()) is not None:
            return r
        tk = next(self.ids)
        self.pending[tk] = {"market": market, "direction": direction, "price": price, "sl": sl, "tp": tp,
                            "volume": volume, "magic": magic, "comment": comment[:31]}
        tick = self.ticks.get(market)
        if tick is not None:                       # limiet die al marktbaar is, vult meteen
            self.set_price(market, tick.bid, tick.ask, tick.time)
        return Result(True, tk, price, 10008)

    def place_market(self, market, direction, sl, tp, volume, magic, comment) -> Result:
        self.calls.append(("market", market, direction, sl, tp, volume, magic))
        if (r := self._rej()) is not None:
            return r
        tick = self.ticks[market]
        tk = next(self.ids)
        o = {"market": market, "direction": direction, "price": None, "sl": sl, "tp": tp, "volume": volume,
             "magic": magic, "comment": comment[:31]}
        price = tick.ask if direction == "LONG" else tick.bid
        self._open(tk, o, price, tick.time)
        return Result(True, tk, price, 10009)

    def cancel_order(self, ticket) -> Result:
        self.calls.append(("cancel", ticket))
        if ticket in self.pending:
            self.pending.pop(ticket)
            self.cancelled.add(ticket)
            return Result(True, ticket)
        return Result(False, ticket, message="order bestaat niet")

    def set_sltp(self, market, position, sl, tp) -> Result:
        self.calls.append(("sltp", position, sl, tp))
        if position not in self.open:
            return Result(False, message="positie bestaat niet")
        self.open[position].update(sl=sl, tp=tp)
        return Result(True, position)

    def close_position(self, market, position, comment="KATSU sluit") -> Result:
        self.calls.append(("close", position))
        if position not in self.open:
            return Result(False, message="positie bestaat niet")
        p = self.open[position]
        tick = self.ticks[market]
        price = tick.bid if p["direction"] == "LONG" else tick.ask
        self._close(position, price, tick.time, "KATSU")
        return Result(True, position, price)

    # ---- toestand
    def pending_orders(self, magics):
        return [PendingInfo(t, o["market"], o["magic"], o["comment"], o["price"], o["sl"], o["tp"], o["volume"])
                for t, o in self.pending.items() if o["magic"] in magics]

    def positions(self, magics):
        out = []
        for t, p in self.open.items():
            if p["magic"] in magics:
                tick = self.ticks[p["market"]]
                s = 1 if p["direction"] == "LONG" else -1
                px = tick.bid if s > 0 else tick.ask
                out.append(PositionInfo(t, p["market"], p["magic"], p["comment"], p["direction"], p["price_open"],
                                        p["sl"], p["tp"], p["volume"], p["time"],
                                        s * (px - p["price_open"]) * CONTRACT[p["market"]] * p["volume"], 0.0))
        return out

    def closed_position(self, position):
        c = self.closed.get(position)
        if c is None:
            return None
        return ClosedInfo(c["price_open"], c["time"], c["exit"], c["exit_time"], c["reason"], c["profit"],
                          c["commission"], 0.0)

    def order_was_filled(self, ticket):
        return ticket if (ticket in self.open or ticket in self.closed) else None


__all__ = ["FakeBroker", "rates_to_frame"]
