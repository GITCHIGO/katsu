# KATSU — onderzoeksplan: een echte edge zoeken (fase 2)

**Status:** GOEDGEKEURD 11 okt 2026 (opdeling en werkwijze). Laag 1 wordt gebouwd.
**Datum:** 10 oktober 2026
**Vraag van Gitchi:** niet gewoon alles testen en met het resultaat werken, maar grondig zoeken *wat werkt en wat niet*, met alle varianten van sweep, CHoCH, BOS en FVG, ook op H1 en H4. Eerst brainstormen en zo veel mogelijk bedenken, dan pas bouwen.

---

## 1. Wat we al weten (bouwsteen 1–3, 2020–2024)
- M5: niets werkt, ook niet zonder kosten. M5 valt af.
- Sweep + CHoCH ≈ willekeurig. BOS-continuatie ≈ iets slechter dan willekeurig (breuken lopen vaker terug).
- FVG op M15 met H1 + H4 mee: **vóór kosten** +0,12 à +0,18R, duidelijk boven willekeurig. Na kosten net niet genoeg.
- Kosten zijn op lage timeframes de spelbreker (0,1–0,3R per trade). Op H1/H4 is de SL groter, dus de kosten in R kleiner.
- Patroon: hoe hoger de timeframe en hoe meer de hogere timeframes mee zijn, hoe beter.

## 2. Het grootste gevaar bij "alles testen": toevalstreffers
Test je 500 combinaties, dan zijn er ~25 die puur door toeval "significant" lijken. GAMAN en de meeste retail-modellen zijn daarop gestorven: ze vonden iets moois in het verleden dat nooit echt bestond. Daarom werkt dit plan in **lagen met poortjes**, en telt het **elke** test mee.

## 3. Werkwijze in drie lagen

### Laag 1 — Signaalonderzoek (breed, goedkoop, nog geen strategie)
Voor elk soort gebeurtenis (een BOS, een CHoCH, een sweep van de dagelijkse high, een FVG, …) meten we **wat de koers daarna doet**, zonder entry-, SL- of TP-regels:
- beweging in de verwachte richting na 4, 12, 24 en 48 candles, uitgedrukt in ATR;
- grootste beweging mee (MFE) en tegen (MAE);
- kans dat de koers eerst +1 ATR haalt vóór −1 ATR (en +2 vóór −1);
- altijd naast een **willekeurige basislijn** (zelfde timeframe, zelfde uren, zelfde richting-verdeling).
Zo zien we per gebeurtenis meteen: zit er informatie in, en hoe groot is die vergeleken met de kosten op die timeframe? Wat geen informatie heeft, valt af vóór we er een strategie van maken.

### Laag 2 — Strategie (alleen voor wat laag 1 overleeft)
Pas dan: entry, SL, TP, uitvoering op M1 met alle kosten, placebo, kostenplafond, keuzeregel. De MFE/MAE uit laag 1 vertelt welke SL en TP logisch zijn (in plaats van overal 2R te gokken).

### Laag 3 — Bevestiging en eindtest
- Bevestiging op een apart stuk data dat in laag 1 en 2 niet gebruikt is.
- Daarna, voor de allerbeste kandidaat (of hoogstens enkele), de eenmalige eindtest op 2025–2026.

## 4. Data opdelen (vastgelegd 11 okt 2026, akkoord Gitchi)
**Eindtest = 2025–2026, op slot** (uitdrukkelijke wens Gitchi). De data vanaf 1 jan 2025 wordt weggesneden vóór er iets berekend wordt.

| Data | Gebruik |
|---|---|
| Alles vóór 2020 (FX vanaf 2010, goud/zilver/US500 vanaf feb 2016) **+ oneven maanden 2020–2024** | Verkennen (laag 1 en 2) |
| Even maanden 2020–2024 | Bevestigen (alleen kandidaten, één keer) |
| 2025–2026 | Eindtest (één keer, na bevroren spec) |

- Zo zit elke soort markt (rustige jaren 2016–2019, corona, oorlog, renteverhogingen, de goudrally) in de verkenning, en de bevestiging ligt in dezelfde rommelige jaren 2020–2024 maar op andere maanden.
- Een gebeurtenis hoort bij de maand waarin ze ontstaat; de meetvensters stoppen uiterlijk op 31 dec 2024.
- Extra eis: een effect moet in de meeste afzonderlijke jaren dezelfde kant op wijzen.

**Beschikbare data (ontvangen 11 okt 2026, IC Markets MT5):**
| Markt | M15 / H1 / H4 intraday vanaf | Spread in de data |
|---|---|---|
| EURUSD, GBPUSD | jan 2010 | ja |
| XAUUSD, XAGUSD | eind jan 2016 (daarvóór alleen dagcandles) | deels |
| US500 | feb 2016 (daarvóór alleen dagcandles) | deels |
| XAUUSD, EURUSD M1 | jan 2020 | ja |
Controle: H1 uit het bestand en H1 gebouwd uit de M1-data komen voor 94–99% van de candles tot op 1 tick overeen (2020–2026).

