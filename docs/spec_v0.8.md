# KATSU — spec v0.8: intraday / scalp met Traders Reality-ideeën en ronde getallen (24 okt 2026, akkoord Gitchi)

Wens Gitchi (24 okt 2026): iets dat **dagelijks** terugkomt, richting scalpen, vertrekkend van **Traders Reality**
(waar hij begon) — vector candles en ADR ("wat jij het beste vindt"). Trendvolgen op D1 is te traag (afgewezen).
**Akkoord Gitchi 24 okt 2026** ("ja, bouwen"). Vastgelegd vóór er één trade berekend is; de verduidelijkingen in §2b
zijn toegevoegd tijdens het bouwen, ook vóór de eerste run.

## 0. Waarom deze ideeën (de reden vóór de data)
- **Ronde getallen (Osler 2003, New York Fed, echte orderboeken van een bank, EURUSD/GBPUSD/USDJPY):** take-profits
  liggen vaak exact op 00-niveaus → de koers keert daar iets vaker; stop-losses liggen net voorbij ronde getallen →
  na een doorbraak versnelt de koers. Het effect is klein (in de simulatie ±3 procentpunt meer keringen) en de studie
  test niet of het na kosten winst geeft. Dit is het enige idee hier met onderzoek erachter.
- **Vector candles (PVSRA):** een candle met uitzonderlijk volume = grote partijen actief. Traders Reality: zulke zones
  worden later "recovered" (de koers komt terug). In forex alleen **tick-volume** (aantal prijswijzigingen) — een
  benadering van echt volume. Geen onderzoek bekend; wordt eerlijk getest.
- **ADR (gemiddelde dagrange):** dagranges keren terug naar hun gemiddelde (bekend statistisch gegeven). Een dag die
  zijn ADR al gemaakt heeft, heeft gemiddeld minder ruimte over → ADR als **filter en TP-plafond** (keuze Claude).

## 1. Definities (alleen gesloten candles; servertijd = New York + 7 u; Belgisch = server − 1 u)
- **Signaal-timeframe M5** (opgebouwd uit M1). ATR = ATR14 van M5.
- **Vector (climax):** tick-volume ≥ **2 × het gemiddelde van de 10 vorige M5-candles**, of range × tick-volume ≥ het
  hoogste van de 10 vorige (definitie Traders Reality-indicator). Bull = close > open, bear = close < open.
  De 150%-vectors (blauw/violet) worden niet gebruikt.
- **ADR** = gemiddelde (high − low) van de **14 vorige** serverdagen (zondagcandles niet meegeteld).
  **ADR-high** = laagste koers van vandaag tot nu + ADR · **ADR-low** = hoogste van vandaag − ADR.
  **Rest-ADR long** = ADR-high − entry · short = entry − ADR-low.
- **Rond niveau:** EURUSD elk **00 en 50** (1.0800, 1.0850 …) · XAUUSD elke **$10** (2350, 2360 …).
- **Handelsvenster:** signalen 08:00–21:00 Belgisch (Londen + New York; Azië heeft weinig volume). Alles wat om
  **22:45 Belgisch** nog open is, wordt gesloten (intraday, geen swap). Een order die dan nog niet gevuld is, vervalt.

