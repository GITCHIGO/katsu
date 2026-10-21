"""Rekenregels van het dashboard, met de hand uitgerekende voorbeelden."""
import numpy as np
import pandas as pd

from katsu.dashboard_calc import clustered_t, max_drawdown, one_at_a_time, usd

T = pd.Timestamp


def test_dollars_bij_vast_lot():
    df = pd.DataFrame({"markt": ["EURUSD", "XAUUSD"], "pips": [12.5, -30.0], "r_net": [1.25, -1.0],
                       "r_free": [1.3, -0.9], "risk_pips": [10.0, 30.0], "risk_pips_free": [9.8, 29.0]})
    lots = {"EURUSD": 0.10, "XAUUSD": 0.02}
    # EURUSD: 12,5 pips × 10 $ × 0,10 lot = 12,50 $ ; goud: −30 pips (= −3,00 $ koers) × 10 × 0,02 = −6,00 $
    assert np.allclose(usd(df, lots), [12.5, -6.0])
    # zonder kosten: 1,3R × 9,8 pips × 10 × 0,1 = 12,74 $ ; −0,9R × 29 × 10 × 0,02 = −5,22 $
    assert np.allclose(usd(df, lots, "r_free"), [12.74, -5.22])


def test_een_trade_tegelijk_per_markt():
    df = pd.DataFrame({
        "markt":     ["EURUSD", "EURUSD", "GBPUSD", "EURUSD", "EURUSD"],
        "vulling":   ["gevuld", "gevuld", "gevuld", "niet gevuld", "gevuld"],
        "r_net":     [1.0, -1.0, 2.0, np.nan, 0.5],
        "fill_time": [T("2025-01-02 10:00"), T("2025-01-02 11:00"), T("2025-01-02 11:00"), pd.NaT, T("2025-01-02 12:00")],
        "exit_time": [T("2025-01-02 12:00"), T("2025-01-02 11:30"), T("2025-01-02 13:00"), pd.NaT, T("2025-01-02 14:00")],
    })
    out = one_at_a_time(df)
    # rij 1 valt weg (EURUSD nog open tot 12:00), rij 2 blijft (andere markt), rij 3 niet gevuld,
    # rij 4 vult om 12:00 = net gesloten → telt
    assert list(out.index) == [0, 2, 4]


def test_t_geclusterd_per_week():
    x = np.array([1.0, 1.0, -1.0, 3.0]); w = np.array([1, 1, 2, 2])
    # gemiddelde 1; week 1: (0+0)=0 ; week 2: (−2+2)=0 → se 0 → nan
    assert np.isnan(clustered_t(x, w))
    x = np.array([2.0, 1.0, 0.0]); w = np.array([1, 1, 2])
    # gem. 1; week 1: 1 + 0 = 1 ; week 2: −1 → se = √2 / 3 ; t = 1 / 0,4714 = 2,1213
    assert abs(clustered_t(x, w) - 3 / np.sqrt(2)) < 1e-9


def test_grootste_daling():
    # cumulatief: 10, 4, 7, −3, 5 → top 10, dal −3 → daling 13
    assert max_drawdown([10, -6, 3, -10, 8]) == 13
    assert max_drawdown([-5, 2]) == 5          # meteen verlies telt vanaf 0


def test_dollars_extra_markten():
    df = pd.DataFrame({"markt": ["XAGUSD", "US500"], "pips": [20.0, -15.0], "r_net": [1.0, -1.0]})
    # zilver: 20 pips (0,20 $) × 50 $ × 0,02 lot = 20 $ ; US500: −15 punten × 1 $ × 1 lot = −15 $
    assert np.allclose(usd(df, {"XAGUSD": 0.02, "US500": 1.0}), [20.0, -15.0])
