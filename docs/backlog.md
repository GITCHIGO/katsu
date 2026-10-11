# KATSU — backlog: ideeën die later apart getest worden

Laatst bijgewerkt: 9 oktober 2026. Niets hiervan wordt gebouwd zonder eigen spec. Elk idee wordt **apart** getest, met dezelfde uitvoerings- en testregels (placebo, zonder kosten, keuzeregel, 2025–2026 dicht).

## Soorten FVG (wens Gitchi, 9 okt 2026)
| Soort | Wat het is | Testbaar? |
|---|---|---|
| Continuation / trend-FVG | FVG met de trend mee | **Getest** in bouwsteen 3 (M15 + H1/H4 veelbelovend vóór kosten) |
| Reversal-FVG | Eerste FVG na een CHoCH/MSS | Grotendeels getest als entry B van bouwsteen 1 (faalde); kan nog als eigen setup |
| Inverse FVG (IFVG) | FVG die met een close doorbroken wordt en daarna van rol wisselt | Ja, duidelijk te definiëren |
| Exhaustion-FVG | FVG laat in een lange, steile trend | Ja, mits "lange trend" vooraf exact vastligt (bv. ≥ X ATR zonder pullback) |
| Common / range-FVG | FVG in een zijwaartse markt | Ja: FVG terwijl de trend NEUTRAL is (nu uitgesloten door de filter) |
| Island reversal / BPR | Twee tegengestelde FVG's die overlappen | Ja (balanced price range) |
| Consequent encroachment (CE) | 50% van de FVG als instap | Getest als entry B in bouwsteen 3 (slechter dan de rand) |
| "Professional vs novice" | Op basis van volume | Moeilijk: forex heeft geen centraal volume, alleen tickvolume (zwakke benadering) |

## Varianten van sweep, CHoCH en BOS
- **Sweep — soort liquiditeit:** gewone swing (getest), equal highs/lows, sessie-high/low (Azië-range, Londen), vorige dag/week high/low (PDH/PDL, PWH/PWL), ronde getallen. Interne vs externe liquiditeit.
- **CHoCH:** interne CHoCH (kleine structuur) vs swing-CHoCH (grote structuur); **MSS** = CHoCH met displacement (sterke candle, vaak met FVG).
- **BOS:** interne vs externe (swing) BOS; met of zonder displacement; breuk met body (getest) vs wick; "inducement" (een BOS die eigenlijk een sweep blijkt).
- Alle drie kunnen op een hogere timeframe (H1/H4) getest worden; tot nu toe enkel M5/M15.

## Andere genoteerde ideeën
- Grote FVG's op een hogere timeframe (H1/H4) met H4/D1 mee, meerdere dagen open (Gitchi, 9 okt 2026).
- Entry-verfijning op M1 na een signaal op een hogere timeframe.
- Dashboard met vangrails (alleen in-sample, eindtest op slot, teller van geprobeerde combinaties) en live monitoring.
- Echte swapwaarden uit MT5 (Specificatie) invullen i.p.v. de voorlopige.
- **Dips kopen op aandelenindexen** (wens Gitchi, 11 okt 2026, voor later): US500 gaf in ronde 2 het enige lichtpuntje (78% winrate, +0,10R netto, maar 54 trades). Later testen met D1/H1 van US30, NAS100, GER40, UK100.
- **ICT-boek, nog niet getest:** CBDR-projecties, NWOG/NDOG, OTE 62–79%, D1-swingbias met raid van candle 3, NY 07–09u retracement, breaker/mitigation/rejection blocks, IPDA 20/40/60 dagen, seizoenen (zie `ict_boek_samenvatting.md`).
- **Regels voor elke volgende spec:** maximale looptijd per trade; swap evenredig met prijs en periode in plaats van een vast bedrag.