## 2. Vier varianten (niet meer; elk apart)
Overal: **SL minimum** EURUSD 6 pips · goud $2,50 (kosten ≤ ±0,25R en weinig twijfel binnen één M1-candle);
**TP 1,5R** (Gitchi's gewone RR), **maar nooit verder dan de rest-ADR** — past 1,5R niet, dan geen trade als de
rest-ADR < 1R, anders TP op de rest-ADR. Eén trade tegelijk per variant per markt.

| Variant | Idee | Signaal | Order | SL |
|---|---|---|---|---|
| **V1 vector-recovery** | koers komt terug in de vector, daarna verder in de richting van de vector | bull-vector (long) / bear-vector (short), body ≥ 1 × ATR | limiet op **50% van de body**, geldig 24 M5-candles (2 u); geannuleerd als de TP eerst geraakt wordt | voorbij de wick van de vector + spread + 0,1 ATR |
| **V2 vector aan ADR-uiterste** (Traders Reality "climax aan de top") | uitputting → ommekeer | bull-vector die een nieuwe dag-high maakt terwijl de dagrange ≥ 90% ADR → **short** (spiegel voor long) | **stoporder** op 50% van de body (de koers moet eerst terugvallen = bevestiging), geldig 12 M5-candles | voorbij de high (low) van de vector + spread + 0,1 ATR |
| **V3 ronde getal: kering** (Osler 1) | TP-orders op het niveau → koers keert | koers nadert een rond niveau van ≥ 15 pips / $5 weg, eerste aanraking die dag | limiet **1 pip / $0,30 vóór** het niveau, tegen de beweging in (koers stijgt naar 1.0900 → sell limit 1.0899) | 6 pips / $2,50 voorbij het niveau |
| **V4 ronde getal: doorbraak** (Osler 2) | stops net voorbij het niveau → versnelling | eerste M5-close ≥ 2 pips / $0,60 voorbij een rond niveau die dag | marktorder op de volgende M5-open, mee met de doorbraak | aan de andere kant van het niveau: niveau ∓ 6 pips / $2,50 (min. SL geldt) |

ADR-filter (alle varianten behalve V2): **geen nieuwe long als de koers ≥ 90% van de ADR boven de dag-low staat**
(spiegel voor short). V2 gebruikt juist dat moment.

## 2b. Verduidelijkingen (tijdens het bouwen, vóór de eerste run)
- **V3 klaarzetten:** bij een M5-close die 2–10 pips (goud $0,60–3,00) onder een rond niveau L ligt, terwijl de laagste
  low van de laatste 12 M5-candles ≥ 15 pips ($5) onder L lag en L vandaag nog niet geraakt is → sell limit op L − 1 pip
  ($0,30), geldig 12 M5-candles. Eén order per niveau per dag. Spiegel voor long.
- **V4 doorbraak:** de M5-close ligt ≥ 2 pips ($0,60) boven L, de vorige M5-close lag onder L, en het is de eerste
  close boven L vandaag. Spiegel voor short.
- **SL bij V3/V4:** het niveau ± 6 pips ($2,50) plus de spread op het moment van vullen (zoals elke KATSU-SL).
  Is de afstand tot de vulling kleiner dan het minimum, dan schuift de SL naar het minimum (geen weigering).
- **TP:** de dichtste van 1,5R en het ADR-niveau (ADR-high voor long, ADR-low voor short, berekend op het signaal).
  Ligt het ADR-niveau dichter dan 1R → geen trade. Een limiet/stop wordt geannuleerd als de geplande TP eerst
  geraakt wordt.
- **Sluiten:** om 23:45 server (22:45 Belgisch), vóór de rollover-spread; orders vervallen ook dan.
- **Placebo:** marktorder op de open van een M5-candle op hetzelfde uur en kwartier van een willekeurige andere
  handelsdag in dezelfde periode, zelfde richting, SL- en TP-afstand, zonder kosten.
- **Even maanden 2020–2024 = eindtest van deze spec** (besluit Gitchi 24 okt 2026). Een eventuele replay toetst zich
  vooruit op de demo.

## 3. Uitvoering
KATSU-motor (`katsu/execution.py`): M1-candles, ASK = BID + spread (met minimum), slippage op markt/stop/SL,
commissie, rollover-spread, bij twijfel binnen één M1-candle telt de SL. **Extra controle:** het aandeel trades
waarbij SL en TP in **dezelfde M1-candle** vallen. Boven 5% → de uitslag is onbetrouwbaar en is tick-data nodig.
Markten: **EURUSD en XAUUSD** (M1 van IC Markets 2020 – okt 2026, met tick-volume).

## 4. Testplan (vooraf vast)
- **Verkenning (de poort):** 2025 – 9 okt 2026 (Gitchi: de markt sinds 2025 telt) **en** de oneven maanden 2020–2024,
  apart gerapporteerd.
- Per variant en per markt: trades (per dag), winrate, gem. R netto, t (geclusterd per week), R zonder kosten,
  placebo zonder kosten (zelfde richting, SL- en TP-afstand, op hetzelfde kwartier van een willekeurige andere dag),
  per jaar, kosten in R, aandeel twijfel-candles.
- **Poort (alle voorwaarden):**
  1. ≥ 300 trades in 2025–26 (gemiddeld ±1 per handelsdag over beide markten — "dagelijks");
  2. gem. ≥ +0,10R netto in 2025–26, t ≥ 2,0 (lat bij 4 varianten √(2·ln 4) ≈ 1,7; 2,0 als minimum);
  3. zonder kosten beter dan de placebo;
  4. niet negatief op de oneven maanden 2020–2024 (de markt mag anders zijn, maar een echte edge mag daar niet
     duidelijk verliezen);
  5. twijfel-candles ≤ 5%.
- **Wat slaagt:** één eindtest op de **even maanden 2020–2024** (nog nooit bekeken), zelfde code, geen aanpassing.
  Daarna demo naast KATSU Live. Wat faalt: noteren, niet bijschaven.
- Niets van deze varianten komt in het bouwstenen-dashboard vóór de poort beslist is.

## 5. Nog open
- **Tick-data:** nodig als de twijfel-controle > 5% geeft. Gitchi kijkt in MT5 hoe ver de ticks teruggaan.
</content>
</invoke>
