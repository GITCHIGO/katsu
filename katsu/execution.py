"""
Uitvoering op M1 (spec §4–6): hoe een setup een echte trade wordt.

Prijzen in de MT5-data zijn BID. ASK = BID + spread.
- Een long koopt op ASK en wordt gesloten op BID (SL/TP kijken naar de BID).
- Een short verkoopt op BID en wordt gesloten op ASK (SL/TP kijken naar de ASK).

Conservatieve regels (geen gunstige aannames):
- Spread = max(spread van de candle, minimum uit de config). MT5 bewaart de laagste spread per candle.
- Slippage: elke markt- en stoporder wordt `slip_ticks` slechter gevuld.
- Opent een candle al voorbij de SL (gap), dan wordt gevuld op die open (min slippage).
- Raakt één M1-candle zowel SL als TP, dan telt de SL.
- TP is een limietorder: gevuld exact op de TP, nooit beter.
- Bij een limiet-entry (variant B) wordt op de vulcandle alleen de SL gecontroleerd,
  niet de TP (we weten niet of de high vóór of na de vulling kwam).
- Looptijd (gewijzigd 9 okt 2026): een trade loopt tot SL of TP, ook over nacht en weekend.
  Per nacht (elke servermiddernacht; vrijdag -> maandag = 3 nachten) wordt swap aangerekend.
  Gaps over nacht of weekend vullen de SL op de open (zie hierboven).
  Rond de rollover (23:55–01:30 server) wordt de spread verbreed (MT5 bewaart alleen de laagste).
  Oud gedrag (sluiten om 00:00 server = 23:00 Brussel) blijft beschikbaar met close_eod=True.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from katsu.signals import LONG, Setup


@dataclass(frozen=True)
class Instrument:
    name: str = "XAUUSD"
    tick: float = 0.01            # kleinste prijsstap
    point: float = 0.01           # eenheid van de MT5-spreadkolom
    min_spread: float = 0.10      # minimum spread in prijs (spec §2)
    slip: float = 0.25            # slippage in prijs per markt-/stopuitvoering (spec §5, basis)
    commission: float = 0.08      # commissie round turn per eenheid, in prijs (€7/lot ≈ $0,08/oz)
    rr: float = 2.0               # TP in R
    sl_atr_buffer: float = 0.1    # SL-buffer = spread + 0,1 × ATR
    min_sl_atr: float = 1.0       # minimale SL-afstand = 1 × ATR
    limit_valid_bars: int = 6     # variant B: geldigheid limietorder in setup-candles
    cap_slip: float | None = None # slippage waarmee het kostenplafond rekent (None = slip).
                                  # Bij een stresstest blijft de beslissing op de basis-slippage,
                                  # alleen de uitvoering wordt slechter.
    swap: float = 0.0             # swapkost LONG per eenheid per nacht, in prijs (positief = kost)
    swap_short: float | None = None   # swapkost SHORT; None = zelfde als long. Een swap-opbrengst
                                      # wordt bewust niet meegeteld (0 = gratis, nooit negatief)
    rollover_min_spread: float = 0.0  # spread tijdens rollover = max(2 × data, dit); 0 = uit
    close_eod: bool = False       # True = oud gedrag: sluiten om 00:00 server (23:00 BE)
    max_hold_days: float | None = None    # maximale looptijd in kalenderdagen; daarna sluiten op de close
    swap_pct_long: float | None = None    # swap als % van de prijs per jaar (long); vervangt `swap` als gezet
    swap_pct_short: float | None = None   # idem short (None = zelfde als long)


# Vastgelegde instellingen per markt (spec §2 en §5).
# Swap: VOORLOPIG en bewust ongunstig (beide richtingen als kost) tot de echte MT5-waarden binnen zijn.
XAUUSD = Instrument("XAUUSD", tick=0.01, point=0.01, min_spread=0.10, slip=0.25, commission=0.08,
                    swap=0.40, rollover_min_spread=0.50)          # $40/lot/nacht · rollover min $0,50
EURUSD = Instrument("EURUSD", tick=0.00001, point=0.00001, min_spread=0.00001, slip=0.00003,
                    commission=0.00008,                            # €7/lot ≈ $8 per 100.000 = 0,8 pip
                    swap=0.00008, swap_short=0.0,                  # gemeten op Gitchi's trades (sep-okt 2026):
                                                                   # long ≈ −€7/lot/nacht ≈ 0,8 pip; short ≈ +€1,4–3,8
                                                                   # (opbrengst, niet meegeteld)
                    rollover_min_spread=0.00005)                   # rollover min 0,5 pip

ROLLOVER_START, ROLLOVER_END = 23 * 60 + 55, 90   # servertijd in minuten: 23:55 tot 01:30
CHUNK = 2880                                      # aantal M1-candles per zoekstap (2 dagen)


@dataclass(frozen=True)
class OrderPlan:
    direction: str
    signal_time: pd.Timestamp
    kind: str                       # "market" of "limit"
    anchor: float                   # sweep-extreme (basis voor de SL)
    atr: float                      # ATR14 van de setup-timeframe op het signaal
    limit_price: float | None = None
    valid_until: pd.Timestamp | None = None
    market: str = "XAUUSD"
    max_cost_r: float | None = None   # kostenplafond (spec v0.2 §4); None = geen plafond


@dataclass
class Trade:
    direction: str
    signal_time: pd.Timestamp
    status: str                     # "gesloten", "sl_te_klein", "kosten_te_hoog", "niet_gevuld", "geen_data"
    entry_time: pd.Timestamp | None = None
    fill: float | None = None
    sl: float | None = None
    tp: float | None = None
    risk: float | None = None
    exit_time: pd.Timestamp | None = None
    exit_price: float | None = None
    exit_reason: str | None = None  # "TP", "SL", "EINDE_DATA" (of "EINDE_DAG" met close_eod)
    r_gross: float | None = None
    cost_r: float | None = None
    r_net: float | None = None
    nights: int | None = None       # aantal servermiddernachten dat de trade openstond
    swap_r: float | None = None     # swapkost in R (zit ook in cost_r)

    def as_dict(self) -> dict:
        return asdict(self)


class M1:
    """Snelle toegang tot M1-data als numpy-reeksen."""
    def __init__(self, m1: pd.DataFrame, ins: Instrument):
        self.t = m1.index
        self.o = m1["open"].to_numpy(float); self.h = m1["high"].to_numpy(float)
        self.lo = m1["low"].to_numpy(float); self.c = m1["close"].to_numpy(float)
        self.sp = np.maximum(m1["spread"].to_numpy(float) * ins.point, ins.min_spread)
        if ins.rollover_min_spread > 0:
            mins = self.t.hour * 60 + self.t.minute
            win = np.asarray((mins >= ROLLOVER_START) | (mins < ROLLOVER_END))
            self.sp[win] = np.maximum(2 * self.sp[win], ins.rollover_min_spread)
        self.day = self.t.values.astype("datetime64[D]").astype(np.int64)   # serverdatum als getal


def _round_tick(x: float, tick: float) -> float:
    return round(round(x / tick) * tick, 10)


def planned_cost_r(plan: OrderPlan, d: M1, ins: Instrument, i: int | None = None):
    """
    Verwachte kosten in R op het moment dat de order vertrekt (spec v0.2 §4).
    Kosten = spread (met minimum) + 2 × slippage + commissie.
    R = geplande entry (markt: open + spread + slippage; limiet: limietprijs) tot de geplande SL.
    Geeft (risk, kosten_in_R); kosten_in_R is None als de risk niet positief is of er geen data is.
    """
    if i is None:
        i = int(d.t.searchsorted(plan.signal_time))
    if i >= len(d.t):                       # signaal na de laatste candle: geen data, geen order
        return None, None
    long = plan.direction == LONG
    s = 1.0 if long else -1.0
    sp0 = d.sp[i]
    slip = ins.slip if ins.cap_slip is None else ins.cap_slip
    if plan.kind == "market":
        planned = d.o[i] + sp0 + slip if long else d.o[i] - slip
    else:
        planned = plan.limit_price
    risk = s * (planned - (plan.anchor - s * (sp0 + ins.sl_atr_buffer * plan.atr)))
    cost = sp0 + 2 * slip + ins.commission
    return risk, (cost / risk if risk > 0 else None)


def simulate(plan: OrderPlan, d: M1, ins: Instrument) -> Trade:
    long = plan.direction == LONG
    s = 1.0 if long else -1.0
    slip = ins.slip
    i = int(d.t.searchsorted(plan.signal_time))      # eerste M1-candle die start op/na het signaal
    if i >= len(d.t):
        return Trade(plan.direction, plan.signal_time, "geen_data")

    # ---- Kostenplafond: beslist vóór de order vertrekt, met wat dan bekend is ----
    if plan.max_cost_r is not None:
        risk_plan, cost_r = planned_cost_r(plan, d, ins, i)
        if cost_r is None or cost_r > plan.max_cost_r:
            return Trade(plan.direction, plan.signal_time, "kosten_te_hoog", risk=risk_plan, cost_r=cost_r)

    # ---- Entry ----
    tp_from_same_bar = True
    if plan.kind == "market":
        fi = i
        fill = d.o[fi] + d.sp[fi] + slip if long else d.o[fi] - slip
    else:
        fi = None
        end_t = plan.valid_until
        j = i
        while j < len(d.t) and d.t[j] < end_t:
            ask_o, ask_l = d.o[j] + d.sp[j], d.lo[j] + d.sp[j]
            if long and ask_l <= plan.limit_price:
                fi = j; fill = min(plan.limit_price, ask_o); break
            if not long and d.h[j] >= plan.limit_price:
                fi = j; fill = max(plan.limit_price, d.o[j]); break
            j += 1
        if fi is None:
            return Trade(plan.direction, plan.signal_time, "niet_gevuld")
        tp_from_same_bar = False

    buffer = d.sp[fi] + ins.sl_atr_buffer * plan.atr
    sl = _round_tick(plan.anchor - s * buffer, ins.tick)
    risk = s * (fill - sl)
    if risk < ins.min_sl_atr * plan.atr:
        return Trade(plan.direction, plan.signal_time, "sl_te_klein", d.t[fi], fill, sl, None, risk)
    tp = _round_tick(fill + s * ins.rr * risk, ins.tick)

    # ---- Beheer tot exit ----
    if ins.close_eod:
        day_end = (d.t[fi] + pd.Timedelta(days=1)).normalize()    # 00:00 servertijd volgende dag
        end = int(d.t.searchsorted(day_end))
    else:
        end = len(d.t)
    if ins.max_hold_days is not None:
        end = min(end, int(d.t.searchsorted(d.t[fi] + pd.Timedelta(days=ins.max_hold_days))))
    k = None
    exit_price = reason = None
    for a in range(fi, end, CHUNK):
        b = min(a + CHUNK, end)
        sp = d.sp[a:b]
        if long:
            adv_o, adv, fav = d.o[a:b], d.lo[a:b], d.h[a:b]                       # BID
        else:
            adv_o, adv, fav = d.o[a:b] + sp, d.h[a:b] + sp, d.lo[a:b] + sp      # ASK
        sl_hit = s * (adv - sl) <= 0
        tp_hit = s * (fav - tp) >= 0
        if a == fi and not tp_from_same_bar:
            tp_hit[0] = False
        si = int(np.argmax(sl_hit)) if sl_hit.any() else None
        ti = int(np.argmax(tp_hit)) if tp_hit.any() else None
        if si is not None and (ti is None or si <= ti):         # zelfde candle: SL telt
            k = a + si
            gap = k != fi and s * (adv_o[si] - sl) <= 0
            exit_price = (adv_o[si] if gap else sl) - s * slip
            reason = "SL"; break
        if ti is not None:
            k = a + ti
            exit_price, reason = tp, "TP"; break
    if reason is None:
        k = end - 1                                                 # laatste candle (dag of data)
        close = d.c[k] if long else d.c[k] + d.sp[k]
        exit_price = close - s * slip
        if ins.close_eod:
            reason = "EINDE_DAG"
        elif end < len(d.t):
            reason = "MAX_DUUR"
        else:
            reason = "EINDE_DATA"

    r_gross = s * (exit_price - fill) / risk
    nights = int(d.day[k] - d.day[fi])
    if ins.swap_pct_long is not None:
        pct = ins.swap_pct_long if (long or ins.swap_pct_short is None) else ins.swap_pct_short
        swap_rate = fill * pct / 365.0             # meegroeiend met de prijs
    else:
        swap_rate = ins.swap if (long or ins.swap_short is None) else ins.swap_short
    swap_r = max(swap_rate, 0.0) * nights / risk
    cost_r = ins.commission / risk + swap_r
    return Trade(plan.direction, plan.signal_time, "gesloten", d.t[fi], fill, sl, tp, risk,
                 d.t[k], exit_price, reason, r_gross, cost_r, r_gross - cost_r, nights, swap_r)


# ---------------- Van setup naar orderplan ----------------

def entry_level_variant_b(setup: Setup, bars: pd.DataFrame) -> float:
    """Eerste FVG in de CHoCH-beweging (bovenkant bij long, onderkant bij short), anders 50%."""
    h = bars["high"].to_numpy(float); lo = bars["low"].to_numpy(float); c = bars["close"].to_numpy(float)
    a, b = setup.sweep_index, setup.choch_index
    for i in range(a + 1, b):                         # FVG-midden-candle i, met i-1 >= a en i+1 <= b
        if setup.direction == LONG and lo[i + 1] > h[i - 1]:
            return float(lo[i + 1])
        if setup.direction != LONG and h[i + 1] < lo[i - 1]:
            return float(h[i + 1])
    return float((setup.sweep_extreme + c[b]) / 2)


def make_plan(setup: Setup, bars: pd.DataFrame, tf: str, atr_series: pd.Series,
              variant: str, ins: Instrument) -> OrderPlan:
    atr = float(atr_series.iloc[setup.choch_index])
    if variant == "A":
        return OrderPlan(setup.direction, setup.signal_time, "market", setup.sweep_extreme, atr,
                         market=ins.name)
    lvl = entry_level_variant_b(setup, bars)
    valid = setup.signal_time + ins.limit_valid_bars * pd.Timedelta(tf)
    return OrderPlan(setup.direction, setup.signal_time, "limit", setup.sweep_extreme, atr, lvl, valid,
                     market=ins.name)


# ---------------- Portefeuille: 1 positie per markt, gezamenlijke dagstop ----------------

def run_portfolio(plans: list[OrderPlan], data: dict, instruments: dict, day_stop_r: float = -2.0,
                  server_offset_h: int = 1) -> pd.DataFrame:
    """
    Speelt de plannen van alle markten in tijdsvolgorde af (spec §6):
    - maximaal 1 positie (of lopende limietorder) per markt;
    - na day_stop_r (som netto R over ALLE markten) op een Brusselse kalenderdag geen nieuwe trades;
      een resultaat telt pas mee vanaf het moment dat de trade gesloten is, op de dag van de exit
      (gecorrigeerd 9 okt 2026: vroeger telde een lopende trade van de andere markt al mee);
    - overgeslagen setups worden ook gelogd (status 'positie_open' of 'dagstop').
    `data` en `instruments` zijn dicts per marktnaam (M1-object en Instrument).
    """
    import heapq
    rows = []
    busy_until: dict = {}
    day_r: dict = {}          # gerealiseerde netto R per Brusselse dag (op de dag van de EXIT)
    pending: list = []        # (exit_time, volgnr, exit_dag, r_net) van trades die nog lopen

    def be_day(ts):
        return (ts - pd.Timedelta(hours=server_offset_h)).date()

    for n, p in enumerate(sorted(plans, key=lambda x: (x.signal_time, x.market))):
        # Alleen resultaten die op dit moment al gerealiseerd zijn, tellen mee (geen vooruitkijken).
        while pending and pending[0][0] <= p.signal_time:
            _, _, dd, r = heapq.heappop(pending)
            day_r[dd] = day_r.get(dd, 0.0) + r
        day = be_day(p.signal_time)
        base = {"market": p.market, "direction": p.direction, "signal_time": p.signal_time}
        if p.signal_time < busy_until.get(p.market, pd.Timestamp.min):
            rows.append({**base, "status": "positie_open"}); continue
        if day_r.get(day, 0.0) <= day_stop_r:
            rows.append({**base, "status": "dagstop"}); continue
        tr = simulate(p, data[p.market], instruments[p.market])
        if tr.status == "gesloten":
            busy_until[p.market] = tr.exit_time + pd.Timedelta(minutes=1)
            heapq.heappush(pending, (tr.exit_time + pd.Timedelta(minutes=1), n, be_day(tr.exit_time),
                                     tr.r_net))
        elif tr.status == "niet_gevuld" and p.valid_until is not None:
            busy_until[p.market] = p.valid_until
        rows.append({"market": p.market, **tr.as_dict()})
    return pd.DataFrame(rows)
