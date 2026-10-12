# KATSU — spec v0.4: Gitchi-FVG (FVG volgens Gitchi's eigen principes)

Datum: 11 oktober 2026 · Status: **BEVROREN op 12 okt 2026 (versie 2 + §10–11). Geen wijzigingen meer.**
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

## 9. Versie 2 (11 okt 2026, na Gitchi's oordeel over 10 voorbeelden) — vervangt §3.2–3.4, §4 en §5 waar nodig
Gitchi's oordeel per voorbeeld werd gemeten; de regels hieronder scheiden zijn ja's van zijn nee's:
| Regel | Waarom (zijn woorden) | Meting op de 10 voorbeelden |
|---|---|---|
| De **middelste candle** (candle 2) van de FVG *sluit* voorbij de laatste intacte swing high/low | "bij mij is de regel dat de middelste candle de vorige low of high moet doorbreken" | Bij alle ja/misschien-voorbeelden waar, bij 5 van 6 nee's niet |
| Gat ≥ **0,5 ATR** | "veel te krap", "precies een muntworp" | Nee's 0,1–0,4 ATR, ja's 0,7–1,8 ATR |
| Candle 3: body ≥ **25%** van de range | "een soort wick i.p.v. een deftige volle candle" | Het afgewezen voorbeeld: 11%; ja's 28–53% |
| Entry op **61,8%** in het gat (vanaf de rand waar de koers eerst komt) | "entry veel te laag", keuze Gitchi | — |
| TP = oude high/low zoals §5, maar **nooit verder dan 2R** (het dichtste telt) | "TP veeeel te ver", keuze Gitchi | — |
Gevolg: elke breuk geeft precies één FVG, dus de keuze "eerste/laatste" vervalt. Annuleerniveau = de geplande TP
(oude high/low of het 2R-niveau). Goud krijgt geen aparte regel ("voorzichtig", maar voorbeeld 7 wel genomen);
goud wordt in de uitslag apart bekeken.
Varianten nu: trend (met/zonder) × geldigheid (tot ongeldig / 24 uur) = **4 per markt, 12 in totaal**.
Aantal setups: ~1,2–1,5 per dag per markt (was ~5). Mediane SL ≈ 1,6 ATR.
Opgelet: deze regels zijn afgeleid uit 10 voorbeelden (+ 3 screenshots); het risico op "regels die toevallig
bij deze 10 passen" is reëel. Daarom telt alleen de bevestigingshelft als bewijs.

## 10. Testplan, vooraf vastgelegd (12 okt 2026, vóór er één resultaat bekeken is)
Gitchi bedoelde met "61,8%" waarschijnlijk de fib vanaf de verre kant van het gat (= 38,2% diep; voorbeeld 4 van
versie 2). Beide worden getest en vergeleken:
| Keuze | Waarden |
|---|---|
| Entry-diepte in het gat (vanaf de rand waar de koers eerst komt) | **38,2%** · **61,8%** |
| Trend | met trendspotter (H1 én H4 mee) · zonder |
| Geldigheid order | tot ongeldig (vangnet 5 handelsdagen) · max 24 uur |
= 8 varianten × 3 markten (EURUSD, GBPUSD, XAUUSD) = **24 combinaties**, alleen de verkenningshelft.
Uitvoering per markt (één positie of lopende order per markt, dagstop −2R), op M15-candles, maximale looptijd
14 kalenderdagen, alle kosten. Register: `research/register_gfvg.csv`. Poort zoals §8.
Ter info (geen poort): resultaat vóór kosten, vulgraad, annuleringen, long/short apart, per jaar.
Wat er ook uitkomt: een variant die de poort haalt, moet daarna nog standhouden op de bevestigingshelft.

## 11. Eenmalige eindtest 2025–2026 (beslissing Gitchi 12 okt 2026, vastgelegd vóór de run)
Context: de verkenningshelft haalde de poort niet (0/24; zie `gfvg_resultaat.md`). Gitchi kiest er bewust voor om de
eindtest toch nu te gebruiken. Daarom ligt alles hieronder vast vóór er één candle van 2025–2026 bekeken is.
- **Eén hoofdvariant**: entry 38,2% diep (Gitchi's bedoeling) · zonder trendvoorwaarde · geldig tot ongeldig.
  Gekozen omdat het Gitchi's lezing van de fib is en de meeste trades geeft; NIET de beste uit de verkenning.
- **Eén portefeuille**: EURUSD + GBPUSD + XAUUSD samen (gedeelde dagstop −2R, één positie per markt).
- **Periode**: signalen vanaf 1 jan 2025 tot het einde van de data (9 okt 2026). Swings en ATR mogen eerdere
  candles gebruiken (opwarming). De screenshotdagen van Gitchi (3, 21, 22, 29, 30 sep en 6 okt 2026) tellen niet.
- **Uitvoering**: zoals de verkenning (M15-candles, alle kosten, max. looptijd 14 dagen).
- **Geslaagd** als ALLES klopt: ≥ 100 trades · gemiddeld netto ≥ +0,10R · t ≥ 2,0 (geclusterd per week) ·
  positief in 2025 én in 2026.
- **Ter info, zonder poort**: per markt, zonder kosten, en dezelfde variant met trendspotter (H1+H4 mee).
- Uitslag is definitief. Geslaagd = hoogstens kandidaat voor demo (20 trades lijn per lijn met MT5), nooit meteen live.
  Niet geslaagd = deze FVG-regels zijn afgesloten; geen nieuwe varianten testen op 2025–2026.
