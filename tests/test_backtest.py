"""
Tests voor de backtest-laag (katsu/backtest.py).

Kerncijfers, met de hand uitgerekend voor r = [2, −1, −1, 2, −1,1, −0,5]:
  winrate      = 2 winnaars / 6                         = 0,333
  totaal       = 2 − 1 − 1 + 2 − 1,1 − 0,5              = +0,4
  gemiddelde   = 0,4 / 6                                = +0,0667
  profit factor= (2 + 2) / (1 + 1 + 1,1 + 0,5) = 4 / 3,6 = 1,111
  cumulatief   = 0 → 2 → 1 → 0 → 2 → 0,9 → 0,4
  max drawdown = van top 2 naar 0                       = 2,0
  verliesreeks = (−1, −1) en (−1,1, −0,5)               = 2
"""
import numpy as np
import pandas as pd
import pytest

from katsu.backtest import (MarketData, in_sample, metrics, run_variant, session_be, summary)
from katsu.execution import Instrument, M1, make_plan, run_portfolio
from katsu.signals import detect_setups


def test_metrics_handberekend():
    m = metrics([2, -1, -1, 2, -1.1, -0.5])
    assert m["trades"] == 6
    assert m["winrate"] == pytest.approx(1 / 3)
    assert m["totaal_r"] == pytest.approx(0.4)
    assert m["gem_r"] == pytest.approx(0.4 / 6)
    assert m["pf"] == pytest.approx(4 / 3.6)
    assert m["max_dd"] == pytest.approx(2.0)
    assert m["max_verliesreeks"] == 2


def test_metrics_drawdown_vanaf_start_telt():
    # meteen verlies: de start (0) is de top -> drawdown 1,5
    assert metrics([-1, -0.5, 2])["max_dd"] == pytest.approx(1.5)


def test_metrics_leeg_en_zonder_verlies():
    assert metrics([])["trades"] == 0
    assert metrics([1, 2])["pf"] == np.inf


def test_sessies():
    assert [session_be(h) for h in (3, 8, 13, 14, 17, 18, 23)] == \
        ["Azië", "Londen", "Londen", "Londen+NY", "Londen+NY", "NY", "NY"]


def test_out_of_sample_wordt_weggesneden():
    idx = pd.to_datetime(["2024-12-31 23:59", "2025-01-01 00:00", "2026-03-01 10:00"])
    df = pd.DataFrame({"close": [1, 2, 3]}, index=idx)
    assert list(in_sample(df).index) == [pd.Timestamp("2024-12-31 23:59")]


