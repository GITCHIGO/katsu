# KATSU — spec: dashboard met bouwstenen (12 okt 2026)

Doel: Gitchi kan bouwstenen (setups en filters) vrij combineren en ziet meteen hoe die combinatie het deed op de
**verkenningsdata**. Het dashboard is om ideeën te **zoeken**; bewijs komt alleen van de **bevestigingshelft**
(even maanden 2020–2024, nooit bekeken), en daarna van een demo.

## 1. Data
EURUSD, GBPUSD, XAUUSD · M15 · verkenningshelft (FX 2010–2019, goud feb 2016–2019, + oneven maanden 2020–2024).
Uitvoering op M15-candles (M1 bestaat pas vanaf 2020), met alle kosten. Elke setup wordt **apart** gesimuleerd
(geen portefeuille: overlappende setups tellen allemaal mee). Tijden in Belgische tijd (server − 1 u).

## 2. Soorten setups (LONG; SHORT gespiegeld)
| Soort | Definitie | Signaal |
|---|---|---|
| **FVG** | elke bullish FVG: low(candle 3) > high(candle 1). **"FVG na breuk"** = filter *breuk* ≠ geen: de middelste candle sluit voorbij de laatste bevestigde, intacte swing high (L = 3), zoals spec v0.4 | einde candle 3 |
| **IFVG** | een bearish FVG waar binnen 48 candles een candle **boven** sluit (boven de bovenrand van het gat): het gat wordt steun → long | einde van die candle |
Sweep+CHoCH, BOS, enz. zijn **filters** op deze setups (zie §4), geen aparte soorten.

## 3. Uitstap (jouw regels, voor alle soorten gelijk)
- Entry: limiet op **38,2% diep** in het gat (vanaf de rand die de koers eerst raakt). Geldig tot ongeldig:
  vangnet 5 handelsdagen; geannuleerd als de TP eerst geraakt wordt.
- SL-basis: FVG met breuk = laagste low van het order block (laatste tegengestelde candle tussen de oorsprong van het
  been en candle 1) t/m candle 2 (spec v0.4). FVG zonder breuk = laagste low van de laatste tegengestelde candle
  binnen 10 candles vóór candle 1 t/m candle 2 (geen: candle 1–2). IFVG = laagste low
  tussen candle 1 van de oorspronkelijke FVG en de omkeer-candle. Buffer spread + 0,1 ATR. **Geen** minimum-SL en
  **geen** kostenplafond: de SL-grootte en de kosten zijn filters.
- TP: laagste ongeraakte swing high (L = 3) boven de top van de beweging, maximaal 2R; geen: 2R.
- Maximale looptijd 14 kalenderdagen.

## 4. Kenmerken (filters) — alleen wat op het signaalmoment bekend is
| Groep | Kenmerk | Waarden |
|---|---|---|
| Basis | markt, soort, richting | |
| Structuur | breuk | geen / BOS (M15-trend al mee) / CHoCH (M15-trend tegen) / breuk uit neutraal |
| | sweep vooraf (20 candles vóór candle 1) | swing-low geveegd (wick eronder, close erboven) ja/nee |
| | sweep vorige dag / Azië | low van gisteren / van de Azië-sessie (01–08 BE) vandaag geveegd vóór het signaal: ja/nee |
| | order block | tegengestelde candle binnen 10 candles vóór candle 1: ja/nee |
| | FVG-nummer | eerste / tweede / derde+ FVG in dezelfde richting binnen 20 candles |
| Trend | M15, H1, H4, D1 | mee / tegen / neutraal (trendspotter, alleen gesloten candles) |
| | premium/discount | entry in de goedkope helft van de range van gisteren (long) = "mee", anders "tegen" |
| Tijd | sessie | Azië 01–08 · Londen 08–13 · overlap 13–17 · New York 17–22 · nacht 22–01 (BE) |
| | uur, weekdag | |
| | Silver Bullet-venster | 09–10 / 16–17 / 20–21 BE: ja/nee |
| Vorm & markt | grootte gat (× ATR) | < 0,25 · 0,25–0,5 · 0,5–1 · 1–2 · > 2 |
| | displacement (body candle 2 × ATR) | < 0,5 · 0,5–1 · 1–2 · > 2 |
| | candle 3 vol | body/range < 25% · 25–50% · ≥ 50% |
| | SL (× ATR) | < 1 · 1–2 · 2–3 · > 3 |
| | geplande RR | < 1 · 1–1,5 · 1,5–2 · 2 |
| | kosten (R) | < 0,1 · 0,1–0,2 · > 0,2 |
| | volatiliteit | ATR t.o.v. mediaan van 20 dagen: laag (< 0,8) · normaal · hoog (> 1,25) |
| | NFP-dag | eerste vrijdag van de maand: ja/nee (andere nieuwsdata later) |

## 5. Uitkomst per setup
gevuld of niet · TP/SL/max. duur · netto R · netto pips · R zonder kosten · duur.
**Vergelijkingstrade (placebo):** dezelfde richting, SL- en TP-afstand, op hetzelfde uur van een willekeurige andere
dag (zelfde markt, verkenningsdata), als markt-order. Zo zie je of een filter beter doet dan "gewoon op dat uur traden".

## 6. Wat het dashboard toont
Aantal (gevuld), winrate, gem. R netto, gem. pips per markt, R zonder kosten, placebo, t (geclusterd per week),
curve (cumulatieve R), per jaar, vóór 2020 vs 2020–24, en een uitsplitsing "per waarde" voor elk kenmerk.

## 7. Vangrails
- **Pogingenteller:** elke nieuwe filtercombinatie die je bekijkt, telt (bewaard). Het dashboard toont de lat:
  bij N pogingen is een toevalstreffer van t ≈ √(2·ln N) normaal; pas wat daar ruim boven ligt, is interessant.
- **Bevriezen:** maximaal **3** combinaties. Een bevroren combinatie wordt door Claude één keer getest op de
  bevestigingshelft (zelfde regels, met portefeuille: één positie per markt, dagstop). Alleen die uitslag telt.
  Poort: n ≥ 100, gem. netto ≥ +0,10R, t ≥ 2,0, positief in 2020–22 én 2023–24.
- 2025–2026 wordt niet gebruikt.
