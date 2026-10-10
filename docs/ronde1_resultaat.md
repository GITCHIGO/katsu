# KATSU — laag 1, ronde 1: resultaat signaalonderzoek

Datum: 11 oktober 2026 · Data: **alleen de verkenningshelft** (FX 2010–2019, metalen/US500 feb 2016–2019, plus oneven maanden 2020–2024). Bevestigingshelft (even maanden 2020–2024) en eindtest (2025–2026): **niet bekeken**.
Opzet: vooraf vastgelegd in `onderzoeksplan_edge.md` §9. Code: `katsu/research.py`, `scripts/ronde1.py`, `scripts/ronde1_poort.py` (111 tests, alle groen). Testregister: `research/register_ronde1.csv`.

## In één zin
**615 combinaties getest, 0 door de poort.** Op H1 en H4 gedragen alle SMC-gebeurtenissen zich zoals toeval; op M15 volgt na een BOS, CHoCH of FVG een kleine maar zeer consistente **terugval** — kleiner dan de kosten.

## Hoe "toeval" eruitziet, en wat we zagen
Als er nergens een edge is, verwacht je bij 615 tests ongeveer 2,3% met t ≥ 2 en 2,3% met t ≤ −2 (samen ~28).

| Timeframe | Tests | t ≥ +2 (beter dan willekeurig) | t ≤ −2 (slechter) | Verwacht bij puur toeval |
|---|---|---|---|---|
| M15 | 205 | 1 | **54** | ~5 en ~5 |
| H1 | 215 | 2 | 6 | ~5 en ~5 |
| H4 | 195 | 2 | 5 | ~4 en ~4 |

- **H1 en H4: niets.** Het aantal "opvallende" resultaten is zelfs iets lager dan wat toeval geeft. BOS, CHoCH, MSS, sweeps (swing, vorige dag/week, Azië-range) en FVG's (vorming, retest, inverse) voorspellen op deze markten de koers niet beter dan een willekeurig moment op hetzelfde uur.
- **M15: een echt, consistent effect, maar de verkeerde kant op.** Na een BOS, CHoCH of FVG loopt de koers gemiddeld ~0,1 ATR terug binnen 4 candles (ook zichtbaar zonder beugel, dus geen meetartefact). Het geldt op EURUSD, GBPUSD, goud en zilver, in 80–100% van de jaren. Maar de kosten op M15 zijn 0,2–0,6R per trade; de omgekeerde trade houdt dus niets over.

## Beste positieve aanwijzingen (geen van alle significant)
| Markt | TF | Gebeurtenis | n | Edge (R) | t | Na kosten |
|---|---|---|---|---|---|---|
| EURUSD | H4 | CHoCH L3, TF+1 mee | 161 | +0,31 | 2,5 | +0,11 |
| EURUSD | H4 | CHoCH L3, displacement | 248 | +0,23 | 2,3 | +0,19 |
| XAUUSD | H1 | BOS L5, displacement | 314 | +0,20 | 2,2 | 0,00 |
| XAUUSD | H1 | swing-sweep L1, TF+1 mee | 1342 | +0,11 | 2,2 | −0,12 |
Bij 615 tests zijn een paar t-waarden rond 2–2,5 precies wat toeval oplevert. De poort vroeg t ≥ 3–3,5, steun van andere markten en van naburige L-waarden; geen enkele haalt dat.

## Kosten per trade in R (1R = 1 ATR, benaderend)
| | M15 | H1 | H4 |
|---|---|---|---|
| EURUSD / GBPUSD | 0,21 | 0,10 | **0,05** |
| XAUUSD | 0,45 | 0,22 | 0,10 |
| US500 | 0,33 | 0,17 | 0,08 |
| XAGUSD | 0,60 | 0,30 | 0,14 |
H4 op FX is het enige terrein waar een kleine edge na kosten iets zou kunnen opleveren.

## Wat dit betekent
1. De bouwstenen uit de ICT/SMC-wereld zijn op 5 markten en 6–10 jaar data **op zichzelf geen edge**. Dat sluit aan bij bouwsteen 1–3.
2. Het M15-signaal uit bouwsteen 3 (FVG + H1/H4) komt in deze brede, eerlijkere meting niet terug; het was waarschijnlijk een toevalstreffer.
3. Het enige robuuste patroon is de korte terugval na een breuk op M15. Dat is bekend gedrag (kortetermijn-mean-reversion), maar te klein voor retail-kosten.

## Mogelijke ronde 2 (nog niet beslist, vraag voor Gitchi)
- **H4/D1 op FX met meer context:** premium/discount, niveaus van vorige week/maand, sessie-opens. Kosten zijn daar het laagst.
- **Exits onderzoeken** op de beste H4-aanwijzingen (MFE/MAE), maar alleen als nieuwe, vooraf vastgelegde test.
- **Andere soorten edges, bekend uit onderzoek** buiten ICT/SMC: trendvolgen op D1 (momentum), carry, seizoens-/dag-van-de-week-effecten, opening-range-breakouts. Die hebben in de literatuur een beter trackrecord dan SMC-patronen.
Elke ronde komt opnieuw in het testregister, zodat het totaal aantal pogingen zichtbaar blijft (nu: 615 in laag 1 + 48 combinaties in bouwsteen 1–3).

## Aanvulling 11 okt 2026: met 1,5RR (wens Gitchi)
Zelfde gebeurtenissen, beugel TP +1,5 ATR / SL −1 ATR (quitte zonder kosten bij 40% winrate). Register: `research/register_ronde1_rr15.csv` (nog eens 615 combinaties in het testregister).
- **0 van 615 door de poort.** t ≥ 2: 3 keer; t ≤ −2: 70 keer, waarvan 61 op M15 (zelfde terugval als bij 2R).
- Winrate per familie: M15 37–40%, H1 38–40%, H4 38–40%. Willekeurige momenten geven gemiddeld hetzelfde (−0,01R).
- Conclusie: de RR verandert de winrate, niet de verwachting. Zonder voorsprong in de instap levert geen enkele RR iets op.
