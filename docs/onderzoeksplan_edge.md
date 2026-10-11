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

## 9. Ronde 1 van laag 1 — vooraf vastgelegd (11 okt 2026, vóór enige meting)

**Markten:** XAUUSD, EURUSD, GBPUSD, XAGUSD, US500. **Timeframes:** M15, H1, H4 (bestanden uit MT5; EURUSD-H4 gebouwd uit H1). **Data:** alleen de verkenningshelft (§4); alles vanaf 2025 is vooraf weggesneden.

**Meting per gebeurtenis** (richting d, ATR14 van de gebeurtenis-candle, instap = open van de volgende candle):
- **R21 (hoofdmaat):** een vaste "beugel" van TP +2 ATR en SL −1 ATR, hoogstens 48 candles; raakt één candle beide, dan telt de SL; niets geraakt → resultaat op candle 48. Uitgedrukt in R (1R = 1 ATR).
- Nevenmaten: R11 (+1/−1 ATR), beweging na 4/12/24/48 candles, MFE/MAE over 24 candles.
- **Basislijn:** per gebeurtenis 5 willekeurige candles uit de verkenningshelft van dezelfde markt en timeframe, met **hetzelfde uur** en dezelfde richting (en, bij een trendvariant, dezelfde trendstand). Edge = gemiddelde gebeurtenis − gemiddelde basislijn.
- **Onzekerheid:** standaardfout gegroepeerd per kalenderweek (gebeurtenissen in dezelfde week zijn niet onafhankelijk).
- **Kosten** per markt in R = (typische spread + 2 × slippage + commissie) / mediane ATR van die timeframe.

**Gebeurtenissen (familie → varianten), swinglengte L = 1, 3, 5 waar van toepassing:**
1. **BOS met de structuur mee** (setup-TF HH+HL, body voorbij de laatste swing): alle · displacement (body ≥ 1 ATR) · TF+1 mee · TF+1 én TF+2 mee.
2. **CHoCH** (structuur LH+LL, body boven de laatste swing high; short gespiegeld): alle · displacement · **MSS** (displacement + FVG in de laatste 3 candles) · TF+1 mee met de nieuwe richting · met sweep in de 12 candles ervoor.
3. **Sweeps (ommekeer):** swing-sweep (L) · vorige-dag high/low (M15, H1) · vorige-week high/low (H1, H4) · Azië-range high/low (servertijd 01–09u; M15, H1); telkens alle · TF+1 mee met de ommekeer.
4. **FVG:** vorming met TF+1 mee · eerste retest van de rand binnen 12 candles met TF+1 mee (instap op de rand) · **inverse FVG** (close door de FVG binnen 24 candles → andere richting) · vorming zonder trendfilter.
Hogere timeframes: M15 → H1, H4 · H1 → H4, D1 · H4 → D1, W1.

**Poort naar laag 2 (alles moet kloppen):**
- ≥ 100 gebeurtenissen in de verkenningshelft voor die markt;
- edge op R21 met t ≥ 3,0 als minstens één andere markt dezelfde kant op wijst (t ≥ 1), anders t ≥ 3,5;
- zelfde teken vóór 2020 en in de oneven maanden 2020–2024 (waar beide bestaan), en in de meerderheid van de jaren;
- minstens 2 van de 3 waarden van L dezelfde kant op (waar L bestaat);
- gemiddelde R21 min kosten ≥ +0,05R (of, bij een negatief effect, de omgekeerde trade).
Alle rijen gaan in het testregister (`research/register_ronde1.csv`), ook wat niets oplevert.

## 10. Laag 2 voor de beste H4-aanwijzingen — vooraf vastgelegd (11 okt 2026, vóór enige meting)
Ronde 1 leverde niets door de poort. Om niets te missen door de vaste ATR-beugel, gaan de beste H4-aanwijzingen toch door laag 2, met echte regels.

**Selectieregel (objectief):** H4, edge > 0, t ≥ 1,5 (bij 2R of 1,5R), n ≥ 100, en positief na kosten. Dat geeft 6 kandidaten, allemaal forex:
1. GBPUSD · BOS L1 · TF+1 (D1) mee
2. EURUSD · CHoCH L3 · alle
3. EURUSD · CHoCH L3 · displacement
4. EURUSD · CHoCH L3 · TF+1 (D1) mee
5. GBPUSD · CHoCH L5 · alle
6. GBPUSD · FVG-vorming · TF+1 (D1) mee

