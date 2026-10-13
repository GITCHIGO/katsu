# KATSU — resultaat AMD / Power of 3 (13 okt 2026)

Spec: `docs/spec_v0.6.md` (vooraf vastgelegd). Code: `katsu/amd.py` (tests `tests/test_amd.py`).
Script: `scripts/amd_test.py` · register: `research/register_amd.csv`.
Data: verkenning vóór 2025 (FX 2010–19, goud 2016–19, oneven maanden 2020–24) + 2025 – 9 okt 2026.
EURUSD, GBPUSD, XAUUSD · M15 · alle kosten · elke setup apart · even maanden 2020–24 niet aangeraakt.

## Uitslag: 0 van 8 varianten haalt de poort

| Variant | Trades | Win | Gem. R netto | t | Zonder kosten | Placebo z.k. | Vóór 2025 | 2025–26 |
|---|---|---|---|---|---|---|---|---|
| C1-E1-B0 (terug in range, markt) | 7.712 | 28% | −0,28 | −12,5 | +0,06 | +0,02 | −0,28 | −0,28 |
| C1-E1-B1 (+ D1-trend mee) | 2.326 | 28% | −0,26 | −6,5 | +0,10 | +0,09 | −0,27 | −0,25 |
| C1-E2-B0 (terug in range, FVG) | 248 | 31% | −0,09 | −0,8 | −0,02 | +0,15 | −0,06 | −0,19 |
| C1-E2-B1 | 82 | 24% | −0,38 | −2,5 | −0,25 | −0,05 | −0,31 | −0,64 |
| C2-E1-B0 (terug over de open, markt) | 5.179 | 49% | −0,17 | −9,7 | −0,02 | +0,01 | −0,18 | −0,13 |
| C2-E1-B1 | 1.521 | 51% | −0,12 | −3,6 | +0,04 | +0,01 | −0,12 | −0,08 |
| C2-E2-B0 (terug over de open, FVG) | 688 | 34% | −0,14 | −2,4 | −0,01 | +0,00 | −0,12 | −0,24 |
| C2-E2-B1 | 216 | 35% | −0,13 | −1,3 | +0,04 | −0,17 | −0,14 | −0,10 |

Per markt is ook alles negatief, op één dunne uitzondering na (C1-E2-B0 EURUSD +0,03R).

## Waarom (wat de cijfers zeggen)
- **De premisse zelf:** de low van de dag valt op 18,7% van de dagen in het manipulatievenster (NY 00–05), de high
  op 20,1%. Het venster is 5 van de ±24 handelsuren (±21%): de extremen vallen er **niet vaker** dan je zou verwachten.
- **Na een "bevestigde" long (C2) sluit de dag in 52,8% van de gevallen boven de midnight open** (5.155 dagen).
  Omdat de koers op dat moment al boven de open staat, is dat nauwelijks meer dan toeval: geen echte doorzetting.
- **Wachten op bevestiging kost de beweging:** bij C2 met markt-entry ligt de TP (overkant van de Azië-range) mediaan
  maar 0,6R weg. Winrate 49% × 0,6R min kosten = verlies.
- **Vroeg instappen (C1) geeft een krappe SL** (mediaan ±9 pips op EURUSD): kosten ±0,18R per trade. Zonder kosten
  is C1-E1 licht positief (+0,06R), maar nauwelijks beter dan willekeurig op hetzelfde uur (+0,02R), en de kosten
  maken het −0,28R.
- **D1-trend als bias** helpt een beetje (−0,17 → −0,12R bij C2-E1), niet genoeg.
- **2025–26 is niet anders** dan de jaren ervoor.

## Controles
- Handcontrole EURUSD 12-03-2019 (C2-E1-B0, long): Azië-range, midnight open, sweep 07:45, bevestiging 10:30, vulling
  1.12631, SL 1.12508, TP 1.12678 geraakt om 11:00, +0,317R — alles klopt met de candles.
- 11 tests met de hand uitgerekend (sweep, beide bevestigingen, FVG 38,2%, spiegeling short, trendfilter, randgevallen).

## Conclusie
AMD als mechanische regel (deze 8 vooraf gekozen varianten) heeft geen voorsprong op deze markten. Wat de bronnen
zelf zeggen, klopt: het patroon is **beschrijvend** — achteraf past het op bijna elke dag, maar op het moment zelf
onderscheidt het een manipulatie niet van een echte uitbraak. Mogelijke volgende stappen zijn een nieuwe spec
(bv. andere TP-keuze, Asia-range-breedte als filter) — maar dat is zoeken, met dezelfde vangrails als het dashboard.
