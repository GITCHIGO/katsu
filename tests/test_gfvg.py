"""
Gitchi-FVG (spec v0.4, versie 2), met de hand uitgerekend. L = 1 om de reeksen kort te houden, ATR = 1.

Reeks LONG (index: open, high, low, close):
 0  100 101  99   100
 1  100 110 100   105    swing high 110 (bevestigd op 2)  -> later het TP-doel
 2  105 106 103   104
 3  104 105 101   102
 4  102 103 100   101
 5  101 105 100,5 104    swing high 105 (bevestigd op 6)  -> de "vorige high"
 6  104 104 102   102,5
 7  102,5 103 98  99     bearish candle, laagste low 98 -> oorsprong én order block
 8  99  101 98,5  100,8  candle 1 van de FVG (high 101)
 9  100,8 106 100,7 105,8  candle 2: sluit boven 105 -> breuk door de middelste candle
10  104 107 102 106,8    candle 3: low 102 > high(8) 101 -> gat 101–102 (1 ATR); body 2,8 / range 5 = 0,56
11  106,8 106,9 105 105,5
12  105,5 106 104 104,5
Verwacht: rand 102, midden 101,5, SL-basis = laagste low OB(7)..candle 2(9) = 98,
TP = 110 (oude high, nooit meer geraakt, boven de top van het been 107).
"""
import pandas as pd
import pytest

from katsu.execution import M1, Instrument, OrderPlan, simulate
from katsu.gfvg import detect_gfvg, make_gfvg_plan

BASE = [(100, 101, 99, 100), (100, 110, 100, 105), (105, 106, 103, 104), (104, 105, 101, 102),
        (102, 103, 100, 101), (101, 105, 100.5, 104), (104, 104, 102, 102.5), (102.5, 103, 98, 99),
        (99, 101, 98.5, 100.8), (100.8, 106, 100.7, 105.8), (104, 107, 102, 106.8),
        (106.8, 106.9, 105, 105.5), (105.5, 106, 104, 104.5)]


def bars(rows, mirror=False):
    if mirror:   # spiegel rond 200: high' = 200 − low enz. -> exact dezelfde setup als SHORT
        rows = [(200 - o, 200 - l, 200 - h, 200 - c) for o, h, l, c in rows]
    idx = pd.date_range("2018-03-05 08:00", periods=len(rows), freq="15min")
    o, h, l, c = zip(*rows)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "spread": 0}, index=idx)


def longs(rows, atr=1.0):
    b = bars(rows)
    return [s for s in detect_gfvg(b, [atr] * len(b), L=1) if s.direction == "LONG"]


def test_long_basis():
    (s,) = longs(BASE)
    assert (s.break_index, s.fvg_index, s.signal_index) == (9, 10, 10)
    assert (s.broken_level, s.swing_index, s.origin_index, s.ob_index) == (105, 5, 7, 7)
    assert (s.edge, s.gap_far, s.anchor, s.tp) == (102, 101, 98, 110)
    assert s.entry(0.0) == 102 and s.entry(0.5) == 101.5


def test_short_is_exact_gespiegeld():
    b = bars(BASE, mirror=True)
    (s,) = [x for x in detect_gfvg(b, [1.0] * len(b), L=1) if x.direction == "SHORT"]
    assert (s.fvg_index, s.break_index, s.broken_level) == (10, 9, 95)
    assert (s.edge, s.gap_far, s.anchor, s.tp) == (98, 99, 102, 90)
    assert s.entry(0.5) == 98.5


def test_middelste_candle_moet_breken():
    # candle 9 sluit op 104,9 (onder 105); pas candle 10 sluit erboven -> de breuk zit in candle 3: geen setup
    rows = BASE[:9] + [(100.8, 105, 100.7, 104.9), (104, 107, 102, 106.8), (106.8, 106.9, 104.5, 105.5),
                       (105.5, 106, 104, 104.5)]
    assert longs(rows) == []


def test_te_krap_gat():
    assert longs(BASE, atr=2.5) == []          # gat 1 < 0,5 × 2,5 = 1,25
    assert len(longs(BASE, atr=2.0)) == 1      # gat 1 = 0,5 × 2,0: precies genoeg


def test_candle_3_met_alleen_wick_telt_niet():
    rows = BASE[:10] + [(105.8, 107, 102, 105.0)] + BASE[11:]    # body 0,8 / range 5 = 0,16 < 0,25
    assert longs(rows) == []


def test_geen_oude_high_erboven_geen_tp():
    rows = [(100, 101, 99, 100), (100, 102, 100, 101)] + BASE[2:]   # oude high nu 102 i.p.v. 110
    (s,) = longs(rows)
    assert s.tp is None
    b = bars(rows)
    assert make_gfvg_plan(s, b, [1.0] * len(b), "ongeldig", "EURUSD") is None


def test_orderplan():
    b = bars(BASE)
    (s,) = longs(BASE)
    a = [1.0] * len(b)
    t_sig = b.index[10] + pd.Timedelta("15min")
    # standaard (keuze Gitchi): entry 61,8% in het gat = 102 − 0,618 × 1 = 101,382
    # geplande SL = 98 − 0,1 = 97,9 · risico 3,482 · 2R-niveau = 101,382 + 6,964 = 108,346 < oude high 110
    p = make_gfvg_plan(s, b, a, "24u", "EURUSD")
    assert p.signal_time == t_sig and p.kind == "limit" and p.limit_price == pytest.approx(101.382)
    assert p.valid_until == t_sig + pd.Timedelta(hours=24)
    assert p.tp_price == 110 and p.max_rr == 2.0 and p.cancel_price == pytest.approx(108.346)
    assert p.anchor == 98 and p.max_cost_r == 0.2
    q = make_gfvg_plan(s, b, a, "ongeldig", "EURUSD", entry_frac=0.0, max_rr=None)
    assert q.limit_price == 102 and q.cancel_price == 110 and q.max_rr is None
    assert q.valid_until == b.index[-1] + pd.Timedelta("15min")         # reeks korter dan 480 candles


