# KATSU — spec v0.7: zones (supply & demand / order block) met limietorder (20 okt 2026)

Wens Gitchi: een strategie rond support & resistance, supply & demand, order blocks, FVG en SMC; zones op **H4, H1 en
M15**; instap met een **limietorder**; "maak er van wat je kan" (zone-kwaliteit). **Alleen 2025–2026** (besluit Gitchi
20 okt 2026: de markt sinds 2025 is anders; jaren daarvoor tellen niet). Vastgelegd vóór de eerste run.

## 1. Zone (LONG = demand; SHORT gespiegeld = supply), op de zone-timeframe TF ∈ {M15, H1, H4}
Alleen gesloten TF-candles; swings L = 3, pas geldig na bevestiging. ATR = ATR14 van TF.
- **Vertrek met structuurbreuk:** candle k sluit boven de laatste bevestigde, nog niet doorbroken swing high (eerste
  close erboven = BOS).
- **Oorsprong o:** de laagste low tussen die swing high en k.
- **Kracht:** close[k] − low[o] ≥ **2 × ATR**[k]. Anders geen zone.
- **Zone:** het order block = de laatste dalende candle (close < open) in o−2 … o; is er geen, dan candle o zelf.
  Bovenrand (proximaal) = high van die candle; onderrand (distaal) = low[o] (het laagste punt van de basis).
  Zone hoger dan 1,5 × ATR → geen zone (geen echte basis).
- **Imbalance (kenmerk, geen filter):** liet het vertrek een FVG achter (low c3 > high c1 tussen o en k)? Ja/nee.

## 2. Order
- Bekend op het einde van candle k; de limietorder staat vanaf dan.
- **Entry-variant E:** **rand** = op de bovenrand · **38,2** = 38,2% diep in de zone vanaf de bovenrand (Gitchi's regel).
- **SL:** onderrand − (spread + 0,1 × ATR). Geen minimum-SL.
- **TP:** de top van het vertrekbeen (hoogste high van o t/m k), maximaal 2R. Ligt die niet boven de vulling → geen trade.
- **Geldig** 7 kalenderdagen; geannuleerd als de TP eerst geraakt wordt. Eén order per zone (alleen de eerste terugkeer).
- Maximale looptijd van de trade: 14 kalenderdagen.
- **Bias-variant B:** **B0** geen · **B1** D1-trend (gesloten D1-candles) **mee**.

## 3. Uitvoering
KATSU-motor (`katsu/execution.py`), alle kosten. **EURUSD en XAUUSD op M1** (IC Markets M1, t/m 6 okt 2026);
**GBPUSD op M15** (geen M1 beschikbaar; SL telt bij twijfel). Elke zone apart gesimuleerd; daarnaast "één trade
tegelijk per markt" (zoals het dashboard).

## 4. Testplan (vooraf vast)
- Raster: TF {M15, H1, H4} × E {rand, 38,2} × B {B0, B1} = **12 varianten**, drie markten samen.
- Data: zones vanaf 1 jan 2025 (opwarming vanaf 2023), t/m de laatste data; zonder Gitchi's 6 screenshotdagen.
- Per variant: trades, winrate, gem. R netto, t (geclusterd per week), R zonder kosten, placebo zonder kosten
  (markt-order op hetzelfde kwartier van een willekeurige andere dag in 2025–26, zelfde SL/TP-afstand), per markt,
  **2025 en 2026 apart**, en "één tegelijk".
- **Poort:** n ≥ 100 (één tegelijk), gem. ≥ +0,10R, t ≥ 2,2 (lat bij 12 varianten √(2·ln 12) ≈ 2,2),
  positief in 2025 **én** 2026, zonder kosten beter dan de placebo.
- Wat slaagt, gaat **meteen vooruit**: maandelijks doorrekenen op nieuwe data vanaf 10 okt 2026. Er bestaat geen
  andere schone toets meer voor deze periode.
- Beschrijvend (geen filter): met/zonder FVG in het vertrek, long/short. Niets wordt na de run bijgesteld.

## 5. Uitslag v0.7 en versie v0.7b (20 okt 2026, vastgelegd vóór de run van v0.7b)
**v0.7: 0 van 12 door de poort** (register `research/register_zones.csv`). Mechanische zwakte gevonden: TP = top van het
vertrekbeen ligt bij het bekend worden van de zone vlak bij de koers, dus de order werd in 83% van de gevallen
geannuleerd omdat de TP eerst geraakt werd. Zo traedt Gitchi niet: een order block blijft geldig als de koers eerst
nog een nieuwe high maakt.
**v0.7b** (enige wijzigingen, rest gelijk):
- Geen annulering meer; de limietorder staat 7 kalenderdagen.
- **TP = de hoogste high (LONG) van het vertrekbeen t/m de laatste afgesloten uitvoeringscandle vóór de vulling**
  (de oude high vlak vóór de terugkeer; bekend op het moment van vullen), maximaal 2R.
- Zelfde 12 varianten en poort, maar de lat stijgt: 24 varianten in totaal → t ≥ 2,5.
