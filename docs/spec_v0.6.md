# KATSU — spec v0.6: AMD / Power of 3 als bouwsteen (13 okt 2026)

Aanvraag Gitchi: online onderzoek naar AMD en er een bouwsteen van maken. Vastgelegd **vóór** de eerste run.

## 1. Wat AMD is (samenvatting van de bronnen)
AMD = **Accumulation – Manipulation – Distribution** ("Power of 3", ICT; afgeleid van Wyckoff). Een periode (meestal
de dag) verloopt rond haar **openingsprijs** in drie fasen:
1. **Accumulatie** — Azië: smalle range rond de open, stops verzamelen zich boven en onder.
2. **Manipulatie** ("Judas swing") — rond de Londen-open (ICT: ±02:00–05:00 New York) een snelle beweging door één kant
   van de range en onder/boven de **midnight open** (00:00 New York), die stops pakt en dan stokt.
3. **Distributie** — de echte beweging terug door de open en naar de liquiditeit aan de overkant ("the draw"),
   tot in de close van de dag.
Bullish dag: opent dicht bij de low, wick onder de open, sluit dicht bij de high. Bearish: gespiegeld.
Handelsregels in de bronnen: niet in de range kopen; wachten op de sweep + **terugkeer** (terug in de range, terug
boven de open, of een MSS/CHoCH), instappen op de retracement (FVG/OB) of meteen; SL voorbij het sweep-extreem;
TP aan de overkant van de range (of de high/low van gisteren). Bias van de hogere timeframe.
Alle bronnen noemen het patroon **beschrijvend, niet mechanisch**; geen enkele bron geeft een controleerbare test
(één affiliate-site claimt ±69% winrate zonder methode).

## 2. Mechanische versie (servertijd = New York + 7 u; Belgische tijd = server − 1 u)
Markten EURUSD, GBPUSD, XAUUSD · M15 · alleen gesloten candles · per markt per dag hoogstens **één** setup.
- **Azië-range:** high/low van de candles 02:00–06:45 server (NY 19:00–23:59). Minstens 16 candles, anders geen dag.
- **Midnight open (MO):** open van de candle 07:00 server (NY 00:00). Ontbreekt die: geen dag.
- **Manipulatievenster:** candles 07:00–11:45 server (NY 00:00–05:00, BE ±06:00–11:00).
- **Sweep long:** een candle in het venster met low < Azië-low **én** low < MO. Short gespiegeld (high > Azië-high én > MO).
- **Bevestiging** (variant C), op een candle ná of gelijk aan de sweep-candle, binnen het venster:
  - **C1 "terug in range":** close > Azië-low (long) / < Azië-high (short).
  - **C2 "terug over de open":** close > MO (long) / < MO (short).
  De eerste bevestigde kant van de dag telt; bevestigen beide kanten op dezelfde candle → geen setup.
- **Manipulatie-extreem:** laagste low (long) van 07:00 t/m de bevestigingscandle.
- **Entry** (variant E):
  - **E1 markt:** op de open van de candle na de bevestiging.
  - **E2 FVG:** de laatste bullish FVG (low c3 > high c1) met c1 ná of op de extreem-candle en c3 t/m de
    bevestigingscandle; limiet **38,2% diep** vanaf de bovenrand (Gitchi's regel). Geldig tot 18:00 server
    (NY 11:00), geannuleerd als de TP eerst geraakt wordt. Geen FVG → geen trade.
- **SL:** manipulatie-extreem − (spread + 0,1 × ATR14 M15). Geen minimum-SL, geen kostenplafond.
- **TP:** de **overkant van de Azië-range** (Azië-high bij long). Ligt die niet voorbij de vulling → geen trade.
- **Exit:** uiterlijk op de dagclose, 00:00 server (NY 17:00), op de close.
- **Bias** (variant B): **B0** geen · **B1** D1-trend (trendspotter, gesloten D1-candles) **mee** met de richting.
- Kosten en uitvoering: de vaste KATSU-motor (`katsu/execution.py`), M15 als uitvoeringscandle, SL telt bij twijfel.

## 3. Testplan (vooraf vast)
- **Hoofdraster:** C ∈ {C1, C2} × E ∈ {E1, E2} × B ∈ {B0, B1} = **8 varianten**, elk over de drie markten samen.
- **Data:** verkenningsdata = FX 2010–2019, goud 2016–2019, oneven maanden 2020–2024 **en** 2025 – 9 okt 2026
  (verkenning sinds besluit 12 okt). Rapport apart: **vóór 2025** en **2025–26**. Even maanden 2020–2024 blijven dicht.
- **Per variant:** trades, winrate, gem. R netto, t (geclusterd per week), R zonder kosten, placebo zonder kosten
  (markt-order op hetzelfde kwartier van een willekeurige andere dag, zelfde SL- en TP-afstand, zelfde dagclose),
  per markt, per periode.
- **Poort (kandidaat om te bevriezen):** n ≥ 100, gem. ≥ +0,10R, t ≥ 2,0 (bij 8 varianten is de toevalslat
  √(2·ln 8) ≈ 2,0), positief **vóór 2025 én in 2025–26**, zonder kosten beter dan de placebo.
- **Beschrijvend (de premisse zelf):** hoe vaak valt de low/high van de dag in het manipulatievenster; en sluit de dag
  na een long-setup (C2) vaker boven de MO dan een gewone dag.
- Niets wordt na het zien van de resultaten bijgesteld. Ideeën die eruit volgen, zijn een nieuwe spec.
