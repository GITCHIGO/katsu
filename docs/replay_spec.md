# KATSU Replay — spec (12 okt 2026)

Doel: Gitchi's eigen, discretionaire beslissingen vastleggen onder eerlijke omstandigheden, om (1) te meten of ze na
kosten een voorsprong hebben en (2) daarna te begrijpen wat hij filtert, zodat dat later regels kunnen worden.
Achtergrond: alle mechanische bouwstenen faalden (zie rapporten); Gitchi was winstgevend op een prop firm en live,
maar die geschiedenis is niet meer beschikbaar.

## Data en blindheid
- EURUSD en XAUUSD, M1 (IC Markets), **alleen oneven maanden 2020–2024** voor het vooruitspelen.
  De even maanden blijven schoon om regels die uit zijn trades volgen later te toetsen. 2025–2026 wordt niet gebruikt.
- 20 episodes per markt: start op een maandag 00:00 (server), 2 handelsweken vooruit, ~20 handelsdagen geschiedenis
  ervoor (die geschiedenis kan in een even maand liggen; alleen als context, zonder datum).
- Geen jaar/maand/datum in beeld: alleen weekdag en uur in **Belgische tijd (server − 1 u)**.

## Bediening
- Timeframes M3, M5, M10, M15, M30, H1, H4 (opgebouwd uit M1; de laatste candle groeit mee, zoals live).
- Vooruit per candle van de gekozen TF, afspelen met snelheid, terugkijken. Orders alleen op het verste punt
  dat al bereikt is (terugkijken is kijken, geen handelen).
- Tekenen: horizontale lijn, trendlijn, rechthoek (optioneel doorgetrokken naar rechts), tekst; kleuren; wissen.
- Orders: market, limit, stop; SL en TP verplicht (prijs). Wijzigen van SL/TP en manueel sluiten mogelijk (gelogd).
- Knoppen: **"Twijfel"** (vinkje bij een trade) en **"Gezien, niet genomen"** / **"Twijfel, niet genomen"**,
  met richting, optioneel entry/SL/TP (hypothetische trade) en een korte reden.

## Uitvoering (zelfde regels als de backtest)
- Data = BID; ASK = BID + spread (max van data en minimum). Market- en stoporders + slippage; SL + slippage.
- Market: gevuld op de open van de volgende M1-candle. Limiet op de limietprijs (of beter bij een gap).
- SL en TP per M1; raakt één M1-candle beide, dan telt de SL. Op de vulcandle van een limiet/stop alleen de SL.
- Kosten: EURUSD min. spread 0,1 pip, slippage 0,3 pip, commissie 0,8 pip; goud min. spread $0,10, slippage $0,25,
  commissie $0,08. Rollover-spread verbreed (23:55–01:30 server). Swap rekent de analyse in Python achteraf.
- Resultaat in R (netto). De analyse in Python herrekent elke trade met `katsu/execution.py` (de pagina is een spiegel).

## Opslag (db van de pagina; Claude leest mee)
- `trades/<id>`: episode, markt, tijdstip (server-minuut), TF in beeld, richting, type, entry/SL/TP (+ wijzigingen),
  twijfel, reden, status en resultaat.
- `beslissingen/<id>`: overgeslagen of twijfel-niet-genomen, met richting, optioneel entry/SL/TP, reden, tijdstip.
- `tekeningen/<episode>` en `voortgang/<episode>`.

## Analyse (vooraf vastgelegd)
Gitchi traedt met een **vaste lotgrootte** (EURUSD 0,1 lot), niet met 1% risico per trade (12 okt 2026). De replay
toont daarom pips en dollars bij de ingevulde lot (1 pip = $10 per lot op EURUSD en goud); R blijft opgeslagen.
De hoofdmaat voor de analyse is **netto pips per trade** (en $ bij zijn lot); R wordt ter info ook getoond.
Voor een later model blijft werkregel 6 (vast risico in R) gelden; dat is een aparte keuze.
1. Na ≥ 100 echte trades: netto pips (en R) per trade, t (geclusterd per week), winrate, per markt; vergeleken met
   (a) alle Gitchi-FVG-signalen in dezelfde weken en (b) willekeurige trades met dezelfde SL/TP-afstanden en tijdstippen.
2. Twijfel: twijfel-genomen vs zeker-genomen; twijfel-niet-genomen (hypothetisch) vs genomen.
2b. TP en SL (wens Gitchi, 12 okt 2026; vast onderdeel van elke analyse): per trade MFE/MAE, hoeveel pips er
   tot de TP ontbraken, of een ruimere SL de trade had gered (nodige extra pips tot de TP alsnog kwam) en hoe krap
   winnaars hun SL ontsnapten. Code: `katsu/replay_analyse.py`, `scripts/replay_analyse.py`. Pas bij voldoende trades
   conclusies trekken (een TP iets vóór een oude high, een ruimere SL); elke aanpassing is een nieuwe, vooraf
   vastgelegde test.
3. Pas als (1) duidelijk positief is: kenmerken zoeken die zijn trades onderscheiden (sessie, breuk, FVG-grootte,
   trend, afstand tot niveaus), daarvan regels maken en die toetsen op de **even maanden** 2020–2024.

## Publicatie
Pagina: `replay/page.html` (+ `replay/sim.js`), gebouwd met `scripts/replay_build.py`; gepubliceerd als artifact
"KATSU Replay" met db-opslag. Episodes als base64-tekst (`episodes/<id>.txt`). Sleutel episode → datum staat buiten
de repo (`katsu_research/replay/sleutel.csv`).

## Ronde 2 — reset (24 okt 2026, besluit Gitchi)
- Gitchi begint opnieuw en neemt de replay vanaf nu ernstig. De 24 trades van ronde 1 (12 okt) zijn **gewist** en tellen
  niet mee; ook beslissingen, tekeningen en voortgang zijn leeg.
- **Fout in ronde 1:** de episodes konden overlappen (twee maandagen in dezelfde maand, 2 weken vooruit); 8 paren
  deelden een week, en de geschiedenis van een episode kon het speelvenster van een andere tonen.
- **Nieuwe keuze van de weken:** per markt **hoogstens één episode per oneven maand** (maandag op dag 1–14, 12 dagen
  vooruit, 28 dagen geschiedenis). Zo overlapt geen speelvenster een ander speelvenster of andermans geschiedenis.
- **Uitgesloten (al gezien in ronde 1), voor beide markten** (zelfde week = zelfde dollarnieuws): mei 2020, nov 2020,
  jan 2022, jul 2022, jul 2024.
- Nog steeds 20 episodes per markt (EURUSD, XAUUSD), willekeurig gekozen (seed 20261024), nummering niet
  chronologisch, oude sleutel bewaard als `katsu_research/replay/sleutel_ronde1.csv`.
- ~~De even maanden 2020–2024 blijven gereserveerd voor de replay~~ — gewijzigd 24 okt 2026 (besluit Gitchi): de even
  maanden zijn de eindtest van spec v0.8. Regels uit de replay toetsen zich vooruit op de demo.