**Waarom oudere data belangrijk is:** een BOS op H4 komt maar ~40–75 keer per jaar per markt voor. Op 3 jaar verkenningsdata is dat te weinig om iets te bewijzen. Met H1/H4 vanaf bv. 2010 wordt dat 5 keer zoveel.

## 5. Wat we testen (de catalogus)
**Timeframes:** M15, H1, H4 als setup. D1 (en H4/W1) als context.
**Markten:** goud en EURUSD. Optioneel extra markten *alleen als bewijs* (zelfde regels): werkt iets op 5 markten, dan is het veel geloofwaardiger dan op 1.

**Structuur**
- BOS: intern vs extern (swing), body vs wick, met/zonder displacement (sterke candle, bv. body ≥ 1 ATR), met/zonder FVG in de breuk.
- CHoCH: intern vs swing; **MSS** (CHoCH met displacement + FVG).
- Swinglengte L = 1, 2, 3, 5 (als buren: een echte edge werkt bij meerdere L).

**Liquiditeit (sweeps)**
- Gewone swing (getest op M5/M15), equal highs/lows, high/low van gisteren (PDH/PDL), vorige week (PWH/PWL), Azië-range, Londen-high/low, ronde getallen.
- Sweep met wick vs met close terug binnen N candles.

**FVG-soorten** (zie `katsu_backlog.md`): continuatie, reversal, inverse (IFVG), BPR/island, range-FVG, exhaustion; instap op rand vs CE (50%).

**Context (als opsplitsing, niet als knop om aan te draaien)**
- Trend op 1 en 2 timeframes hoger (de trendspotter).
- Premium/discount: ligt de koers in de bovenste of onderste helft van de range van de hogere timeframe (ICT).
- Sessie, dag van de week, ATR-regime (rustig/druk), afstand tot de high/low van gisteren.

**Exits** (pas in laag 2): vaste R (1, 1,5, 2, 3), volgende liquiditeit als doel, break-even na 1R. Gekozen op basis van MFE/MAE, niet door alles te proberen.

## 6. Bescherming tegen een valse edge (de poortjes)
1. **Testregister:** elke combinatie die bekeken wordt, komt in een logboek met het aantal. Iedereen kan zien hoeveel er geprobeerd is.
2. **Poort laag 1 → 2:** een gebeurtenis gaat alleen door als ze
   - **per markt** beoordeeld: een edge die alleen op goud of alleen op EURUSD werkt is toegestaan (beslissing Gitchi 10 okt 2026). Omdat dat de kans op een toevalstreffer verdubbelt, is de lat dan hoger: werkt het maar op één markt, dan richtwaarde t ≥ 3,5 in plaats van 3; werkt het op beide, dan telt dat als extra bewijs,
   - in **beide helften** van de verkenningsperiode,
   - de willekeurige basislijn verslaat met een marge die rekening houdt met het aantal tests (strenger naarmate we meer testen; richtwaarde t ≥ 3 in plaats van 2),
   - en een effect heeft dat **groter is dan de kosten** op die timeframe.
3. **Buren:** de naburige instellingen (andere L, ander venster) moeten dezelfde kant op wijzen. Eén eenzaam topje telt niet.
4. **Bevestiging (even maanden 2020–2024):** hoogstens 5 kandidaten, elk één keer.
5. **Eindtest 2025–2026:** één keer, met de succescriteria uit de spec.

## 7. Wat dit níet is
- Geen dataverzameling tot er "iets" positief uitkomt. Als niets de poortjes haalt, is dat de uitkomst, en dat is waardevol: dan weten we dat deze concepten op deze markten geen edge hebben en verliezen we geen geld live.
- Geen combinaties stapelen tot het past. Combinaties mogen pas tussen gebeurtenissen die elk apart al informatie tonen.

## 8. Stand van de vragen (10 okt 2026)
1. Oudere H1/H4/M15-data: ontvangen (zie §4).
2. Opdeling: akkoord, met 2025–2026 als eindtest (zie §4).
3. Extra markten alleen als bewijs: ontvangen voor GBPUSD, XAGUSD en US500 (USDJPY nog niet).
4. Swap EURUSD gemeten op Gitchi's trades (sep–okt 2026): long ≈ −€7/lot/nacht (≈ 0,8 pip, nu zo ingesteld), short ≈ +€1,4 tot +€3,8 (opbrengst, wordt bewust niet meegeteld → 0). Goud: geen gegevens, voorlopig $0,40/oz per nacht in beide richtingen als kost.
