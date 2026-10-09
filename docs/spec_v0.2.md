# KATSU — Spec v0.2: BOS-continuatie (bouwsteen 2)

**Status:** GOEDGEKEURD door Gitchi op 9 okt 2026 (voorstellen §9 aanvaard). Volgende stap: bouwen + controlegrafieken.
**Datum:** 9 oktober 2026
**Vorige bouwsteen:** v0.1 (sweep + CHoCH) faalde op 2020–2024, ook zonder kosten niet beter dan willekeurig instappen. Zie `docs/stap4_resultaat_bouwsteen1.md`.

---

## 1. Doel
Eén vraag: **heeft instappen *mee* met de trend, na een breuk van de structuur (BOS), een edge na kosten?**
Bouwsteen 1 was een ommekeer (tegenbeweging → sweep → CHoCH). Deze bouwsteen is het omgekeerde idee: de trend loopt al, de koers maakt een nieuwe top (long) en we stappen in bij de terugval.

## 2. Wat gelijk blijft aan v0.1 (niet opnieuw te beslissen)
- Markten: **goud en EURUSD, exact dezelfde regels**, criteria per markt (v0.1 §2).
- Data, uitvoering, kosten en slippage-plan (v0.1 §2 en §5): M1-controle, SL bij twijfel, gap-regel, TP als limiet, basis-slippage $0,25 / 0,3 pip met stresstest.
- Risico (v0.1 §6): 1% per trade, alles in R, max 1 positie per markt, dagstop −2R over beide markten samen, einde handelsdag 23:00 BE.
- Swing-definitie (strikt, L candles links en rechts, pas bevestigd na sluiting) en **H1-trend met L = 3** als richtingsfilter.
- Logging (v0.1 §7): uur, dag, sessie, ATR-percentiel, trend M15/H1/H4/D1, enz. Alleen meten, geen filter.

## 3. Definities (long; short is exact gespiegeld)

**H1-trend:** UP (laatste twee H1-swing highs én lows stijgend). Alleen longs in UP, alleen shorts in DOWN, geen trades bij NEUTRAL.

**Structuur op de setup-timeframe (M5 of M15) moet óók mee zijn:**
- Op het moment vóór de breuk: laatste twee bevestigde swing highs stijgend **en** laatste twee swing lows stijgend (HH + HL).
- Reden: breekt de koers een top terwijl de setup-timeframe nog daalt, dan is dat een CHoCH (bouwsteen 1), geen BOS. Zo overlappen de twee bouwstenen niet.

**Het niveau:** de laatste bevestigde swing high, op voorwaarde dat hij nog **intact** is (sinds zijn ontstaan heeft geen candle erboven gesloten). Elk niveau kan maar één keer een BOS geven.

**BOS:** een gesloten candle sluit **met de body boven** dat niveau. Een wick erboven telt niet.
- Signaaltijd = einde van de BOS-candle.

**Higher low (HL):** de laatste bevestigde swing low vóór de BOS-candle. Dat is het punt waar het idee "de trend loopt door" fout blijkt → basis voor de SL.

## 4. Entry, SL, TP

| | Variant A: retest | Variant B: meteen mee |
|---|---|---|
| **Entry** | Limietorder op het **gebroken niveau** (de oude top wordt steun). Geldig **12 candles** na het signaal, daarna geannuleerd | **Marktorder** op de open van de candle na de BOS |
| **SL** | HL − buffer (spread + 0,1 × ATR14 setup-timeframe) | idem |
| **TP** | 2R vast | idem |

- **Minimale SL:** 1 × ATR14 → anders overslaan (zelfde als v0.1).
- **Kostenplafond (toegevoegd 9 okt 2026, na de controlegrafieken en vóór enig backtestresultaat):** sla een setup over als de verwachte kosten meer dan **0,2R** zijn.
  - Verwachte kosten = spread (met minimum) + 2 × slippage (in en uit) + commissie, in prijs.
  - R = afstand tussen geplande entry (marktorder: open + spread + slippage; limiet: de limietprijs) en de SL, bepaald met de spread op het signaalmoment. Alles is bekend vóór de order vertrekt, dus live werkt het identiek.
  - Reden: in een rustige markt is de SL klein maar blijven de kosten gelijk (controlegrafiek #3: SL ≈ $3, kosten ≈ $0,78 ≈ 0,26R). Gitchi wil sowieso geen krappe SL.
  - Overgeslagen setups worden gelogd met status `kosten_te_hoog`.
- Geen break-even, geen trailing.

## 5. Varianten (8, niet meer)
Setup-timeframe M5 of M15 × entry A of B × swinglengte L = 1 of L = 3. Zelfde opbouw als v0.1, zodat de resultaten vergelijkbaar zijn.

## 6. Testplan (vooraf vastgelegd)
- **Alleen in-sample 2020–2024.** 2025–2026 blijft dicht tot een variant de keuzeregel haalt en de spec bevroren is.
- **Keuzeregel:** dezelfde als v0.1 §8 (positief op beide markten bij basis-slippage, ≥ 100 trades per markt, hoogste gemiddelde netto R wint; geen kandidaat = bouwsteen faalt → bouwsteen 3).
- **Succescriteria op out-of-sample:** dezelfde als v0.1 §8 (≥ 80 trades, ≥ +0,10R, PF ≥ 1,2, max DD ≤ 10R, naburige varianten positief, hoogste stress niet negatief).
- **Nieuw, standaard in elk rapport:**
  1. dezelfde setups **zonder kosten** (is er een voorsprong vóór kosten?);
  2. een **placebo**: willekeurige instapmomenten en richting met dezelfde SL-grootte en dezelfde motor. Een variant die niet duidelijk beter doet dan de placebo, heeft geen edge, ook als hij toevallig positief is.
- **Eerst controlegrafieken** (12 willekeurige in-sample setups) en jouw oordeel, pas daarna de backtest.

## 7. Wat we bewust niet doen
- **Geen FVG in deze bouwsteen.** FVG-retest is bouwsteen 3 en wordt daar apart getest. Mengen we het hier, dan weten we achteraf niet wat er werkte. (Dit wijkt af van de korte beschrijving in v0.1 §9; beslist 9 okt 2026.)
- Geen filters uit het v0.1-rapport (sessie, H4/D1). Die zijn niet bewezen.
- Geen afstelling van TP, venster of buffer per markt.

## 8. Bronnen
- BOS = close voorbij de vorige swing in trendrichting; CHoCH = breuk tegen de trend: theinnercircletraders.com/understanding-break-of-structure-and-change-of-character
- Breakout-pullback-continuation (breuk met een close, retest van het niveau, ongeldig bij close terug in de range): luxalgo.com/library/concept/breakout-pullback-continuation

## 9. Beslissingen (9 okt 2026)
1. **Variant B = marktorder** direct na de BOS (niet de FVG-retest). ✅
2. **Retest-limiet geldig 12 candles** (1 uur op M5, 3 uur op M15). ✅
3. **Kostenplafond 0,2R** (zie §4), vóór de backtest toegevoegd. ✅
