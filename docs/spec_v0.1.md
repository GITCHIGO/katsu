# KATSU — Spec v0.1: Sweep + CHoCH met de trend

**Status:** concept, vragen beantwoord; wacht op meer M1-historiek en definitieve goedkeuring. Er wordt niets gebouwd voor deze spec is goedgekeurd.
**Datum:** 9 oktober 2026

---

## 0. Wat ForexDetective goed en fout doet (achtergrond)

| Goed (nemen we mee als hypothese) | Fout (vermijden we) |
|---|---|
| Stapt vaak in na een **liquidity sweep** (stop-hunt) | Genoemde entry is bij posten al weg; resultaten gemeten op een prijs die niet te krijgen was |
| Trades **met de trend** werken bij hem duidelijk beter | Trades tegen een sterke beweging in ("vallend mes") zijn zijn zwakste |
| **Ochtend** (06–08u) en maandag/donderdag scoren het best | Verliezen onvolledig gerapporteerd (~50 SL-berichten tegenover ~162 echte) |
| Vaste structuur: SL, TP1–TP3 | Veel "second/third entries" = risico stapelen op één idee |
| | Order block, FVG en RSI-divergentie die hij noemt, zitten niet aantoonbaar bij zijn entries |

Bron: `claude/fase1_forexdetective_verificatie.md`.

---

## 1. Doel van deze eerste test
Eén vraag beantwoorden: **heeft "sweep + CHoCH met de trend" een edge na kosten, op data die niet gebruikt is om de regels te maken?**
Niet: zo veel mogelijk winst uit het verleden persen.

## 2. Markt en data
- **Twee markten met exact dezelfde regels: XAUUSD (goud) en EURUSD** (beslist 9 okt 2026).
- Geen aparte afstelling per markt. De variant wordt gekozen op 2020–2024 van beide markten samen.
- Een regel die op twee markten werkt is geloofwaardiger; de succescriteria (§8) gelden **per markt apart**. Live gaat alleen de markt die slaagt (vooraf vastgelegd, geen achteraf-keuze).
- **Data:** IC Markets MT5 M1, **2 jan 2020 – 6 okt 2026** (bid-prijzen, spread per minuut). Gecontroleerd 9 okt 2026: geen dubbele of onmogelijke candles; de enige gaten zijn kerst/nieuwjaar en marktsluitingen; identiek aan de eerdere export in de overlap.
- **Let op spread:** MT5 slaat per candle de *laagste* spread op. Bij EURUSD is die bijna altijd 0 (raw-account). De backtest gebruikt daarom een minimum: goud $0,10, EURUSD 0,1 pip, plus 1 tick slippage per uitvoering.

## 3. Definities (exact)

Alle berekeningen gebruiken **alleen gesloten candles**. Een swing telt pas als hij bevestigd is.

**Timeframes:** setup op **M5** (variant: M15). Trend op **H1**.

**Swing high / low:** een candle waarvan de high (low) strikt hoger (lager) is dan die van de L candles ervoor en de L erna. Bevestigd pas na sluiting van de L-de candle erna (geen repaint).
- L = 1 is de klassieke ICT "3-candle rule"; L = 3 filtert ruis op M5. Beide zijn een toegestane variant (zie §8).
- Gelijke highs/lows tellen niet als swing, maar als liquiditeitsniveau (equal highs/lows).

**Trend (H1):**
- Up: laatste twee bevestigde swing highs stijgend **en** laatste twee swing lows stijgend.
- Down: beide dalend.
- Anders neutraal → **geen trades**.
- De H1-swings gebruiken altijd **L = 3** (de L-varianten in §8 gelden voor de setup-timeframe).
- De trend wordt bepaald op het moment van het signaal, met alleen H1-candles die dan gesloten zijn.

**Liquidity sweep (long; short omgekeerd):**
- Een gesloten M5-candle waarvan de low **onder** de laatste bevestigde swing low komt (gevormd in de laatste 24 candles, en bevestigd vóór deze candle),
- op voorwaarde dat die swing low nog **intact** is: sinds zijn ontstaan heeft geen enkele candle eronder gesloten (een doorbroken niveau is geen liquiditeit meer),
- en die **boven** die swing low sluit.
- Sweep-low = de laagste low van de sweep.
- Wordt de swing low daarna met een **close** doorbroken, dan was het geen sweep maar een *liquidity run* → setup vervalt.
- Gelogd (geen filter): soort niveau (gewone swing, equal lows, vorige-weeklow) en de body van de reversal-candle (% van de range).

