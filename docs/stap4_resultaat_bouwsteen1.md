# KATSU — stap 4: resultaat bouwsteen 1 (sweep + CHoCH met de H1-trend)

Datum: 9 oktober 2026 · Periode: **2020–2024 (in-sample)** · Out-of-sample 2025–2026: **niet bekeken**.
Code: `katsu/backtest.py`, `scripts/backtest.py` · Tests: `tests/test_backtest.py` (50 tests in totaal, alle groen).

## Uitslag in één zin
**Bouwsteen 1 faalt.** Geen enkele van de 8 varianten is positief, op geen van beide markten, zelfs niet bij de laagste slippage. Volgens de vooraf vastgelegde keuzeregel (spec §8): geen eindtest, door naar bouwsteen 2 (BOS-continuatie).

## Resultaten bij basis-slippage (na alle kosten)

| Variant | Goud trades | Goud gem. R | Goud PF | EURUSD trades | EURUSD gem. R | EURUSD PF |
|---|---|---|---|---|---|---|
| M5-A-L1 | 901 | −0,21 | 0,71 | 835 | −0,28 | 0,63 |
| M5-A-L3 | 270 | −0,10 | 0,84 | 237 | −0,18 | 0,75 |
| M5-B-L1 | 392 | −0,28 | 0,67 | 368 | −0,45 | 0,51 |
| M5-B-L3 | 104 | −0,36 | 0,56 | 95 | −0,39 | 0,56 |
| M15-A-L1 | 353 | −0,18 | 0,71 | 301 | −0,26 | 0,61 |
| M15-A-L3 | 111 | −0,23 | 0,64 | 89 | −0,18 | 0,72 |
| M15-B-L1 | 146 | −0,07 | 0,90 | 129 | −0,29 | 0,64 |
| M15-B-L3 | 57 | −0,25 | 0,65 | 46 | −0,08 | 0,89 |

Bij lage slippage ($0,10 / 0,1 pip) blijft alles negatief (beste: goud M15-B-L1 −0,02R, EURUSD M15-B-L3 −0,06R).

## Waarom: er is geen voorsprong, ook niet vóór kosten
1. **Zonder enige kost** (geen spread, geen slippage, geen commissie) liggen dezelfde setups rond nul: tussen −0,20R en +0,11R per variant; de grootste groepen (M5-A-L1, ~900 trades per markt) −0,01R (goud) en −0,07R (EURUSD).
2. **Placebo-test:** 3.000 willekeurige instapmomenten met een willekeurige richting, zelfde SL-grootte en dezelfde uitvoeringsmotor:
   - zonder kosten: goud −0,06R, EURUSD −0,01R
   - met basiskosten: goud −0,21R, EURUSD −0,21R
   KATSU M5-A-L1 haalt goud −0,21R en EURUSD −0,28R. **Niet beter dan een muntworp.**
3. De kosten zijn dus niet de oorzaak; ze maken een nul-voorsprong alleen zichtbaar negatief.
4. Het motorblok werkt zoals verwacht: de placebo zonder kosten komt rond nul uit, en meer slippage geeft altijd een slechter resultaat (ook getest).

## Per jaar (voorbeeld M5-A-L3, basis)
Alleen 2020 was positief (goud +0,08R, EURUSD +0,29R); 2021–2024 alle vier negatief op beide markten. Geen enkele periode waarin het structureel werkte.

## Context (alleen gemeten, geen filter — §7)
Over alle varianten samen bij basis-slippage (overlappende trades tellen meerdere keren mee, dus alleen als richting):
- Long −0,24R, short −0,25R: geen verschil.
- Ochtend 06–12u −0,23R, rest −0,25R: geen verschil.
- Sessie: Azië −0,37R, Londen −0,18R, Londen+NY −0,08R, NY −0,27R. Ook de beste sessie is negatief.
- **H4 en D1 in dezelfde richting als de trade:** −0,29R; beide tegen: −0,24R. De trend op hogere timeframes helpt **niet**.
- Met een FVG in de CHoCH-beweging −0,21R, zonder −0,27R.

Niets hiervan wordt nu een filter. Een filter mag alleen via een nieuwe spec, met een nieuwe test, en een groep die nog altijd negatief is kan sowieso niet "gered" worden door te filteren.

## Wat we hiervan leren
- "Sweep + CHoCH" zoals de meeste ICT/SMC-uitleg het beschrijft, is op zichzelf op goud en EURUSD 2020–2024 **geen** voorsprong.
- De 70% winrate die je bij ForexDetective zag, komt dus niet uit dit patroon alleen. Dat past bij wat we eerder vonden: zijn hoge winrate kwam vooral uit zijn voorsprong in timing, niet uit het patroon zelf.
- Dit is een goed resultaat voor het proces: we weten het nu met 5 jaar data en echte kosten, in plaats van na maanden live verlies.

## Volgende stap
Bouwsteen 2: **BOS-continuatie** (spec §9). Eerst de spec-tekst uitwerken en laten goedkeuren, dan bouwen, controlegrafieken, en dezelfde backtest.


## Herhaling 9 okt 2026: zonder de 23:00-regel (trades lopen tot SL of TP)
Zelfde setups en regels, maar geen sluiting om 23:00; met swap per nacht, verbrede rollover-spread en de gecorrigeerde dagstop (alleen gesloten trades tellen).

| Variant | Goud oud → nieuw | EURUSD oud → nieuw |
|---|---|---|
| M5-A-L1 | −0,21 → −0,23 | −0,28 → −0,34 |
| M5-A-L3 | −0,10 → −0,14 | −0,18 → −0,26 |
| M5-B-L1 | −0,28 → −0,30 | −0,45 → −0,49 |
| M5-B-L3 | −0,36 → −0,39 | −0,39 → −0,40 |
| M15-A-L1 | −0,18 → −0,16 | −0,26 → −0,28 |
| M15-A-L3 | −0,23 → −0,29 | −0,18 → −0,18 |
| M15-B-L1 | −0,07 → −0,07 | −0,29 → −0,32 |
| M15-B-L3 | −0,25 → −0,36 | −0,08 → −0,09 |

- **Uitslag blijft: faalt.** Beste bij lage slippage −0,03R, bij hoge −0,12R. Geen kandidaat voor de keuzeregel.
- 16% van de trades bleef minstens één nacht open (90% hoogstens 1 nacht, langste 14 nachten). Swap kostte gemiddeld 0,02R per trade.
- Zonder kosten: tussen −0,22R en +0,14R, rond de placebo (−0,09 tot +0,04R). Geen voorsprong.
