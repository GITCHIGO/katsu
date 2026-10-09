"""
Bouwsteen 3: 12 willekeurige FVG-setups uit 2020–2024 (in-sample) als controlegrafieken.
6 goud + 6 EURUSD, telkens 3 op M5 en 3 op M15, trendfilter T+ (de twee timeframes erboven mee).
Getekend met variant A (limiet op de rand); de uitkomst van variant B (midden) staat in de titel.
Gebruik: python -m scripts.controle_fvg <xau_m1.pkl> <eur_m1.pkl> <uit.pdf>
"""
import random
import sys

import pandas as pd

from katsu.backtest import in_sample
from katsu.data import resample
from katsu.execution import EURUSD, XAUUSD, M1, simulate
from katsu.fvg import FILTER_TFS, detect_fvg, make_fvg_plan
from katsu.plotting import save_fvg_pdf
from katsu.signals import multi_tf_trend
from katsu.structure import atr

INTRO = """KATSU — controle bouwsteen 3: FVG-retest met de hogere timeframes mee

Per pagina één setup. Tijden in Brusselse tijd. Alle setups komen uit 2020–2024.
Idee (long): drie candles waarbij de low van candle 3 boven de high van candle 1 blijft
(een gat = FVG), terwijl de twee timeframes erboven stijgen (M5: M15+H1, M15: H1+H4).
We kopen bij de terugkeer naar de bovenkant van het gat.
  blauw vlak           = de FVG (het gat)
  oranje stippellijn   = laagste low van de drie FVG-candles = basis voor de SL
  zwart / paars / turquoise (streep-punt) = entry / SL / TP van variant A (rand)
  Geen zwarte lijn = de koers kwam binnen 12 candles niet terug, of de SL was te krap.
Trades lopen tot SL of TP (ook over nacht).

Vraag per pagina: is dit voor jou een echte FVG met de trend mee?
Noteer de nummers waar je twijfelt of nee zegt, met een woord uitleg.
Beoordeel de SETUP, niet het resultaat."""


def main(xau_path, eur_path, out):
    rnd = random.Random(20261011)
    items = []
    n = 1
    for name, path, ins in (("XAUUSD", xau_path, XAUUSD), ("EURUSD", eur_path, EURUSD)):
        m1 = in_sample(pd.read_pickle(path))
        ctx = multi_tf_trend(m1)
        d = M1(m1, ins)
        for tf in ("5min", "15min"):
            bars = resample(m1, tf); a = atr(bars, 14)
            for f in ("T0", "T+"):
                print("aantal FVG-setups 2020–2024:", name, tf, f, len(detect_fvg(bars, tf, ctx, f)))
            setups = detect_fvg(bars, tf, ctx, "T+")
            # alleen setups die echt een trade worden in variant A (anders is er niets te beoordelen)
            longs, shorts = [], []
            pool = list(setups); rnd.shuffle(pool)
            for s in pool:
                ta = simulate(make_fvg_plan(s, tf, a, "A", ins), d, ins)
                if ta.status != "gesloten":
                    continue
                (longs if s.direction == "LONG" else shorts).append((s, ta))
                if len(longs) >= 2 and len(shorts) >= 2:
                    break
            pick = longs[:2] + shorts[:1] if tf == "5min" else longs[:1] + shorts[:2]
            for s, ta in pick:
                tb = simulate(make_fvg_plan(s, tf, a, "B", ins), d, ins).as_dict()
                ta = ta.as_dict()
                t_be = (s.signal_time - pd.Timedelta(hours=1)).strftime("%a %d/%m/%Y %H:%M")
                ub = tb["exit_reason"] or tb["status"]
                tfn = "M5" if tf == "5min" else "M15"
                tr_ctx = "  ".join(f"{k}:{v}" for k, v in ctx(s.signal_time).items())
                title = (f"#{n}  {name}  {tfn}  {s.direction}  signaal {t_be} (BE)  filter {'+'.join(FILTER_TFS[(tf, 'T+')])}  "
                         f"A (rand): {ta['exit_reason']} ({ta['nights']} nacht)  ·  B (midden): {ub}\ntrend  {tr_ctx}")
                items.append((s, bars, ta, title)); n += 1
    save_fvg_pdf(items, out, INTRO)
    print(f"{len(items)} setups -> {out}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
