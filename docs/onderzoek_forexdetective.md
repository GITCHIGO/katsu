# Fase 1 — Verificatie ForexDetective-signalen (XAUUSD, jan 2025 – okt 2026)

**Datum analyse:** 8 oktober 2026
**Bronnen:** Telegram-export "FOREX DETECTIVE PREMIUM" (9.027 berichten, sept 2021 – okt 2026), IC Markets MT5 M1-data XAUUSD en EURUSD (2 jan 2025 – 6 okt 2026).

## Wat getest is
- 574 signalen met Stop Loss sinds 2025 op goud of EURUSD. Na het herstellen van duidelijke typfouten (bv. SL 3454 i.p.v. 3354, verkeerde richting) blijven **538 bruikbare goudsignalen** over. EURUSD: slechts 8 signalen, zonder entryprijs, niet getest.
- Typisch signaal: entry, SL op ~$5–6 (≈ 50–60 "pips"), TP1 op ~1R, TP2 op ~2R, TP3 op ~3R. 386 eerste entries, 116 "second/third entry".
- Tijdsuitlijning: Telegram-tijd + 1 uur = MT5-servertijd (gecontroleerd per maand; in de DST-overgangsweken +2u).
- Kosten: echte spread uit de M1-data + commissie $7/lot round turn. Bij twijfel binnen één M1-candle (SL en TP tegelijk) telt SL.

## Resultaten (gemiddelde R per trade, na kosten)

| Scenario | Trades | Winrate | Alles op TP1 | Half TP1 + BE → TP2 | Alles op TP2 |
|---|---|---|---|---|---|
| **Zijn genoemde entry, gevuld bij posten** (= wat hij rapporteert) | 538 | 70% | **+0,28R** | +0,33R | +0,35R |
| Marktorder direct bij posten | 481 | 67% | −0,01R | −0,01R | +0,01R |
| Marktorder 1 min na posten | 462 | 65% | +0,00R | +0,01R | +0,03R |
| Limietorder op zijn entry (60 min geldig) | 456 (82 niet gevuld) | 54% | −0,02R | +0,00R | −0,01R |

## Kernbevindingen
1. **Zijn genoemde entry is op het moment van posten al niet meer beschikbaar.** De koers staat bij posten mediaan **$1,3–1,5 (≈ 0,2R) verder** in de richting van de trade. Bij 57–76 signalen stond de koers bij posten zelfs al voorbij TP1 of SL.
2. **Die 0,2R is precies zijn hele edge.** Op zijn eigen prijs: +0,28 tot +0,35R per trade. Als volger (markt- of limietorder): ≈ 0R. Na kosten is volgen dus break-even, met de variantie van ~500 trades.
3. **Hij rapporteert verliezen onvolledig.** Sinds 2025: ~230 berichten over TP-hits, ~50 over SL-hits, terwijl zelfs zijn eigen prijzen ~162 SL-hits vóór TP1 opleveren.
4. **2026 is zwakker dan 2025** (marktentry, TP2-variant: +0,12R in 2025, −0,17R in 2026).
5. De analyse-posts met patronen (kanalen, wedges, Elliott, FVG) bevatten geen niveaus of richting in de tekst; die zijn hier niet getoetst.

## Aanvulling: is zijn 70% winrate een setup-edge of alleen voorsprong?
Vraag van Gitchi: los van het te laat instappen, heeft zijn *methode* een edge?

Test: bij posten staat de koers gemiddeld **0,30R** voorbij zijn entry. Bij TP1 ≈ 1R en SL = 1R geeft een willekeurige koersbeweging met die voorsprong al een winkans van (1+h)/(1+a).

| | Puur door voorsprong (toeval) | Werkelijk |
|---|---|---|
| Winrate | 70,1% | 69,9% |
| Gem. R (zonder kosten) | +0,298R | +0,295R |
| **Edge bovenop voorsprong** | | **−0,003R** (95%-interval −0,07 tot +0,06) |

**Zijn volledige winrate wordt verklaard door de beweging vóór hij post.** Vanaf het moment van posten voorspellen zijn signalen niets meer dan toeval.

Twee mogelijke verklaringen, met deze data niet te onderscheiden:
1. Zijn setup triggert echt op de genoemde prijs en hij post gewoon laat. Dan kan een model dat de setup zelf herkent die voorsprong wél pakken.
2. Hij post pas als de koers al zijn kant op beweegt, en noemt dan de eerdere prijs (selectie achteraf). Dan bestaat de edge niet; de setups die meteen tegen hem in gingen zien we nooit.

