"""Poort van laag 1 (plan §9): elke voorwaarde apart gecontroleerd op een verzonnen register."""
import numpy as np
import pandas as pd

from scripts.ronde1_poort import gate


def base_row(**kw):
    r = dict(markt="XAUUSD", tf="H1", familie="BOS", L=3, variant="alle", n=500, R21=0.30, basis_R21=0.0,
             edge=0.30, se=0.08, t=3.75, R11=0.1, edge_R11=0.1, fwd12_atr=0.1, kosten_R=0.10,
             edge_voor_2020=0.3, edge_2020_24=0.3, jaren_zelfde_teken=0.8, aantal_jaren=8)
    r.update(kw)
    return r


def buren(**kw):
    # L=1 en L=5 met hetzelfde teken als buren
    return [base_row(L=1, t=0.5, edge=0.05), base_row(L=5, t=0.5, edge=0.05), base_row(**kw)]


def run(rows):
    return gate(pd.DataFrame(rows)).iloc[-1]


def test_alles_goed_gaat_door():
    assert bool(run(buren()).poort)


def test_te_weinig_gebeurtenissen():
    assert not bool(run(buren(n=99)).poort)


def test_alleen_een_markt_vraagt_t_35():
    assert not bool(run(buren(t=3.2, edge=0.3)).poort)          # geen steun andere markt: 3,5 nodig
    rows = buren(t=3.2) + [base_row(markt="EURUSD", t=1.2, edge=0.1)]
    assert bool(gate(pd.DataFrame(rows)).iloc[2].poort)            # andere markt mee: 3,0 volstaat


def test_helften_moeten_zelfde_teken():
    assert not bool(run(buren(edge_2020_24=-0.1)).poort)


def test_meerderheid_jaren():
    assert not bool(run(buren(jaren_zelfde_teken=0.5)).poort)


def test_buren_l_moeten_mee():
    rows = [base_row(L=1, edge=-0.1, t=-1), base_row(L=5, edge=-0.1, t=-1), base_row()]
    assert not bool(gate(pd.DataFrame(rows)).iloc[2].poort)


def test_na_kosten_te_weinig_over():
    assert not bool(run(buren(R21=0.12, kosten_R=0.10)).poort)    # 0,02 < 0,05


def test_negatief_effect_gebruikt_omgekeerde_trade():
    rows = [base_row(L=1, edge=-0.05, t=-0.5), base_row(L=5, edge=-0.05, t=-0.5),
            base_row(edge=-0.3, t=-3.8, R21=-0.3, R11=-0.25, edge_voor_2020=-0.3, edge_2020_24=-0.3)]
    r = gate(pd.DataFrame(rows)).iloc[2]
    assert r.richting == "omgekeerd"
    assert r.netto_na_kosten == 0.25 - 0.10          # omgekeerde trade: −R11 − kosten
    assert bool(r.poort)
