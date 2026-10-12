"""Export van de dashboard-data: codes, schaal en ontbrekende waarden moeten exact terug te lezen zijn."""
import numpy as np
import pandas as pd
import pytest

from scripts.dashboard_export import MISSING, NUM, ORDER, encode, prepare


def _row(**kw):
    base = {c: v[0] for c, v in ORDER.items()}
    base.update({"r_net": 1.234, "r_free": 1.5, "r_placebo": -1.0, "r_placebo_free": -0.9, "pips": 12.34,
                 "risk_pips": 10.0, "risk_pips_free": 9.9, "jaar": 2018, "week": 2500,
                 "t_sig": pd.Timestamp("2018-03-05 10:15"), "fill_time": pd.Timestamp("2018-03-05 10:45"),
                 "exit_time": pd.Timestamp("2018-03-05 13:00"), "risk_plan": 0.0010})
    base.update(kw)
    return base


def test_codes_en_schaal_terug_te_lezen():
    df = pd.DataFrame([_row(), _row(markt="XAUUSD", breuk="CHoCH", uur="17", r_net=-1.0004, pips=-5.06)])
    body = encode(df)
    c = body["cols"]
    assert [ORDER["markt"][i] for i in c["markt"]] == ["EURUSD", "XAUUSD"]
    assert [ORDER["breuk"][i] for i in c["breuk"]] == ["geen", "CHoCH"]
    assert [ORDER["uur"][i] for i in c["uur"]] == ["0", "17"]
    # R × 1000 en pips × 10, afgerond
    assert c["r_net"] == [1234, -1000]
    assert c["pips"] == [123, -51]
    assert np.allclose(np.array(c["r_net"]) / NUM["r_net"], [1.234, -1.0], atol=5e-4)
    # tijd in minuten sinds 1970
    assert c["ts"][0] == int(pd.Timestamp("2018-03-05 10:15").value // 60_000_000_000)
    assert c["exit_time"][0] - c["fill_time"][0] == 135          # 10:45 → 13:00
    assert c["risk_pips"] == [100, 100]


def test_ontbrekend_wordt_missing():
    df = pd.DataFrame([_row(r_net=np.nan, r_placebo=np.nan, exit_time=pd.NaT)])
    c = encode(df)["cols"]
    assert c["r_net"] == [MISSING] and c["r_placebo"] == [MISSING] and c["exit_time"] == [MISSING]


def test_onbekende_waarde_geeft_fout():
    df = pd.DataFrame([_row(breuk="iets anders")])
    with pytest.raises(ValueError):
        encode(df)


def test_kostenklasse():
    # EURUSD: kosten = min_spread + 2 × slippage + commissie (in prijs); risico 0,0010 = 10 pips
    rows = [_row(risk_plan=0.0100), _row(risk_plan=0.0010), _row(risk_plan=0.0001), _row(risk_plan=0.0)]
    for r in rows:
        r.update({"vulling": "gevuld", "uitkomst": "TP"})
    out = prepare(pd.DataFrame(rows))
    assert list(out["kosten"]) == ["<0,1R", "0,1–0,2R", ">0,2R", "onbekend"]
