"""Vooruit-test: data samenvoegen, markt uit bestandsnaam, stopregels."""
import pandas as pd
import pytest

from scripts.vooruit_data import market_of, merge
from scripts.vooruittest import stop_status


def test_markt_uit_bestandsnaam():
    assert market_of("/x/EURUSD_M15_okt.csv") == "EURUSD"
    assert market_of("us500 m15.csv") == "US500"
    with pytest.raises(ValueError):
        market_of("onbekend.csv")


def test_samenvoegen_nieuw_wint_en_gesorteerd():
    i = pd.to_datetime(["2026-10-09 23:30", "2026-10-09 23:45"])
    base = pd.DataFrame({"close": [1.0, 2.0]}, index=i)
    new = pd.DataFrame({"close": [2.5, 3.0]}, index=pd.to_datetime(["2026-10-09 23:45", "2026-10-12 00:00"]))
    out = merge(base, new)
    assert list(out.close) == [1.0, 2.5, 3.0] and out.index.is_monotonic_increasing


def test_stopregels():
    assert stop_status(10, -0.9) == "loopt"                       # te vroeg om te stoppen
    assert stop_status(20, -0.31).startswith("STOP")
    assert stop_status(25, -0.2) == "loopt"
    assert stop_status(40, -0.01).startswith("STOP")
    assert stop_status(150, 0.12).startswith("kandidaat")


def test_samenvatting_winst_en_verlies():
    from scripts.vooruittest import summary
    tr = pd.DataFrame({"markt": ["EURUSD"] * 3, "r_net": [1.5, -1.0, -1.1], "pips": [15.0, -10.0, -11.0],
                       "week": [1, 1, 2], "loopt": [False, False, False]})
    s = summary(tr)
    # 0,10 lot EURUSD = 1 $ per pip: winst 15 $, verlies −21 $, netto −6 $
    assert (s["winst"], s["verlies"]) == (1, 2)
    assert s["winst_usd"] == pytest.approx(15.0) and s["verlies_usd"] == pytest.approx(-21.0) and s["usd"] == pytest.approx(-6.0)
    assert s["winst_R"] == pytest.approx(1.5) and s["verlies_R"] == pytest.approx(-2.1)