def _random_m1(days=15, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-03-04 00:00", periods=days * 1440, freq="1min")
    idx = idx[idx.dayofweek < 5]
    p = 2000 + np.cumsum(rng.normal(0, 0.3, len(idx)))
    o = np.r_[p[0], p[:-1]]
    hi = np.maximum(o, p) + rng.uniform(0, 0.2, len(idx))
    lo = np.minimum(o, p) - rng.uniform(0, 0.2, len(idx))
    return pd.DataFrame({"open": o, "high": hi, "low": lo, "close": p,
                         "tickvol": 1, "spread": 15}, index=idx)


def test_variant_gebruikt_exact_dezelfde_code_als_de_bouwstenen():
    """De backtest mag niets anders doen dan detect_setups -> make_plan -> run_portfolio."""
    m1 = _random_m1()
    ins = Instrument("XAUUSD", slip=0.25)
    md = MarketData("XAUUSD", m1, ins)
    out = run_variant([md], "5min", "A", 1)
    b, a, _ = md.tf_bars("5min")
    setups = detect_setups(b, "5min", md.h1_trend, L=1)
    assert len(setups) > 0
    ref = run_portfolio([make_plan(s, b, "5min", a, "A", ins) for s in setups],
                        {"XAUUSD": M1(m1, ins)}, {"XAUUSD": ins})
    assert len(out) == len(ref)
    assert list(out.status) == list(ref.status)
    np.testing.assert_allclose(out.r_net.to_numpy(float), ref.r_net.to_numpy(float), equal_nan=True)
    assert set(out.variant) == {"M5-A-L1"}
    assert {"uur_be", "sessie", "trend_H4", "trend_D1", "sweep_diepte_atr"} <= set(out.columns)


def test_meer_slippage_is_nooit_beter():
    m1 = _random_m1()
    md = MarketData("XAUUSD", m1, Instrument("XAUUSD"))
    r = {s: run_variant([md], "5min", "A", 1, slip={"XAUUSD": s}) for s in (0.10, 0.50)}
    lo = r[0.10][r[0.10].status == "gesloten"].r_gross.sum()
    hi = r[0.50][r[0.50].status == "gesloten"].r_gross.sum()
    assert hi <= lo


def test_summary_telt_alleen_gesloten_trades():
    t = pd.DataFrame({"status": ["gesloten", "dagstop", "gesloten", "niet_gevuld"],
                      "market": ["X", "X", "X", "X"], "r_net": [2.0, np.nan, -1.0, np.nan],
                      "entry_time": pd.to_datetime(["2024-01-01", None, "2024-01-02", None])})
    s = summary(t, ["market"])
    assert s.loc[0, "trades"] == 2 and s.loc[0, "totaal_r"] == pytest.approx(1.0)


def test_bos_variant_gebruikt_dezelfde_bouwstenen():
    """Bouwsteen 2 in de backtest = detect_bos -> make_bos_plan -> run_portfolio, niets anders."""
    from katsu.bos import detect_bos, make_bos_plan
    m1 = _random_m1()
    ins = Instrument("XAUUSD", slip=0.25)
    md = MarketData("XAUUSD", m1, ins)
    for v in ("A", "B"):
        out = run_variant([md], "5min", v, 1, block="bos")
        b, a, _ = md.tf_bars("5min")
        setups = detect_bos(b, "5min", md.h1_trend, L=1)
        assert len(setups) > 0
        ref = run_portfolio([make_bos_plan(s, "5min", a, v, ins) for s in setups],
                            {"XAUUSD": M1(m1, ins)}, {"XAUUSD": ins})
        assert list(out.status) == list(ref.status)
        np.testing.assert_allclose(out.r_net.to_numpy(float), ref.r_net.to_numpy(float), equal_nan=True)
        assert set(out.variant) == {f"BOS-M5-{v}-L1"}
        assert "niveau_tot_hl_atr" in out.columns


def test_onbekende_bouwsteen_geeft_fout():
    md = MarketData("XAUUSD", _random_m1(days=3), Instrument("XAUUSD"))
    with pytest.raises(ValueError):
        md.setups("5min", 1, "fibonacci")


def test_frictionless_houdt_dezelfde_setups_als_het_kostenplafond():
    """Diagnose zonder kosten mag geen setups toevoegen die bij echte kosten weggevallen zouden zijn."""
    m1 = _random_m1()
    md = MarketData("XAUUSD", m1, Instrument("XAUUSD", slip=0.25, swap=0.4, rollover_min_spread=0.5))
    echt = run_variant([md], "5min", "B", 1, block="bos")
    zonder = run_variant([md], "5min", "B", 1, block="bos", frictionless=True)
    weg = set(echt.loc[echt.status == "kosten_te_hoog", "signal_time"])
    assert len(weg) > 0
    assert weg.isdisjoint(set(zonder.signal_time))
    g = zonder[zonder.status == "gesloten"]
    assert (g.cost_r == 0).all()            # geen commissie en geen swap


def test_placebo_geeft_trades_met_de_gevraagde_sl_grootte():
    from katsu.backtest import placebo
    md = MarketData("XAUUSD", _random_m1(), Instrument("XAUUSD"))
    out = placebo(md, "5min", np.array([3.0]), n=50, frictionless=True)
    g = out[out.status == "gesloten"]
    assert len(g) > 10
    assert set(g.direction) == {"LONG", "SHORT"}
    # zonder kosten: SL = anker − 0,1 ATR buffer -> risk ≈ 3,1 ATR (entry = open volgende candle ≈ close)
    b, a, _ = md.tf_bars("5min")
    assert g.risk.median() > 2.0 * a.median()


def test_stresstest_verandert_niet_welke_setups_genomen_worden():
    """Het kostenplafond beslist op de basis-slippage; de stresstest maakt alleen de uitvoering slechter.
    (Per setup gecontroleerd: welke setups later 'positie_open' zijn, mag wel verschillen,
    want exits liggen bij meer slippage anders.)"""
    from dataclasses import replace
    from katsu.bos import detect_bos, make_bos_plan
    from katsu.execution import planned_cost_r
    m1 = _random_m1()
    basis = Instrument("XAUUSD", slip=0.25)
    stress = replace(basis, slip=0.50, cap_slip=0.25)
    md = MarketData("XAUUSD", m1, basis)
    b, a, _ = md.tf_bars("5min")
    plans = [make_bos_plan(s, "5min", a, "B", basis) for s in detect_bos(b, "5min", md.h1_trend, L=1)]
    db, ds = M1(m1, basis), M1(m1, stress)
    weg_b = [planned_cost_r(p, db, basis)[1] > 0.2 for p in plans]
    weg_s = [planned_cost_r(p, ds, stress)[1] > 0.2 for p in plans]
    assert any(weg_b) and weg_b == weg_s


def test_fvg_variant_gebruikt_dezelfde_bouwstenen():
    """Bouwsteen 3 in de backtest = detect_fvg -> make_fvg_plan -> run_portfolio, niets anders."""
    from katsu.fvg import detect_fvg, make_fvg_plan
    m1 = _random_m1()
    ins = Instrument("XAUUSD", slip=0.25)
    md = MarketData("XAUUSD", m1, ins)
    for v, f in (("A", "T0"), ("B", "T+")):
        out = run_variant([md], "5min", v, f, block="fvg")
        b, a, _ = md.tf_bars("5min")
        setups = detect_fvg(b, "5min", md.ctx_trend, filt=f)
        assert len(setups) > 0
        ref = run_portfolio([make_fvg_plan(s, "5min", a, v, ins) for s in setups],
                            {"XAUUSD": M1(m1, ins)}, {"XAUUSD": ins})
        assert list(out.status) == list(ref.status)
        np.testing.assert_allclose(out.r_net.to_numpy(float), ref.r_net.to_numpy(float), equal_nan=True)
        assert set(out.variant) == {f"FVG-M5-{v}-{f}"}
        assert "fvg_grootte_atr" in out.columns
