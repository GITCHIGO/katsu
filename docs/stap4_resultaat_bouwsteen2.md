# KATSU — resultaat bouwsteen 2 (BOS-continuatie, spec v0.2)

Datum: 9 oktober 2026 · Periode: **2020–2024 (in-sample)** · Out-of-sample 2025–2026: **niet bekeken**.
Code: `katsu/bos.py`, `katsu/backtest.py`, `scripts/backtest.py … bos` · 67 tests, alle groen.
Regels: spec v0.2 inclusief kostenplafond 0,2R (toegevoegd vóór de backtest, na de controlegrafieken).

## Uitslag in één zin
**Bouwsteen 2 faalt.** Alle 8 varianten zijn negatief op beide markten, ook bij de laagste slippage (beste: goud M5-A-L1 −0,02R). Volgens de keuzeregel: geen eindtest, door naar bouwsteen 3 (FVG-retest).

## Resultaten bij basis-slippage, met de diagnoses (gemiddelde R per trade)

| Variant | Markt | Trades | Winrate | **Netto R** | PF | Zonder kosten | Placebo met kosten | Placebo zonder kosten |
|---|---|---|---|---|---|---|---|---|
| M5-A-L1 | Goud | 680 | 37% | **−0,04** | 0,93 | +0,04 | −0,19 | −0,04 |
| M5-A-L1 | EURUSD | 965 | 35% | **−0,14** | 0,78 | −0,05 | −0,11 | 0,00 |
| M5-A-L3 | Goud | 647 | 32% | **−0,18** | 0,71 | −0,10 | −0,14 | −0,03 |
| M5-A-L3 | EURUSD | 813 | 35% | **−0,16** | 0,74 | −0,07 | −0,08 | 0,00 |
| M5-B-L1 | Goud | 1084 | 36% | **−0,08** | 0,88 | +0,08 | −0,13 | −0,05 |
| M5-B-L1 | EURUSD | 1364 | 35% | **−0,14** | 0,78 | −0,01 | −0,08 | +0,01 |
| M5-B-L3 | Goud | 896 | 33% | **−0,14** | 0,76 | −0,03 | −0,14 | −0,04 |
| M5-B-L3 | EURUSD | 1027 | 35% | **−0,17** | 0,73 | −0,06 | −0,06 | +0,01 |
| M15-A-L1 | Goud | 517 | 33% | **−0,17** | 0,71 | −0,10 | −0,11 | −0,01 |
| M15-A-L1 | EURUSD | 666 | 34% | **−0,19** | 0,70 | −0,10 | −0,08 | +0,01 |
| M15-A-L3 | Goud | 406 | 32% | **−0,18** | 0,69 | −0,12 | −0,07 | +0,02 |
| M15-A-L3 | EURUSD | 437 | 36% | **−0,17** | 0,72 | −0,11 | −0,09 | −0,02 |
| M15-B-L1 | Goud | 761 | 34% | **−0,15** | 0,74 | −0,04 | −0,07 | +0,01 |
| M15-B-L1 | EURUSD | 889 | 34% | **−0,18** | 0,70 | −0,09 | −0,08 | 0,00 |
| M15-B-L3 | Goud | 526 | 36% | **−0,14** | 0,74 | −0,08 | −0,07 | +0,02 |
| M15-B-L3 | EURUSD | 541 | 34% | **−0,16** | 0,72 | −0,09 | −0,07 | +0,01 |

Max drawdown over 5 jaar: 54R tot 209R. Bij 1% risico per trade is dat onleefbaar.

## Wat de diagnoses zeggen
1. **Het kostenplafond werkte zoals bedoeld.** De kosten per trade (spread + slippage + commissie) zijn nu ~0,05–0,16R in plaats van tot 0,33R. Daarom zit de placebo met kosten nu rond −0,07 à −0,19R in plaats van −0,21R.
2. **Zonder kosten is BOS-continuatie meestal sléchter dan willekeurig instappen.** In 13 van de 16 gevallen ligt "zonder kosten" onder "placebo zonder kosten". Een breuk van een top op M5/M15 loopt dus eerder vaker terug dan door. Dat is een consistente bevinding, geen toeval in één variant.
3. **Uitzondering: goud M5 met L=1** (A: +0,04R, B: +0,08R zonder kosten, tegenover −0,04/−0,05R voor de placebo). Er zit daar mogelijk een kleine voorsprong vóór kosten, maar na kosten blijft het negatief (−0,04 en −0,08R); variant A was in 4 van de 5 jaren negatief, variant B in alle 5. Geen kandidaat.
4. **Stresstest:** de keuze welke setups genomen worden ligt vast op de basis-slippage; de stresstest maakt alleen de uitvoering slechter (gecorrigeerd en getest vóór de definitieve run).

## Context (alleen gemeten, geen filter)
- Sessie: Azië −0,21R, Londen −0,14R, Londen+NY −0,11R, NY −0,12R. Alle negatief.
- H4-trend mee −0,12R, tegen −0,16R. Iets beter, maar negatief.
- Ruim een derde van alle BOS-setups viel weg door het kostenplafond (krappe SL in een rustige markt). Precies wat Gitchi op de grafieken zag.

## Wat we hiervan leren
- Bouwsteen 1 (ommekeer na sweep) ≈ willekeurig. Bouwsteen 2 (meegaan na een breuk) ≈ iets slechter dan willekeurig. Op M5/M15 binnen één handelsdag hebben de twee basispatronen van "smart money concepts" op goud en EURUSD 2020–2024 geen edge.
- De kosten zijn op deze timeframes zwaar: zelfs met het plafond kost een trade gemiddeld ~0,1R. Een strategie moet vóór kosten al +0,2R halen om aan +0,10R netto te komen.

## Volgende stap
Bouwsteen 3: FVG-retest (spec v0.1 §9). Eerst spec, dan grafieken, dan backtest.


## Herhaling 9 okt 2026: zonder de 23:00-regel (trades lopen tot SL of TP)
Zelfde setups en regels (met kostenplafond), maar geen sluiting om 23:00; met swap per nacht, verbrede rollover-spread en de gecorrigeerde dagstop (alleen gesloten trades tellen).

| Variant | Goud oud → nieuw | EURUSD oud → nieuw |
|---|---|---|
| M5-A-L1 | −0,04 → −0,04 | −0,14 → −0,26 |
| M5-A-L3 | −0,18 → −0,20 | −0,16 → −0,26 |
| M5-B-L1 | −0,08 → −0,11 | −0,14 → −0,20 |
| M5-B-L3 | −0,14 → −0,16 | −0,17 → −0,22 |
| M15-A-L1 | −0,17 → −0,21 | −0,19 → −0,29 |
| M15-A-L3 | −0,18 → −0,19 | −0,17 → −0,20 |
| M15-B-L1 | −0,15 → −0,16 | −0,18 → −0,25 |
| M15-B-L3 | −0,14 → −0,17 | −0,16 → −0,14 |

- **Uitslag blijft: faalt.** Beste bij lage slippage −0,02R, bij hoge −0,07R.
- 29% van de trades bleef minstens één nacht open (90% hoogstens 1 nacht, langste 48 nachten). Swap kostte gemiddeld 0,02R per trade.
- Zonder kosten: tussen −0,16R en +0,08R; in 13 van de 16 gevallen nog altijd onder de placebo zonder kosten. Breuken lopen vaker terug dan door, ook als je ze langer laat lopen.
