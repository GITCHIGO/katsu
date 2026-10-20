# KATSU — resultaat zones (supply & demand / order block, limietorder), 20 okt 2026

Spec: `docs/spec_v0.7.md` (v0.7 en v0.7b, vooraf vastgelegd). Code: `katsu/zones.py` (tests `tests/test_zones.py`),
`scripts/zones_test.py`. Registers: `research/register_zones.csv` (v0.7), `research/register_zones_b.csv` (v0.7b).
Data: **alleen 2025 – okt 2026** (besluit Gitchi). EURUSD en XAUUSD uitgevoerd op **M1**, GBPUSD op M15. Alle kosten.
Cijfers hieronder: één trade tegelijk per markt.

## v0.7 — 0 van 12 door de poort
TP = top van het vertrekbeen + annuleren als die eerst geraakt wordt → 83% van de orders geannuleerd (mechanische
zwakte van de spec, zie §5 van de spec). Wat gevuld werd: alles negatief (M15 −0,22 tot −0,27R; H1 −0,05 tot −0,13R).

## v0.7b — 0 van 12 door de poort (lat t ≥ 2,5)
Order 7 dagen geldig zonder annulering; TP = oude high vlak vóór de vulling, max 2R.

| Variant | Trades | Win | Gem. R | t | Zonder kosten | Placebo z.k. | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| M15 rand | 3.684 | 35% | −0,17 | −6,9 | −0,01 | −0,00 | −0,15 | −0,19 |
| M15 rand + D1 mee | 1.374 | 37% | −0,10 | −2,2 | +0,07 | −0,02 | −0,09 | −0,11 |
| M15 38,2 | 3.816 | 31% | −0,27 | −10,8 | −0,04 | −0,07 | −0,26 | −0,29 |
| M15 38,2 + D1 mee | 1.344 | 33% | −0,20 | −4,4 | +0,03 | −0,09 | −0,17 | −0,23 |
| H1 rand | 823 | 34% | −0,14 | −3,0 | −0,05 | +0,09 | −0,14 | −0,13 |
| **H1 rand + D1 mee** | 306 | 39% | **−0,00** | −0,0 | +0,11 | +0,15 | −0,06 | +0,07 |
| H1 38,2 | 818 | 30% | −0,23 | −4,2 | −0,09 | +0,01 | −0,21 | −0,27 |
| H1 38,2 + D1 mee | 288 | 37% | −0,01 | −0,1 | +0,10 | +0,07 | +0,01 | −0,05 |
| H4 rand | 165 | 36% | −0,07 | −0,7 | −0,02 | +0,20 | −0,24 | +0,16 |
| **H4 rand + D1 mee** | 57 | 39% | **+0,02** | +0,1 | +0,07 | +0,12 | −0,12 | +0,25 |
| H4 38,2 | 145 | 26% | −0,27 | −2,5 | −0,21 | +0,07 | −0,36 | −0,12 |
| H4 38,2 + D1 mee | 47 | 32% | −0,10 | −0,4 | −0,04 | +0,04 | −0,12 | −0,06 |

## Wat de cijfers zeggen
- **Hoe hoger de timeframe en met de D1-trend mee, hoe minder slecht:** M15 −0,17R → H1 met D1 mee ±0 → H4 met D1
  mee +0,02R (maar 57 trades). Dat is een consistente richting, geen voorsprong.
- **Instappen op de rand is beter dan 38,2% diep** in elke variant: dieper wachten geeft minder winnaars.
- **Zonder kosten** zijn de beste varianten licht positief (+0,07 tot +0,11R), maar niet beter dan willekeurig traden
  op hetzelfde uur met dezelfde SL/TP (placebo +0,12 tot +0,15R).
- Handcontrole EURUSD H1 (zone 2 jun 2025, vulling 3 jun 17:08, TP op het 2R-plafond, +1,94R): klopt met de candles.

## Conclusie
Mechanische supply & demand-zones met een limietorder hebben in 2025–2026 geen voorsprong na kosten. De enige
richting die iets oplevert, is "hogere timeframe + D1-trend mee" (break-even). Een volgende stap zou een nieuwe,
vooraf vastgelegde spec zijn op H1/H4 met D1 mee — maar met ±60–300 trades in 21 maanden is een kleine voorsprong
statistisch niet te zien; alleen een vooruit-test kan dat.
