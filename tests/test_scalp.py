"""Spec v0.8 — handberekende scenario's voor vector candles, ADR, ronde getallen en de nieuwe motoropties."""
import numpy as np
import pandas as pd
import pytest

from katsu import scalp
from katsu.execution import EURUSD, M1, OrderPlan, simulate
from dataclasses import replace


def m1_frame(start, closes, tickvol=10, spread=0):
    """M1-candles met open = vorige close, high/low = max/min(open, close)."""
    idx = pd.date_range(start, periods=len(closes), freq="1min")
    c = np.asarray(closes, float)
    o = np.r_[c[0], c[:-1]]
    tv = np.broadcast_to(np.asarray(tickvol), c.shape).astype(int)
    return pd.DataFrame({"open": o, "high": np.maximum(o, c), "low": np.minimum(o, c), "close": c,
                         "tickvol": tv, "spread": spread}, index=idx)


# ---------------- vector candles ----------------

def test_vector_volume_200_procent():
    # 11 M5-candles: 10 × volume 50 (5 M1 × 10), dan 100 = exact 2 × het gemiddelde -> climax.
    m5 = pd.DataFrame({"open": [1.0] * 11, "high": [1.001] * 11, "low": [0.999] * 11,
                       "close": [1.0] * 10 + [1.0005], "tickvol": [50] * 10 + [100]},
                      index=pd.date_range("2025-03-03 10:00", periods=11, freq="5min"))
    v = scalp.vectors(m5)
    assert v[-1] == 1                       # bull: close > open
    assert (v[:10] == 0).all()              # te weinig geschiedenis of geen uitschieter
    # 99 < 2 × 50, en range × volume = 0,001 × 99 = 0,099 < hoogste vorige 0,002 × 50 = 0,100 -> geen vector
    m5.loc[m5.index[-1], ["tickvol", "high", "low"]] = [99, 1.0005, 0.9995]
    assert scalp.vectors(m5)[-1] == 0


def test_vector_range_maal_volume():
    # Volume niet 2×, maar range × volume het hoogste van de 10 vorige -> toch climax.
    m5 = pd.DataFrame({"open": [1.0] * 11, "high": [1.001] * 10 + [1.003], "low": [0.999] * 10 + [0.9995],
                       "close": [1.0] * 10 + [0.9996], "tickvol": [50] * 10 + [60]},
                      index=pd.date_range("2025-03-03 10:00", periods=11, freq="5min"))
    assert scalp.vectors(m5)[-1] == -1      # 0,0035 × 60 = 0,21 ≥ 0,002 × 50 = 0,10; bear


# ---------------- ADR ----------------

def test_adr_gemiddelde_van_14_vorige_dagen():
    days = pd.bdate_range("2025-03-03", periods=16)
    rows = []
    for i, d in enumerate(days):            # dag i heeft range (i + 1) × 0,001
        rows.append(m1_frame(d + pd.Timedelta(hours=10), [1.0, 1.0 + (i + 1) * 0.001]))
    m1 = pd.concat(rows)
    adr = scalp.adr_series(m1)
    assert np.isnan(adr.iloc[13])
    assert adr.iloc[14] == pytest.approx(np.mean(np.arange(1, 15)) * 0.001)    # dagen 1..14 -> 7,5 pips × 10
    assert adr.iloc[15] == pytest.approx(np.mean(np.arange(2, 16)) * 0.001)


# ---------------- signalen op een handgemaakte dag ----------------

def frame_for_signals(closes, start="2025-03-17 10:00"):
    """Features met een vaste ADR van 100 pips (zodat de ADR-filter niet in de weg zit)."""
    f = scalp.features(m1_frame(start, closes))
    f["adr"] = 0.0100
    f["atr"] = 0.0003
    f["vec"] = 0
    return f


def test_v3_sell_limit_voor_het_ronde_getal():
    # Koers stijgt in 1 u van 1.0880 naar 1.0895: 5 pips onder 1.0900, kwam van 20 pips onder -> sell limit 1.0899.
    closes = np.r_[np.full(60, 1.0880), np.linspace(1.0880, 1.0895, 60)]
    f = frame_for_signals(closes)
    sig = scalp.signals(f, "EURUSD")["V3"]
    shorts = [p for p in sig if p.direction == "SHORT"]
    assert len(shorts) == 1                               # één order per niveau per dag
    p = shorts[0]
    assert p.limit_price == pytest.approx(1.0899)
    assert p.anchor == pytest.approx(1.0906)              # 6 pips voorbij het niveau (+ spread in de motor)
    assert p.kind == "limit" and p.min_risk == pytest.approx(0.0006)
    assert p.valid_until == p.signal_time + 12 * scalp.M5


