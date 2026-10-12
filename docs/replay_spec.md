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
1. Na ≥ 100 echte trades: netto R per trade, t (geclusterd per week), winrate, per markt; vergeleken met
   (a) alle Gitchi-FVG-signalen in dezelfde weken en (b) willekeurige trades met dezelfde SL/TP-afstanden en tijdstippen.
2. Twijfel: twijfel-genomen vs zeker-genomen; twijfel-niet-genomen (hypothetisch) vs genomen.
3. Pas als (1) duidelijk positief is: kenmerken zoeken die zijn trades onderscheiden (sessie, breuk, FVG-grootte,
   trend, afstand tot niveaus), daarvan regels maken en die toetsen op de **even maanden** 2020–2024.
