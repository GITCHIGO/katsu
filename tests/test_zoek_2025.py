"""Spec v0.9 — handberekende controles van het zoeken (één tegelijk, greedy stap, geen 2026 in de keuze)."""
import numpy as np
import pandas as pd

from scripts import zoek_2025 as Z


def toy():
    # 200 trades op EURUSD in 2025; kenmerk 'sessie' 0 = goed (+1R), 1 = slecht (−1R).
    rows = []
    for i in range(200):
        good = i % 2 == 0
        rows.append({"markt": 0, "soort": 0, "vulling": 0, "sessie": 0 if good else 1, "week": i // 4,
                     "fill_time": float(i * 100), "exit_time": float(i * 100 + 50),
                     "r_net": 1.0 + (i % 7) * 0.01 if good else -1.0, "r_free": 0.0, "r_placebo_free": 0.0,
                     "periode": "2025"})
    order = {"markt": ["EURUSD", "GBPUSD", "XAUUSD"], "soort": ["FVG"], "vulling": ["gevuld"],
             "sessie": ["Londen", "Azië"], "uitkomst": []}
    return pd.DataFrame(rows), order


def test_een_tegelijk_slaat_overlappende_trades_over():
    df = pd.DataFrame({"markt": [0, 0, 0, 1], "vulling": [0, 0, 0, 0], "r_net": [1.0, 1.0, 1.0, 1.0],
                       "fill_time": [0.0, 10.0, 60.0, 10.0], "exit_time": [50.0, 70.0, 80.0, 20.0]})
    kept = Z.one_at_a_time(df)
    assert kept["fill_time"].tolist() == [0.0, 60.0, 10.0]   # tweede EURUSD-trade valt weg; GBPUSD apart


def test_greedy_zet_de_slechte_chip_uit():
    df, order = toy()
    counter = [0]
    allowed, steps, best = Z.search(df, order, "FVG", counter)
    assert allowed["sessie"] == {0}                          # Azië (alleen verliezers) uit
    assert best["n"] == 100 and best["gem"] > 1.0
    assert counter[0] >= 2


def test_2026_beinvloedt_de_keuze_niet():
    df, order = toy()
    d26 = df.copy(); d26["periode"] = "2026"; d26["r_net"] = -d26["r_net"]   # 2026 precies omgekeerd
    a1, _, _ = Z.search(df, order, "FVG", [0])
    a2, _, _ = Z.search(pd.concat([df, d26], ignore_index=True), order, "FVG", [0])
    assert a1 == a2