**Regels:**
- Instap: marktorder op de open van de volgende H4-candle.
- SL op de structuur − buffer (spread + 0,1 × ATR14 H4): BOS → laatste bevestigde higher low; CHoCH → laagste low tussen de gebroken swing high en de CHoCH-candle; FVG → laagste low van de drie FVG-candles (short gespiegeld).
- **TP 1,5R** (Gitchi's RR, hoofdmaat); 2R alleen ter info.
- Minimale SL 1 × ATR, kostenplafond 0,2R, trades lopen tot SL/TP, swap per nacht, 1 positie per markt, dagstop −2R.
- Uitvoering gecontroleerd op **M15-candles** (fijnste data vanaf 2010); raakt een M15-candle SL en TP, dan telt de SL.
- Kosten: EURUSD zoals ingesteld (swap long 0,8 pip, short 0); GBPUSD: min. spread 0,3 pip, slippage 0,3 pip, commissie 0,8 pip, swap 0,8 pip in beide richtingen (voorzichtig, niet gemeten).
- Alleen gebeurtenissen in de verkenningshelft.

**Poort naar de bevestigingshelft:** ≥ 100 trades, gemiddeld ≥ +0,10R netto bij 1,5R, t ≥ 2,0, positief vóór 2020 én in 2020–2024 (oneven maanden), meerderheid van de jaren positief. Wat erdoor komt, wordt één keer getest op de even maanden 2020–2024.

## 11. Ronde 2 — vooraf vastgelegd (11 okt 2026, vóór enige meting)
Bronnen: het ICT-boek dat Gitchi aanleverde (*ICT 2022 Mentorship — Full ICT Day Trading Model*, LumiTraders; samengevat in `docs/ict_boek_samenvatting.md`) en bekende niet-ICT-effecten.
**Tijd:** de server van IC Markets = New York + 7 uur, het hele jaar (gecontroleerd: de week opent altijd om 00:00 server; US500 opent om 16:30 server = 09:30 NY). Alle ICT-tijden hieronder in NY-tijd met servertijd erbij.
**Data:** alleen de verkenningshelft (§4); M15 voor de intraday-modellen, D1 gebouwd uit H1.

### A. ICT-tijdmodellen (nieuw t.o.v. ronde 1: vaste tijdvensters, sessieniveaus, dagbias)
Niveaus per dag: Azië-range 20:00–00:00 NY (03–07 server) · midnight open = open om 00:00 NY (07:00 server) · London-range 02:00–05:00 NY (09–12 server) · ADR5 = gemiddelde dagrange van de 5 vorige dagen.
**Dagbias (boek H12):** gisteren boven de high van eergisteren geweest maar eronder gesloten → bias SHORT vandaag; spiegelbeeld → LONG; anders geen bias.
1. **London Judas:** tussen 02:00–05:00 NY (09–12 server) de eerste M15-candle die onder de Azië-low prikt en erboven sluit → LONG (spiegel: SHORT). SL = low van die candle − buffer.
   Varianten: alle · met dagbias mee · smalle Azië-range (< 0,3 × ADR5) · ma–wo · smal + bias · SMT (alleen EURUSD/GBPUSD: de andere munt maakte in hetzelfde venster géén nieuwe Azië-low).
2. **Silver Bullet:** liquiditeit = London-high/low. Tussen 09:30–10:00 NY (16:30–17:00 server) een sweep ervan (wick erdoor, close terug); daarna tussen 10:00–11:00 NY (17–18 server) de eerste M15-FVG in de tegenrichting → limiet op het midden van de FVG (geldig tot 11:00 NY). SL = extreme van de sweep − buffer. Varianten: alle · met dagbias mee.
3. **Monday range:** di–vr, de eerste H1-candle die boven de maandag-high prikt en eronder sluit → SHORT (spiegel LONG). SL = high van die candle + buffer. Varianten: alle · met dagbias mee.
4. **Dagbias als trade:** bij bias SHORT: short op de midnight open (07:00 server), SL = high van gisteren + buffer. Spiegel voor LONG.
5. **London close:** is om 10:00 NY (17:00 server) de range van de dag (vanaf midnight open) > ADR5, fade dan de richting van de dag op de open van 17:00 server, SL = extreme van de dag + buffer.
**Meting A:** instap zoals beschreven, SL zoals beschreven (buffer = 0,1 × ATR14 M15), **TP 1,5R** (hoofdmaat, Gitchi's RR), uiterlijk sluiten om 16:00 NY (23:00 server) — het boek is een daytrade-model. SL eerst bij twijfel binnen een M15-candle; limiet: geen TP op de vulcandle. Netto R = bruto − kosten/risico (kosten zoals ronde 1). Minimale SL 0,5 × ATR14 M15 (anders overslaan).
**Basislijn A:** per trade 5 willekeurige M15-candles uit de verkenningshelft met hetzelfde serveruur en dezelfde richting, met dezelfde SL-afstand in ATR en dezelfde sluittijd.

### B. Bekende effecten buiten ICT
6. **Trendvolgen D1 (Donchian):** LONG als de D1-close boven de hoogste high van de vorige N dagen sluit (instap volgende open), SHORT gespiegeld; eerste SL 2 × ATR20; uitstap als de close onder de laagste low van de vorige M dagen komt (trailing) of op de SL. Systemen: N/M = 20/10 en 55/20. Eén positie per markt, kosten incl. swap per nacht. Beoordeeld **over de 5 markten samen** (zo wordt trendvolgen altijd gebruikt) én per markt.
7. **US500 dips kopen:** close > SMA200 en RSI(2) < 10 → LONG op de volgende open; uitstap als de close boven de SMA5 komt, of na 10 dagen, of op een nood-SL van 3 × ATR14. Variant RSI(2) < 5. Ook op de andere 4 markten, alleen als bewijs.
**Meting B:** echte trades in R (1R = de eerste SL-afstand), na kosten.

### Poort ronde 2 (alles moet kloppen)
- ≥ 100 trades (B6: over de 5 markten samen ≥ 100);
- gemiddeld netto ≥ +0,10R per trade;
- A: edge t.o.v. de basislijn met t ≥ 3,0 als een andere markt mee is (t ≥ 1), anders t ≥ 3,5; B: t ≥ 2,5 t.o.v. nul;
- positief vóór 2020 én in 2020–2024 (oneven maanden), en in de meerderheid van de jaren.
Alles in `research/register_ronde2.csv`.

## 12. Ronde 3 — de resterende bouwstenen, vooraf vastgelegd (11 okt 2026, vóór enige meting)
Beslissing Gitchi: ICT is een methode; we gaan verder met de bouwstenen waarmee we begonnen en die we nog wilden testen.
Zelfde opzet als ronde 1 (laag 1): 5 markten, M15/H1/H4, verkenningshelft, gepaarde basislijn (zelfde uur en richting), geclusterde fout per week. **Hoofdmaat: R15** (beugel TP +1,5 ATR / SL −1 ATR, Gitchi's RR); R21 ter info. Poort zoals §9, met R15.

**Bouwsteen 4 — Order block:** na een BOS met de structuur mee (zelfde BOS als ronde 1, L = 1/3/5) is het OB de laatste candle tegen de richting (LONG: laatste rode candle) tussen de higher low en de BOS-candle. Gebeurtenis = eerste terugkeer in het OB (LONG: low ≤ OB-high) binnen 24 candles; instap op de OB-high (limiet).
Varianten: alle · TF+1 mee · met FVG in de impuls (tussen OB en BOS-candle).

**Bouwsteen 5 — Fibonacci 61,8–78,6% (OTE):** na een BOS (L = 1/3/5): been = higher low → hoogste high t/m de BOS-candle. Gebeurtenis = eerste terugloop tot het niveau binnen 24 candles, zolang er geen nieuwe high boven het been komt; instap op dat niveau (limiet).
Varianten: niveau 61,8% · niveau 70,5% · 61,8% met TF+1 mee.

**Bouwsteen 6 — RSI-divergentie (RSI14):** LONG: twee opeenvolgende bevestigde swing lows (L = 3/5) waarbij de koers een lagere low maakt maar de RSI op die low hoger staat; gebeurtenis op het moment dat de tweede low bevestigd is. SHORT gespiegeld.
Varianten: alle · RSI op de tweede low < 30 (bij SHORT > 70) · TF+1 mee.

**FVG-soorten (backlog):**
- **BPR:** een FVG die overlapt met een tegengestelde FVG van de laatste 10 candles → richting van de nieuwste.
- **Exhaustion-FVG:** FVG na een beweging van ≥ 4 ATR in 12 candles in dezelfde richting → gemeten als ommekeer (tegenrichting).
- **Range-FVG:** FVG terwijl TF+1 NEUTRAL is → richting van de FVG.

**Sweep-variant (backlog):** **equal highs/lows** — twee bevestigde swing highs (L = 3) binnen 0,1 ATR van elkaar en binnen 48 candles; daarna een candle met wick boven allebei en close eronder → SHORT (spiegel LONG). Varianten: alle · TF+1 mee.

Register: `research/register_ronde3.csv`. Wat de poort haalt, gaat naar laag 2 met de echte regels (SL op de structuur, 1,5R, kosten, **maximale looptijd 5 dagen op M15/H1 en 15 dagen op H4**, swap als % van de prijs: 3%/jaar long, short 0 voor EURUSD en 3% voor de rest).
