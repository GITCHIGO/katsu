# KATSU — vooruit-testplan (21 okt 2026)

Doel: de drie kandidaten testen op data die nog niemand gezien heeft (vanaf **10 okt 2026**, servertijd).
Regels liggen vast in `katsu/presets.py` (= de presets in het dashboard; een test controleert dat ze gelijk zijn).
Wijzigen = nieuwe planversie en de teller van die setup begint opnieuw.

## 1. De drie setups (bevroren)
| Setup | Markten | Filters | Uitstap |
|---|---|---|---|
| **Test #1 (FVG)** | EURUSD, GBPUSD, XAUUSD | FVG · sweep gisteren nee · FVG eerste/derde+ · M15 tegen · H1 tegen/neutraal · Azië/Londen/overlap · ma–vr · geen NFP · volatiliteit hoog | 38,2% in het gat, SL onder OB, TP oude high max 2R, max. 14 dagen |
| **AMD-extra (#386)** | EURUSD, XAUUSD | AMD C1-E2/C2-E1 · sweep gisteren ja · D1 mee/neutraal · kosten < 0,1R | TP overkant Azië-range, SL voorbij manipulatie, sluiten op de dagclose |
| **Zone GBPUSD** | GBPUSD | Zone M15/H4 · instap rand · sweep gisteren ja · Azië-sweep ja · M15 en H4 tegen/neutraal · D1 mee/neutraal · geen nacht | limiet 7 dagen, SL onder de zone, TP oude high vóór de vulling max 2R |
Zilver (XAGUSD) en US500 worden niet gebruikt (besluit Gitchi 21 okt 2026).
Per setup per markt één trade tegelijk. Uitvoering op M15 (zoals het dashboard), alle kosten.

## 2. Wat er gemeten wordt
Algemeen (drie setups samen), per setup en per setup × pair: trades, winst/verlies, winrate, gem. R, gem. winnaar,
gem. verliezer, totaal R, pips, $ bij de lots (EURUSD 0,10 · GBPUSD 0,10 · goud 0,02), t-waarde, en de lijst van alle
trades (vultijd, entry, SL, TP, uitstap, R, pips, $) om lijn per lijn met de demo te vergelijken (werkregel 5).
Trades die op het einde van de data nog lopen, tellen pas mee als ze gesloten zijn.

## 3. Werkwijze (elke maand, of wanneer Gitchi wil)
1. Gitchi exporteert in MT5 de **M15**-candles van EURUSD, GBPUSD en XAUUSD vanaf
   1 sep 2026 tot nu (tab-gescheiden; de marktnaam in de bestandsnaam) en stuurt ze door.
2. `python -m scripts.vooruit_data <htf> <vooruitmap> <csv's>` — samenvoegen en controleren.
3. `python -m scripts.vooruittest <vooruitmap> <uit> 2026-10-10` → JSON; `python -m scripts.vooruit_rapport` → pagina
   "KATSU Vooruittest" (altijd cumulatief vanaf 10 okt).
4. Optioneel: dezelfde setups ook op een demo-account traden en vergelijken.

## 4. Verwachting
Samen ±11 à 12 trades per maand (test #1 ±7, AMD ±2, zone ±2,5). **Eén maand zegt bijna niets**; alleen grote
afwijkingen tellen. Elke setup wordt **apart** beoordeeld.

## 5. Stopregels per setup
- Na 20 trades gemiddeld onder −0,3R → stoppen.
- Na 40 trades onder 0 → stoppen.
- Pas na ±150 trades met ≥ +0,10R (en t ≥ 2) klein echt geld overwegen.

## 6. Proefrun
Om het rapport te tonen: september 2026 (oude data, telt niet): 22 trades, winrate 50%, +0,08R gemiddeld.
Komt overeen met het dashboard (verschil = Gitchi's 6 screenshotdagen, die het dashboard voor 2025–26 weglaat).
Uitgebreide proefrun juni – 9 okt 2026 (wens Gitchi, oude data, telt niet): 52 trades, winrate 56%, +0,20R gemiddeld,
winst +$675,71 (29) · verlies −$423,43 (23) · netto +$252,28. Test #1 33 trades +0,22R · AMD 8 trades +0,49R ·
Zone GBPUSD 11 trades −0,05R. Het rapport toont nu ook totale winst en totaal verlies (algemeen, per setup, per pair).