Waarschuwingssignaal voor verklaring 2: een echte setup houdt meestal nog wat edge ná de trigger. Hier is die exact nul.

**Gevolg:** de enige eerlijke manier om zijn methode te beoordelen is zijn setups zelf als regels te coderen en te backtesten op onze M1-data. Zo zien we ook de setups die hij niet postte.

## Conclusie voor KATSU
- **Zijn signalen kopiëren geeft geen aantoonbare edge.** KATSU niet bouwen als copy-model van zijn signalen.
- Zijn *concepten* (FVG, BOS/CHoCH, liquiditeit, Fibonacci, RSI-divergentie, correctiepatronen) kunnen nog steeds bouwstenen zijn, maar moeten **systematisch op onze eigen data** bewezen worden, met realistische fills.
- Les voor elke strategie: **meet altijd op de prijs die je echt kon krijgen**, niet op de prijs die genoemd wordt.

## Beperkingen
- Telegram-tijden op de seconde, koersdata per minuut: entry op de open van de eerstvolgende minuut.
- Maximale looptijd 5 dagen; daarna slotkoers.
- Typfouten automatisch hersteld (±100 op SL/TP, richting); 13 signalen onherstelbaar, uitgesloten.

## Patronen in zijn signalen (positieve aanname: gevuld op zijn eigen entry)
Gem. R bij uitstap op TP1, 538 goudsignalen. "Boven toeval" = resultaat min wat de voorsprong bij posten alleen al verklaart.

- **Uur (Brussel):** best 06–08u (74%, +0,39R) en 18–20u (77%, +0,40R); zwakst 09–14u (65%, +0,20–0,23R).
- **Dag:** maandag (79%, +0,46R) en donderdag (74%, +0,36R) best; dinsdag, woensdag, vrijdag zwakst (64–65%, +0,15–0,20R).
- **Richting:** buys 74% / +0,35R vs sells 64% / +0,19R — waarschijnlijk vooral de sterke goud-uptrend 2025–26.
- **Bouwstenen** (laatste goud-analysepost ≤12u vóór het signaal, 255 gekoppeld): best order block, RSI-divergentie, CHoCH (+0,30–0,37R); zwakst driehoek, demand/supply, FVG, Fibonacci, kanaal (+0,08–0,19R).
- Geen enkele groep ligt duidelijk boven toeval (alles binnen ±0,15R, steekproeven te klein). Dit zijn hypotheses voor de backtest, geen bewezen regels.

## Reverse engineering: wat zit er echt op de grafiek bij zijn entries?
Op elk van zijn 540 instapmomenten (laatste minuut dat de koers op zijn entry stond, mediaan 1,1 min vóór posten) gemeten op M5, M15 en H1, vergeleken met 1.500 willekeurige momenten op dezelfde uren.

| Kenmerk | Bij hem | Toeval | Significant? |
|---|---|---|---|
| Liquidity sweep (wick door laatste swing, close terug) M5 | 24% | 17% | ja (z=3,3) |
| Liquidity sweep M15 | 21% | 15% | ja (z=3,0) |
| CHoCH M15 | 18% | 14% | grensgeval (z=2,0) |
| Order block (M5/M15/H1, 2 varianten) | 8–31% | 7–30% | nee |
| FVG (M5/M15/H1) | 29% | 28–29% | nee |
| RSI-divergentie (M5/M15/H1) | 4–5% | 3–4% | nee |
| BOS (M5/M15/H1) | 14–19% | 16–19% | nee |
| Ronde prijs ($5-veelvoud) | 22% | 20% | nee |

Binnen zijn trades: met de trend van de laatste 3 uur (M15) +0,35–0,41R; tegen een sterke beweging in +0,10R (−0,20R boven toeval). Kopen bij lage RSI (vallend mes) is zijn zwakste groep.

**Conclusie:** met standaarddefinities is zijn setup op de grafiek nauwelijks terug te vinden. Alleen een liquidity sweep (en mogelijk CHoCH) komt duidelijk vaker voor dan toeval. Order blocks, FVG's en RSI-divergentie zitten niet vaker bij zijn entries dan bij willekeurige momenten. Zijn methode is dus ofwel discretionair (patronen op hogere timeframes die we niet meten), ofwel minder systematisch dan zijn analyse-posts suggereren.

**Kandidaat voor de eerste KATSU-spec (hypothese, nog te backtesten):** liquidity sweep + CHoCH op M5/M15, in de richting van de trend op hoger tijdsframe, met nadruk op de ochtend.