**Tegenbeweging vóór de sweep (toegevoegd 9 okt 2026, na visuele controle):**
- Een CHoCH is de breuk van de **bestaande** trend. Daarom moet de setup-timeframe vóór de sweep in een structuur **tegen** de H1-trend zitten.
- Long: laatste twee bevestigde swing highs dalend (lower high) **én** laatste twee swing lows dalend (lower low). Short omgekeerd.
- Zonder die tegenbeweging: geen setup.

**CHoCH (long; short omgekeerd):**
- Binnen 12 candles na de sweep sluit een M5-candle **met de body boven** de laatste bevestigde swing high die vóór de sweep lag, dus de laatste **lower high** (een wick alleen telt niet).
- Valt de koers eerst onder de sweep-low, dan vervalt de setup. Sluit die candle wel weer boven het niveau, dan is hij zelf een nieuwe sweep (met een diepere sweep-low).
- Sluit een candle onder het geveegde niveau vóór de CHoCH, dan is het een run → setup vervalt.

**Richting:** alleen longs in een H1-uptrend, alleen shorts in een H1-downtrend.

## 4. Entry, SL, TP

| | Variant A (basis) | Variant B |
|---|---|---|
| **Entry** | Marktorder op de open van de candle na de CHoCH-close | Limietorder op de bovenkant (long) / onderkant (short) van de eerste FVG in de CHoCH-beweging; geen FVG → 50% tussen sweep-low en CHoCH-close. 6 candles geldig, daarna geannuleerd |
| **SL** | Sweep-low − buffer (spread + 0,1 × ATR14 M5) | idem |
| **TP** | 2R vast | idem |

- **Minimale SL:** 1 × ATR14 M5 (anders te krap voor spread/ruis) → setup overslaan.
- **Maximale looptijd:** tot einde handelsdag (23:00 BE), dan sluiten op markt.
- Geen break-even en geen trailing in v0.1 (één ding tegelijk testen).

## 5. Uitvoering in de backtest (de fouten van GAMAN-X, nooit meer)
1. Entry op een prijs die echt bestond: **open van de volgende candle + spread** (buy) of open (sell).
2. SL en TP worden gecontroleerd op **M1-high/low**, niet alleen op de close.
3. Raakt één M1-candle zowel SL als TP → **SL telt** (conservatief).
4. **Kosten:** spread uit de data (met minimum, zie §2) + commissie €7 per lot round turn (bevestigd op echte goudtrade: −0,14 op 0,02 lot; raw-account) + slippage op elke markt- en stopuitvoering.
   - **Slippage (vastgelegd 9 okt 2026, vóór enig resultaat):** goud **$0,25** als basis, stresstest $0,10 en $0,50; EURUSD **0,3 pip** als basis, stresstest 0,1 en 0,6 pip. Succescriteria moeten gehaald worden bij de basis; bij de hoogste stresswaarde mag het resultaat niet negatief zijn.
   - Reden: 1 tick bleek te optimistisch. Op Gitchi's EURUSD-trades lag het echte SL-verlies mediaan ~1,4 pip boven het geplande (19 trades, demo, inclusief entryverschillen); op zijn enige echte goudtrade $1,19.
   - Na de demo wordt de slippage vervangen door de gemeten waarde.
5. Geen data van een ander instrument, geen fallbacks.
6. Exacte zelfde code voor backtest en later live.

## 6. Risico
- **1% per trade** (keuze Gitchi, eigen kapitaal), alles gerapporteerd in R.
- Let op: bij een rekening van €300 is de kleinste goudlot (0,01) met een SL van ~$6 al ≈ 1,7% risico. Echt 1% kan pas vanaf ~€550, of met een cent-account.
- **Maximaal 1 open trade per markt** (dus maximaal 2 tegelijk). Let op: goud en EURUSD reageren allebei op de dollar; bij gelijktijdige trades kan het risico samen 2% zijn.
- **Dagstop:** na −2R op een dag (beide markten samen) geen nieuwe trades meer.
- Geen prop firm gepland → geen prop-regels nodig.

