# KATSU — Spec v0.3: FVG-retest met de hogere timeframes mee (bouwsteen 3)

**Status:** CONCEPT — wacht op goedkeuring van Gitchi. Er wordt niets gebouwd voor deze spec is goedgekeurd.
**Datum:** 9 oktober 2026
**Vorige bouwstenen:** v0.1 sweep + CHoCH (faalt, ≈ willekeurig), v0.2 BOS-continuatie (faalt, iets slechter dan willekeurig). Zie `docs/stap4_resultaat_bouwsteen1.md` en `…2.md`.

---

## 1. Doel
Eén vraag: **heeft instappen op de retest van een FVG, alleen als de hogere timeframes in dezelfde richting wijzen, een edge na kosten?**
Wens van Gitchi (9 okt 2026): een bullish FVG alleen nemen als de hogere timeframes ook bullish zijn (short gespiegeld).

## 2. Wat gelijk blijft aan v0.1/v0.2 (niet opnieuw te beslissen)
- Goud en EURUSD, exact dezelfde regels, criteria per markt.
- Data, uitvoering, kosten, slippage-plan, M1-controle, SL bij twijfel, TP als limiet, einde handelsdag 23:00 BE.
- 1% risico, alles in R, max 1 positie (of lopende order) per markt, dagstop −2R over beide markten samen.
- **Minimale SL 1 × ATR14 en kostenplafond 0,2R** (v0.2 §4). Krappe SL's worden overgeslagen.
- Trenddefinitie: laatste twee bevestigde swing highs én lows stijgend = UP, dalend = DOWN, anders NEUTRAL; L = 3; alleen gesloten candles.
- Standaard in het rapport: zonder kosten + placebo (v0.2 §6). Eerst controlegrafieken, dan backtest.

## 3. Trendspotter (24/7)
- Het systeem berekent **na elke gesloten candle** de trend op **M15, H1, H4 en D1**, per markt, met de bestaande code (`katsu.signals.multi_tf_trend`).
- In de backtest gebeurt dat op elk signaalmoment; in de live-engine (stap 6) draait dezelfde code continu, wordt elke wijziging gelogd en komt de stand op het dashboard.
- In deze bouwsteen is de trendspotter voor het eerst ook een **filter** (§4). Voor de andere bouwstenen blijft hij alleen meten.

## 4. Definities (long; short is exact gespiegeld)

**Bullish FVG:** drie opeenvolgende gesloten candles op de setup-timeframe (M5 of M15) waarbij de **low van candle 3 hoger ligt dan de high van candle 1**. De gap loopt van high candle 1 (onderkant) tot low candle 3 (bovenkant).
- Het signaal bestaat pas op het einde van candle 3.

**Trendfilter (variant, zie §6) — afgestemd op hoe lang de trade loopt:**
- Onze trades zijn intraday (snelle FVG's, uiterlijk dicht om 23:00 BE). Daarom kijkt de filter naar de timeframes **net boven** de setup, niet naar D1 (opmerking Gitchi 9 okt 2026: H4/D1 horen bij grote FVG's die je lang aanhoudt).
- **T0 (basis):** alleen H1 UP, zoals in bouwsteen 1 en 2.
- **T+ (afgestemd):** de twee timeframes direct boven de setup allebei UP.
  - M5-setup: **M15 en H1** UP.
  - M15-setup: **H1 en H4** UP.
- D1 is geen filter; hij wordt wel gelogd.
- Gemeten op het einde van candle 3, met alleen candles die dan gesloten zijn. Anders geen setup.

**Elke FVG geeft maar één order.**

## 5. Entry, SL, TP

| | Variant A: rand | Variant B: midden |
|---|---|---|
| **Entry** | Limiet op de **bovenkant** van de gap (eerste aanraking) | Limiet op het **midden** van de gap (50%, ICT "consequent encroachment") |
| **Geldig** | 12 candles na het signaal | idem |
| **SL** | Laagste low van de drie FVG-candles − buffer (spread + 0,1 × ATR14) | idem |
| **TP** | 2R vast | idem |

- Minimale SL 1 × ATR14 en kostenplafond 0,2R → anders overslaan (gelogd).
- Geen break-even, geen trailing.

## 6. Varianten (8, niet meer)
Setup-timeframe **M5 of M15** × entry **A of B** × trendfilter **T0 of T+**.
(De swinglengte L speelt hier geen rol: een FVG heeft geen swings nodig. Die plek gaat naar de trendfilter, zodat we rechtstreeks meten of de extra timeframe iets toevoegt bovenop H1.)

Verwachte aantallen 2020–2024 (geteld vóór de retest, de 1-positie-regel en het kostenplafond, met SL ≥ 1 ATR), per jaar:
- goud M5: T0 ~3.100, T+ ~910 · goud M15: T+ ~290
- EURUSD M5: T0 ~3.440, T+ ~1.010 · EURUSD M15: T+ ~340
Omdat er maar 1 positie per markt tegelijk mag lopen, wordt maar een deel daarvan echt getradeerd.

## 7. Testplan
Identiek aan v0.2 §6: alleen 2020–2024, dezelfde keuzeregel en succescriteria, 2025–2026 blijft dicht.

## 8. Wat we bewust niet doen
- Geen combinatie met sweep of BOS (die faalden apart; combineren mag pas met bouwstenen die apart slagen).
- Geen minimumgrootte voor de FVG buiten de minimale SL en het kostenplafond.
- Geen hogere timeframe als setup (H1/H4) in deze bouwsteen. Dat idee staat genoteerd voor later (beslissing Gitchi: eerst alle bouwstenen testen, daarna kijken hoe verder).
  - Genoteerd idee: **grote FVG's op een hogere timeframe die meerdere dagen open blijven, met H4/D1 mee als filter.** Pas als eigen spec, na de bouwstenen.

## 9. Bronnen
- FVG (3-candle imbalance), consequent encroachment = 50% van de gap: theinnercircletraders.com (ICT fair value gap)
