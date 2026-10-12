# KATSU — spec v0.5: ICT Silver Bullet (bouwsteen op vraag van Gitchi, 12 okt 2026)

Status: **testplan vooraf vastgelegd (vóór de run)**. Alleen de verkenningshelft. Bevestigingshelft dicht.
2025–2026 wordt niet gebruikt (eindtest voor FVG-strategieën is al gebruikt op 12 okt 2026).

## 0. Wat al bekend is
Ronde 2 testte een smalle versie (alleen 10–11u NY, alleen na een sweep van de London-high/low, instap op het
midden): 358 trades, bruto 0,00R, net als willekeurige trades op hetzelfde kwartier. Deze spec test de bredere,
gangbare versie met alle drie de vensters.

## 1. Bronnen (research 12 okt 2026)
- FXOpen, "The ICT Silver Bullet Trading Strategy": vensters 03–04, 10–11, 14–15u New York; FVG die in het venster
  ontstaat; limiet op de rand van de FVG die het dichtst ligt; SL onder candle 1 of voorbij de laatste swing;
  TP op de volgende liquiditeit, vaak ≥ 1:2; richting volgens de hogere timeframe.
- LuxAlgo, "Silver Bullet": in het venster eerst een sweep van liquiditeit óf een structuurwissel, daarna een FVG
  door displacement; geen FVG vóór het einde van het venster = geen trade; SL voorbij de manipulatie-swing;
  TP op de liquiditeit aan de overkant.

## 2. Regels (LONG; SHORT gespiegeld)
1. **Vensters** (servertijd = New York + 7 u, het hele jaar): London 10:00–11:00, NY AM 17:00–18:00, NY PM 21:00–22:00
   (= 03–04, 10–11, 14–15u NY). Belgische tijd = server − 1 u.
2. **FVG**: candle 2 en candle 3 beginnen in het venster en candle 3 sluit uiterlijk op het einde van het venster.
   Bullish FVG = low(candle 3) > high(candle 1). Per venster per dag maximaal **één** setup: de eerste FVG die de filter haalt.
3. **Filter (3 varianten)**:
   - *alle*: geen extra voorwaarde.
   - *sweep*: tussen het begin van het venster en candle 2 ging de koers onder de laatste bevestigde swing low
     (L = 3, bevestigd vóór het venster). Bij SHORT: boven de laatste swing high.
   - *bias*: H1-trend (trendspotter, alleen gesloten candles) in de richting van de trade.
4. **Entry**: limiet op de bovenkant van het gat (SHORT: onderkant). Geldig tot het einde van het venster.
   Geannuleerd als de geplande TP eerst geraakt wordt.
5. **SL-basis**: de laagste low van het begin van het venster tot en met candle 3 (de manipulatie-swing).
   Buffer, minimum-SL (1 ATR) en kostenplafond (0,2R) zoals altijd.
6. **TP**: de laagste bevestigde swing high (L = 3) boven de top van de beweging die nog niet geraakt is, maximaal 2R
   (keuze Gitchi, v0.4); geen zo'n high: 2R.
7. Trade loopt tot SL of TP, maximale looptijd 14 kalenderdagen, alle kosten, één positie per markt, dagstop −2R.

## 3. Timeframes, markten, data
| Versie | Markten | Periode (verkenningshelft) | Uitvoering |
|---|---|---|---|
| **M5** | EURUSD, XAUUSD | oneven maanden 2020–2024 (M1 bestaat pas vanaf 2020) | op M1 |
| **M15** | EURUSD, GBPUSD, XAUUSD | vóór 2020 + oneven maanden 2020–2024 | op M15 |
Combinaties: M15 3 × 3 vensters × 3 filters = 27; M5 2 × 3 × 3 = 18; **samen 45**.

## 4. Poort (zelfde maatstaf als eerder)
n ≥ 100 · gemiddeld netto ≥ +0,10R · t ≥ 2,0 (geclusterd per week) · positief in beide helften
(M15: vóór 2020 en 2020–24; M5: 2020–22 en 2023–24) · meer dan de helft van de jaren positief.
Ter info: zonder kosten, winrate, vulgraad. Een variant die slaagt, moet daarna op de bevestigingshelft standhouden.
Register: `research/register_silver_bullet.csv`.