## 7. Wat we loggen per setup (ook als hij niet getradeerd wordt)
Uur en dag (Brussel), sessie, ATR-percentiel, trendsterkte H1, sweepdiepte, tijd tussen sweep en CHoCH, SL-grootte, en of er ook een FVG/order block was.
- **Trend op M15, H1, H4 en D1** op het moment van het signaal (zelfde swing-definitie, L = 3; D1/H4 volgen de servertijd). Alleen gelogd, **geen filter** in v0.1. Blijkt een combinatie sterk, dan wordt die eerst als regel vastgelegd in een volgende spec en opnieuw getest.
Deze labels worden **niet** als filter gebruikt in v0.1, alleen gemeten.

## 8. Testplan (vooraf vastgelegd)
- **Als er oudere data komt:** in-sample = alles vóór 1 jan 2025; out-of-sample = 2025–2026.
- **Zonder oudere data:** in-sample = 2025; out-of-sample = 2026.
- Out-of-sample wordt **pas bekeken als de spec bevroren is**, en maar één keer.
- **Keuzeregel in-sample (vastgelegd 9 okt 2026, vóór de eerste backtest):** een variant komt in aanmerking als hij op 2020–2024, bij basis-slippage, op **beide markten** een positieve gemiddelde netto R heeft en per markt **minstens 100 trades**. Van die varianten wint de hoogste gemiddelde netto R over beide markten samen; bij gelijkspel de variant met meer trades. Komt geen enkele variant in aanmerking, dan faalt deze bouwsteen: geen eindtest, door naar bouwsteen 2 (BOS).
- **Toegestane varianten (8 in totaal, niet meer):** setup M5 of M15 × entry A of B × swinglengte L = 1 of L = 3.
- **Ochtend** (06–12u BE) wordt apart gerapporteerd, niet als filter gekozen.

**Succescriteria (out-of-sample, na kosten):**
- minstens 80 trades,
- gemiddeld ≥ +0,10R per trade,
- profit factor ≥ 1,2,
- max drawdown ≤ 10R,
- in-sample én out-of-sample allebei positief,
- naburige varianten ook positief (niet één toevallige topcombinatie).

Voldoet het niet → we noteren het, en gaan naar de volgende bouwsteen. Niet bijschaven tot het past.

## 9. Volgorde van bouwstenen (vooraf vastgelegd)
Elke bouwsteen wordt eerst **apart** getest als eigen entry-signaal, met dezelfde uitvoerings- en testregels. Pas wat zelfstandig slaagt, mag gecombineerd worden; elke combinatie moet zich opnieuw bewijzen op out-of-sample.
1. Sweep + CHoCH met de trend (deze spec, reversal na pullback)
2. **BOS-continuatie:** in een H1-trend sluit M5 met de body voorbij de laatste swing in trendrichting; entry op retest van het gebroken niveau of de FVG van de break
3. FVG-retest
4. Order block
5. Fibonacci 61,8–78,6%
6. RSI-divergentie

Faalt een bouwsteen: noteren en naar de volgende. Niet bijschaven tot het past.

## 10. Bronnen voor de definities
- BOS/CHoCH (close vereist, CHoCH = tegen de trend): theinnercircletraders.com/understanding-break-of-structure-and-change-of-character
- Sweep vs run (wick + close terug vs close erdoor): theinnercircletraders.com/ict-liquidity-sweep-vs-liquidity-run
- Swing 3-candle rule, bevestigd na sluiting: liquidityscan.io/blog/what-is-a-swing-high-and-swing-low-in-ict-the-3-candle-rule

## 11. Beslissingen (9 okt 2026)
1. **Markt:** goud én EURUSD, zelfde regels, criteria per markt (gewijzigd 9 okt 2026; was: goud primair). ✅
2. **Risico:** 1% per trade. ✅
3. **Prop firm:** nee, alleen eigen kapitaal. ✅
5. **Demo-account KATSU:** IC Markets Raw Spread, EUR, €5.000, hefboom 1:200 (gelijk aan live). Symboolnaam goud: `XAUUSD`.
4. **Historiek:** M1 vanaf 2 jan 2020 ontvangen en gecontroleerd. ✅ → in-sample 2020–2024, out-of-sample 2025–2026.
