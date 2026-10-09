# KATSU — resultaat bouwsteen 3 (FVG-retest met de hogere timeframes mee, spec v0.3)

Datum: 9 oktober 2026 · Periode: **2020–2024 (in-sample)** · Out-of-sample 2025–2026: **niet bekeken**.
Regels: spec v0.3 (trades lopen tot SL/TP, swap, rollover-spread, kostenplafond 0,2R, dagstop op gesloten trades).
Code: `katsu/fvg.py`, `scripts/backtest.py … fvg` · 84 tests, alle groen.

## Uitslag in één zin
**Formeel faalt bouwsteen 3**: geen enkele variant is op **beide** markten positief (keuzeregel). Maar voor het eerst is er een duidelijk signaal vóór kosten: **FVG op M15 met H1 + H4 mee (T+)** ligt op beide markten ruim boven willekeurig instappen.

## Resultaten bij basis-slippage (gemiddelde R per trade)

| Variant | Markt | Trades | Winrate | **Netto R** | PF | Zonder kosten | Placebo zonder kosten |
|---|---|---|---|---|---|---|---|
| M15-A-T+ | Goud | 336 | 38% | **+0,06** | 1,09 | **+0,18** | +0,06 |
| M15-A-T+ | EURUSD | 477 | 36% | **−0,04** | 0,95 | **+0,12** | 0,00 |
| M15-A-T0 | Goud | 948 | 36% | +0,01 | 1,02 | +0,11 | +0,03 |
| M15-A-T0 | EURUSD | 1277 | 33% | −0,11 | 0,86 | +0,04 | −0,05 |
| M15-B-T+ | Goud | 221 | 33% | −0,08 | 0,89 | +0,03 | +0,06 |
| M15-B-T+ | EURUSD | 354 | 36% | −0,05 | 0,93 | +0,10 | −0,04 |
| M15-B-T0 | Goud | 692 | 32% | −0,11 | 0,86 | −0,01 | +0,03 |
| M15-B-T0 | EURUSD | 1009 | 33% | −0,13 | 0,82 | +0,02 | −0,05 |
| M5-A-T+ | Goud | 398 | 27% | −0,28 | 0,65 | −0,19 | −0,06 |
| M5-A-T+ | EURUSD | 668 | 28% | −0,28 | 0,66 | −0,13 | +0,04 |
| M5-A-T0 | Goud | 956 | 34% | −0,07 | 0,91 | +0,02 | −0,05 |
| M5-A-T0 | EURUSD | 1660 | 32% | −0,16 | 0,79 | −0,01 | +0,02 |
| M5-B-T+ | Goud | 243 | 28% | −0,27 | 0,67 | −0,18 | −0,02 |
| M5-B-T+ | EURUSD | 436 | 30% | −0,22 | 0,72 | −0,11 | +0,05 |
| M5-B-T0 | Goud | 619 | 34% | −0,05 | 0,93 | +0,04 | −0,03 |
| M5-B-T0 | EURUSD | 1200 | 31% | −0,19 | 0,76 | −0,04 | +0,06 |

Lage slippage: goud M15-A-T+ +0,08R, EURUSD −0,03R. Hoge slippage: goud +0,03R, EURUSD −0,05R.

## Wat we leren
1. **De trendfilter van Gitchi werkt op M15.** Met H1 + H4 mee (T+) is het resultaat vóór kosten beter dan met alleen H1 (T0), op beide markten: goud +0,18 tegenover +0,11R, EURUSD +0,12 tegenover +0,04R. En duidelijk beter dan de placebo.
2. **Op M5 werkt het omgekeerd.** M15 + H1 als filter maakt M5 slechter (−0,19 en −0,13R vóór kosten). Hoe kleiner de timeframe, hoe meer ruis.
3. **Instap op de rand (A) is beter dan op het midden (B).** Bij B wordt minder vaak gevuld; waarschijnlijk worden net de sterke bewegingen (die niet diep terugkomen) gemist.
4. **De kosten blijven de spelbreker.** Op M15-A-T+ kosten spread, slippage, commissie en swap samen ~0,11–0,15R per trade; dat haalt een voorsprong van +0,12R op EURUSD onderuit.
5. **Stabiliteit is zwak.** Goud M15-A-T+ per jaar: +0,30 · +0,06 · +0,23 · −0,06 · −0,17R. EURUSD: alleen 2020 positief. De laatste twee jaren zijn op beide markten negatief.
6. **Statistisch:** +0,18R op 336 trades is ongeveer 2 standaardfouten boven nul. Dat is een aanwijzing, geen bewijs, zeker omdat we intussen 24 varianten op 2 markten (48 combinaties) bekeken hebben.

## Wat we NIET doen
- Achteraf de keuzeregel aanpassen (bv. "alleen goud") omdat goud toevallig positief is. Dat is precies het bijschaven dat GAMAN de das omdeed. De regel lag vast vóór de test.

## Mogelijke vervolgstap (vraag voor Gitchi, nog niet beslist)
Het patroon "hoe hoger de timeframe, hoe beter de FVG met de trend mee" past bij Gitchi's eerder genoteerde idee (vóór deze resultaten): **grote FVG's op een hogere timeframe met H4/D1 mee, meerdere dagen open.** Op een hogere timeframe zijn de kosten per trade in R ook veel kleiner. Dat zou een nieuwe spec zijn (bv. FVG op H1 met H4 + D1 mee), met dezelfde regels en keuzeregel, en pas daarna de eenmalige eindtest.
