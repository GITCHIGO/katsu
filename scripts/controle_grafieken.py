"""
Stap 3: 12 willekeurige setups uit 2020–2024 (in-sample) als controlegrafieken.
6 goud + 6 EURUSD, telkens 3 op M5 en 3 op M15, L=3, variant A, basis-slippage.
Gebruik: python scripts/controle_grafieken.py <xau_m1.pkl> <eur_m1.pkl> <uit.pdf>
"""
import random
import sys

import pandas as pd

from katsu.data import resample
from katsu.execution import EURUSD, XAUUSD, M1, make_plan, simulate
from katsu.plotting import save_setups_pdf
from katsu.signals import detect_setups, h1_trend_lookup
from katsu.structure import atr

INTRO = """KATSU — controle stap 3

Per pagina één setup (sweep + CHoCH met de trend). Tijden in Brusselse tijd.
  blauwe stippellijn   = geveegde swing (het liquiditeitsniveau)
  blauw driehoekje     = sweep-candle (wick door het niveau, close terug)
  oranje stippellijn   = swing die de CHoCH moest breken
  oranje cirkel        = CHoCH-close (de candle die erboven/onder sluit)
  zwart / paars / turquoise (streep-punt) = entry / SL / TP (variant A: marktorder op de volgende candle)

Vraag per pagina: is dit voor jou een echte sweep en een echte CHoCH?
Noteer de nummers waar je twijfelt of nee zegt, met een woord uitleg.
Uitkomsten staan erbij, maar beoordeel de SETUP, niet het resultaat.
Alle setups komen uit 2020–2024 (de eindtest 2025–2026 blijft onaangeroerd)."""


def main(xau_path, eur_path, out):
    rnd = random.Random(20261009)
    items = []
    n = 1
    for name, path, ins in (("XAUUSD", xau_path, XAUUSD), ("EURUSD", eur_path, EURUSD)):
        m1 = pd.read_pickle(path); m1 = m1[m1.index < "2025-01-01"]
        trend = h1_trend_lookup(resample(m1, "1h"), 3)
        d = M1(m1, ins)
        for tf in ("5min", "15min"):
            bars = resample(m1, tf); a = atr(bars, 14)
            setups = detect_setups(bars, tf, trend, L=3)
            longs = [s for s in setups if s.direction == "LONG"]
            shorts = [s for s in setups if s.direction != "LONG"]
            pick = rnd.sample(longs, 2) + rnd.sample(shorts, 1) if tf == "5min" else rnd.sample(longs, 1) + rnd.sample(shorts, 2)
            for s in pick:
                tr = simulate(make_plan(s, bars, tf, a, "A", ins), d, ins).as_dict()
                t_be = (s.signal_time - pd.Timedelta(hours=1)).strftime("%a %d/%m/%Y %H:%M")
                uit = tr["exit_reason"] or tr["status"]
                tfn = "M5" if tf == "5min" else "M15"
                title = f"#{n}  {name}  {tfn}  {s.direction}  signaal {t_be} (BE)  uitkomst: {uit}"
                items.append((s, bars, tr, title)); n += 1
    save_setups_pdf(items, out, INTRO)
    print(f"{len(items)} setups -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
