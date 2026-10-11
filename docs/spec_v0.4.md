# KATSU — spec v0.4: Gitchi-FVG (FVG volgens Gitchi's eigen principes)

Datum: 11 oktober 2026 · Status: **concept, goedgekeurd in chat (11 okt 2026), nog niet bevroren**
Bron: Gitchi's uitleg en screenshots (EURUSD M15, sep–okt 2026). Die screenshots liggen in de eindtestperiode;
de dagen 29–30/9, 21–22/9, 3/9 en 6/10/2026 worden daarom uit de eindtest gehouden.

## 1. Idee in één zin
Een FVG telt alleen als de beweging die hem maakt een vorige swing high breekt (bearish: een vorige swing low);
instap met een limietorder op de rand van de FVG bij de retest, SL onder het order block / de laatste low,
TP op de eerstvolgende oude high die nog niet gebroken is.

## 2. Markten, timeframe, data
- Setup op **M15**. Markten: EURUSD, GBPUSD, XAUUSD.
- Alleen de **verkenningshelft** (vóór 2020 + oneven maanden 2020–2024). Bevestigingshelft en 2025–2026 dicht.
- Uitvoering op M15-candles (M1 bestaat pas vanaf 2020; zelfde aanpak als laag 2 in ronde 1–3).
- Tijden in de grafieken: Belgische tijd = server − 1 uur.

## 3. Definities (LONG; SHORT is exact gespiegeld)
1. **Swing high/low**: zoals spec v0.1 §3, met L = 3 (strikt hoger dan 3 candles links en rechts; pas bruikbaar na
   sluiting van de 3de candle rechts).
2. **Breuk van een vorige high**: candle b *sluit* boven de laatste bevestigde swing high H, en geen enkele candle
   sloot er sinds H boven. Elke swing high kan maar één keer gebroken worden.
3. **Het been (de beweging)**: van de laagste low tussen H en b (de *oorsprong*) tot het einde van de duw. De duw is
   voorbij zodra er een nieuwe swing high (index ≥ b) bevestigd is.
4. **Cluster**: alle bullish FVG's waarvan candle 1 op of na de oorsprong ligt en die gevormd zijn vóór het einde van
   de duw. Bullish FVG = low(candle 3) > high(candle 1); gat = high(candle 1) tot low(candle 3).
   Een FVG die vóór het signaal al aangeraakt werd (low ≤ bovenkant), telt niet meer. Elke FVG wordt maar één keer gebruikt.
5. **Signaalmoment**: einde van candle b (als de FVG er al was) of einde van candle 3 van de FVG (als die later komt).
   Alleen gesloten candles.

## 4. Varianten (vooraf vastgelegd: 2 × 2 × 2 = 8 per markt)
| Keuze | Waarde 1 | Waarde 2 |
|---|---|---|
| Welke FVG | **eerste**: eerste nog onaangeraakte FVG van het been; de order blijft daar | **laatste**: steeds de nieuwste FVG; elke nieuwe FVG in de duw vervangt de vorige order |
| Trend | **met trendspotter**: H1 én H4 UP op het signaalmoment (trend uit swings L = 3, alleen gesloten candles) | **zonder** |
| Geldigheid order | **tot ongeldig**, met vangnet 5 handelsdagen (480 M15-candles) | **max 24 uur** |

## 5. Order
- **Entry**: limiet op de bovenkant van het gat (SHORT: onderkant). Alleen de eerste aanraking telt.
- **SL-basis**: het order block = de laatste bearish candle (close < open) tussen de oorsprong en candle 1 van de FVG
  (geen bearish candle: de oorsprong). SL-basis = laagste low van het order block tot en met candle 2.
  Buffer, minimum (1 ATR, anders overgeslagen: nooit een krappe SL) en kostenplafond (0,2R) zoals spec v0.2.
- **TP (variant A)**: de laagste bevestigde swing high (L = 3) boven de hoogste high van het been tot het signaal,
  die sindsdien door geen enkele high geraakt is. Geen minimum-RR. Geen zo'n high: geen trade (gelogd).
- **Annulering vóór de vulling**:
  - de koers raakt eerst het TP-niveau (de beweging is gebeurd; zelfde candle als de vulling: annulering telt);
  - variant *laatste*: er ontstaat een nieuwere FVG in de duw;
  - de geldigheid (5 handelsdagen of 24 uur) is voorbij.
  - (Een close door het gat of een breuk van de oorsprong kan niet vóór de vulling gebeuren: de koers moet eerst
    door de entry. Die gevallen zijn dus gewoon de SL.)

## 6. Risico en beheer
1% risico, resultaat in R, dagstop −2R (alleen gesloten trades), één positie of lopende order per markt,
trade loopt tot SL of TP, maximale looptijd 10 handelsdagen (14 kalenderdagen), swap per nacht,
alle kosten (spread met minimum, slippage, commissie, rollover-spread).

## 7. Volgorde
1. Detector + tests. 2. **10 willekeurige voorbeelden** (vaste toevalsgenerator) aan Gitchi tonen; hij zegt per
voorbeeld ja/nee + waarom. Pas als het grootste deel klopt: 3. test op de verkenningshelft (laag 2: echte regels),
register `research/register_gfvg.csv`. Een winnende variant moet daarna standhouden op de bevestigingshelft;
pas daarna de eenmalige eindtest.

## 8. Poort (zelfde maatstaf als laag 2 eerder)
n ≥ 100, gemiddeld netto ≥ +0,10R, t ≥ 2,0 (geclusterd per week), positief vóór 2020 én 2020–24,
meer dan de helft van de jaren positief. Met 8 varianten × 3 markten = 24 combinaties is één "toevalstreffer"
met t ≈ 2 te verwachten; daarom telt pas de bevestigingshelft.
