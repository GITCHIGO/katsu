"""
Bouwsteen 2: 12 willekeurige BOS-setups uit 2020–2024 (in-sample) als controlegrafieken.
6 goud + 6 EURUSD, telkens 3 op M5 en 3 op M15, L=3. Getekend met variant A (retest-limiet);
de uitkomst van variant B (marktorder) staat in de titel.
Gebruik: python -m scripts.controle_bos <xau_m1.pkl> <eur_m1.pkl> <uit.pdf>
"""
import random
import sys

import pandas as pd

from katsu.backtest import in_sample
from katsu.bos import detect_bos, make_bos_plan
from katsu.data import resample
from katsu.execution import EURUSD, XAUUSD, M1, simulate
from katsu.plotting import save_bos_pdf
from katsu.signals import h1_trend_lookup, multi_tf_trend
from katsu.structure import atr

INTRO = """KATSU — controle bouwsteen 2: BOS-continuatie

Per pagina één setup. Tijden in Brusselse tijd. Alle setups komen uit 2020–2024.
Idee (long): H1 én M5/M15 maken hogere toppen en hogere bodems; een candle sluit
boven de laatste top (BOS); we kopen bij de terugval naar die oude top.
  oranje stippellijn   = de top (swing high) die gebroken wordt
  oranje cirkel        = BOS-close (de candle die er met de body boven sluit)
  blauwe stippellijn   = laatste hogere bodem (higher low) = basis voor de SL
  zwart / paars / turquoise (streep-punt) = entry / SL / TP van variant A (retest-limiet)
  Geen zwarte lijn = de koers kwam binnen 12 candles niet terug (niet gevuld).

Vraag per pagina: is dit voor jou een echte BOS met de trend mee?
Klopt de top die gebroken wordt, en klopt de bodem voor de SL?
Noteer de nummers waar je twijfelt of nee zegt, met een woord uitleg.
Beoordeel de SETUP, niet het resultaat."""


def main(xau_path, eur_path, out):
    rnd = random.Random(20261010)
    items, counts = [], []
    n = 1
    for name, path, ins in (("XAUUSD", xau_path, XAUUSD), ("EURUSD", eur_path, EURUSD)):
        m1 = in_sample(pd.read_pickle(path))
        trend = h1_trend_lookup(resample(m1, "1h"), 3)
        ctx = multi_tf_trend(m1)
        d = M1(m1, ins)
        for tf in ("5min", "15min"):
            bars = resample(m1, tf); a = atr(bars, 14)
            for L in (1, 3):
                counts.append((name, tf, L, len(detect_bos(bars, tf, trend, L=L))))
            setups = detect_bos(bars, tf, trend, L=3)
            longs = [s for s in setups if s.direction == "LONG"]
            shorts = [s for s in setups if s.direction != "LONG"]
            pick = rnd.sample(longs, 2) + rnd.sample(shorts, 1) if tf == "5min" else \
                rnd.sample(longs, 1) + rnd.sample(shorts, 2)
            for s in pick:
                ta = simulate(make_bos_plan(s, tf, a, "A", ins), d, ins).as_dict()
                tb = simulate(make_bos_plan(s, tf, a, "B", ins), d, ins).as_dict()
                t_be = (s.signal_time - pd.Timedelta(hours=1)).strftime("%a %d/%m/%Y %H:%M")
                ua = ta["exit_reason"] or ta["status"]; ub = tb["exit_reason"] or tb["status"]
                tfn = "M5" if tf == "5min" else "M15"
                tr_ctx = "  ".join(f"{k}:{v}" for k, v in ctx(s.signal_time).items())
                title = (f"#{n}  {name}  {tfn}  {s.direction}  signaal {t_be} (BE)  "
                         f"A (retest): {ua}  ·  B (markt): {ub}\ntrend  {tr_ctx}")
                items.append((s, bars, ta, title)); n += 1
    save_bos_pdf(items, out, INTRO)
    print(f"{len(items)} setups -> {out}")
    for c in counts:
        print("aantal BOS-setups 2020–2024:", c, f"≈ {c[3] / 5:.0f}/jaar")


if __name__ == "__main__":
    main(*sys.argv[1:4])