def test_v4_doorbraak_long():
    # Koers kruist 1.0850: M5-close 1.0853 na een close onder 1.0850 -> marktorder long, SL-anker 1.0844.
    closes = np.r_[np.full(60, 1.0840), np.full(5, 1.0846), np.full(5, 1.0853), np.full(30, 1.0853)]
    f = frame_for_signals(closes)
    sig = scalp.signals(f, "EURUSD")["V4"]
    longs = [p for p in sig if p.direction == "LONG"]
    assert len(longs) == 1
    assert longs[0].kind == "market" and longs[0].anchor == pytest.approx(1.0844)
    assert longs[0].signal_time == pd.Timestamp("2025-03-17 11:10")   # close van de M5-candle 11:05


def test_buiten_de_sessie_geen_signaal():
    closes = np.r_[np.full(60, 1.0840), np.full(5, 1.0846), np.full(5, 1.0853), np.full(30, 1.0853)]
    f = frame_for_signals(closes, start="2025-03-17 03:00")              # 02:00 Belgisch: Azië
    assert scalp.signals(f, "EURUSD")["V4"] == []


def test_geen_vooruitkijken_signalen_op_afgekapte_data():
    rng = np.random.default_rng(3)
    n = 60 * 24 * 25
    closes = 1.08 + np.cumsum(rng.normal(0, 0.00012, n))
    m1 = m1_frame("2025-03-03 00:00", closes, tickvol=rng.integers(5, 80, n))
    m1 = m1[m1.index.dayofweek < 5]
    full = scalp.signals(scalp.features(m1), "EURUSD")
    cut = pd.Timestamp("2025-03-20 15:00")
    part = scalp.signals(scalp.features(m1[m1.index < cut]), "EURUSD")
    for v in full:
        a = [p for p in full[v] if p.signal_time <= cut]
        assert a == part[v], v
    assert sum(len(x) for x in full.values()) > 50          # de test vergelijkt echt iets


# ---------------- motor: minimum-SL, minimum-RR, sluituur ----------------

INS = replace(EURUSD, min_spread=0.0, slip=0.0, commission=0.0, swap=0.0, swap_short=0.0, rollover_min_spread=0.0,
              point=0.0, min_sl_atr=0.0, close_at_min=scalp.CLOSE_AT_MIN)


def test_min_sl_schuift_de_sl():
    # Marktorder long op 1.1000, anker 1.0998 (2 pips) -> SL wordt 1.0994 (minimum 6 pips); TP 1,5R = 1.1009.
    m1 = m1_frame("2025-03-17 12:00", [1.1000] * 3 + [1.1009] * 3)
    plan = OrderPlan("LONG", pd.Timestamp("2025-03-17 12:01"), "market", 1.0998, 0.0, market="EURUSD",
                     tp_price=1.1100, max_rr=1.5, min_risk=0.0006, min_rr=1.0)
    tr = simulate(plan, M1(m1, INS), INS)
    assert tr.sl == pytest.approx(1.0994) and tr.tp == pytest.approx(1.1009)
    assert tr.exit_reason == "TP" and tr.r_net == pytest.approx(1.5)


def test_min_rr_geen_trade_als_adr_te_dicht():
    # ADR-high op 1.1004: dat is maar 0,67R bij 6 pips risico -> geen trade.
    m1 = m1_frame("2025-03-17 12:00", [1.1000] * 5)
    plan = OrderPlan("LONG", pd.Timestamp("2025-03-17 12:01"), "market", 1.0994, 0.0, market="EURUSD",
                     tp_price=1.1004, max_rr=1.5, min_risk=0.0006, min_rr=1.0)
    assert simulate(plan, M1(m1, INS), INS).status == "tp_te_klein"


def test_sluiten_om_23u45_server():
    # Gevuld om 23:30; niets geraakt -> gesloten op de close van de candle 23:44 (de laatste vóór 23:45).
    m1 = m1_frame("2025-03-17 23:30", [1.1000] * 14 + [1.1002] + [1.1003] * 10)
    plan = OrderPlan("LONG", pd.Timestamp("2025-03-17 23:30"), "market", 1.0990, 0.0, market="EURUSD",
                     tp_price=1.1100, max_rr=1.5, min_risk=0.0006)
    tr = simulate(plan, M1(m1, INS), INS)
    assert tr.exit_reason == "EINDE_DAG" and tr.exit_time == pd.Timestamp("2025-03-17 23:44")
    assert tr.exit_price == pytest.approx(1.1002)


def test_limiet_vervalt_om_23u45():
    m1 = m1_frame("2025-03-17 23:40", [1.1010] * 10 + [1.0990] * 5)      # zakt pas om 23:50 tot de limiet
    plan = OrderPlan("LONG", pd.Timestamp("2025-03-17 23:40"), "limit", 1.0980, 0.0, 1.0995,
                     pd.Timestamp("2025-03-18 01:00"), market="EURUSD", tp_price=1.1100, max_rr=1.5, min_risk=0.0006)
    assert simulate(plan, M1(m1, INS), INS).status == "niet_gevuld"