def test_orderplan_short_plafond():
    b = bars(BASE, mirror=True)
    (s,) = [x for x in detect_gfvg(b, [1.0] * len(b), L=1) if x.direction == "SHORT"]
    p = make_gfvg_plan(s, b, [1.0] * len(b), "24u", "EURUSD")
    assert p.limit_price == pytest.approx(98.618) and p.cancel_price == pytest.approx(200 - 108.346)


# ---------------- uitvoering: vaste TP en annulering ----------------
INS = Instrument(slip=0.01)
T0 = pd.Timestamp("2025-01-06 10:00")


def m1(rows):
    idx = pd.date_range(T0, periods=len(rows), freq="1min")
    o, h, l, c = zip(*rows)
    return M1(pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "spread": 5}, index=idx), INS)


def plan(**kw):
    return OrderPlan("LONG", T0, "limit", 98.0, 1.0, 99.5, T0 + pd.Timedelta(minutes=10), **kw)


def test_vaste_tp_prijs():
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 100.3, 99.3, 99.6), (99.6, 103.2, 99.5, 103.0)])
    tr = simulate(plan(tp_price=103.0, cancel_price=103.0), d, INS)
    # gevuld op 99,50 · SL 97,80 · risk 1,70 · TP vast op 103,00 -> +3,5/1,7 = 2,0588R bruto
    assert (tr.fill, tr.sl, tr.tp, tr.exit_reason) == (99.5, 97.8, 103.0, "TP")
    assert tr.r_gross == pytest.approx(3.5 / 1.7)


def test_annuleren_als_tp_eerst_geraakt_wordt():
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 103.1, 100.1, 102.9), (102.9, 103, 99.0, 99.2)])
    tr = simulate(plan(tp_price=103.0, cancel_price=103.0), d, INS)
    assert tr.status == "geannuleerd" and tr.exit_time == T0 + pd.Timedelta(minutes=1)


def test_annuleren_wint_bij_twijfel_in_dezelfde_candle():
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 103.1, 99.0, 100.0)])     # raakt entry én TP-niveau
    assert simulate(plan(tp_price=103.0, cancel_price=103.0), d, INS).status == "geannuleerd"


def test_tp_niet_voorbij_de_vulling():
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 100.3, 99.3, 99.6)])
    assert simulate(plan(tp_price=99.4), d, INS).status == "tp_ongeldig"


def test_portefeuille_annulering_geeft_de_markt_vrij():
    from katsu.execution import run_portfolio
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 103.1, 100.1, 102.9), (102.9, 103, 102.0, 102.5),
            (102.5, 102.6, 99.0, 99.2), (99.2, 99.4, 99.1, 99.3)])
    p1 = plan(tp_price=103.0, cancel_price=103.0)                       # geannuleerd op minuut 1
    p2 = OrderPlan("LONG", T0 + pd.Timedelta(minutes=2), "limit", 98.0, 1.0, 99.5,
                   T0 + pd.Timedelta(minutes=5), tp_price=105.0, cancel_price=105.0)
    out = run_portfolio([p1, p2], {"XAUUSD": d}, {"XAUUSD": INS})
    assert list(out.status) == ["geannuleerd", "gesloten"]


def test_tp_plafond_2r():
    # gevuld op 99,50 · SL 97,80 · risico 1,70 · oude high 105 ligt verder dan 2R (99,50 + 3,40 = 102,90)
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 100.3, 99.3, 99.6), (99.6, 103.0, 99.5, 102.95)])
    tr = simulate(plan(tp_price=105.0, cancel_price=102.9, max_rr=2.0), d, INS)
    assert tr.tp == 102.9 and tr.exit_reason == "TP" and tr.r_gross == pytest.approx(2.0)


def test_tp_oude_high_dichterbij_dan_2r():
    d = m1([(100, 100.5, 99.8, 100.2), (100.2, 100.3, 99.3, 99.6), (99.6, 101.5, 99.5, 101.2)])
    tr = simulate(plan(tp_price=101.0, cancel_price=101.0, max_rr=2.0), d, INS)
    assert tr.tp == 101.0 and tr.r_gross == pytest.approx(1.5 / 1.7)


def test_entry_38_2_procent_diep():
    b = bars(BASE)
    (s,) = longs(BASE)
    p = make_gfvg_plan(s, b, [1.0] * len(b), "24u", "EURUSD", entry_frac=0.382)
    assert p.limit_price == pytest.approx(102 - 0.382)               # 101,618
    bm = bars(BASE, mirror=True)
    (t,) = [x for x in detect_gfvg(bm, [1.0] * len(bm), L=1) if x.direction == "SHORT"]
    q = make_gfvg_plan(t, bm, [1.0] * len(bm), "24u", "EURUSD", entry_frac=0.382)
    assert q.limit_price == pytest.approx(98 + 0.382)                # gespiegeld: 98,382
