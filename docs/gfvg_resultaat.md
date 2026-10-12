# KATSU — Gitchi-FVG (spec v0.4): resultaat

Datum: 12 oktober 2026 · Alleen de **verkenningshelft** (FX 2010–2019, goud feb 2016–2019, plus oneven maanden
2020–2024). Bevestigingshelft en eindtest 2025–2026: **niet bekeken**. Testplan vooraf vastgelegd in spec v0.4 §10
(commit vóór de run). Code: `katsu/gfvg.py`, `scripts/gfvg_test.py` (tests: `tests/test_gfvg.py`).
Register: `research/register_gfvg.csv` (24 combinaties).

## In één zin
**0 van 24 door de poort.** Met kosten zijn alle varianten negatief behalve één kleine (+0,02R, 120 trades, t = 0,2);
zonder enige kosten liggen ze tussen −0,23R en 0,00R. Gitchi's FVG-regels geven op zichzelf geen voorsprong.

## Netto R per trade (met alle kosten) — trades tussen haakjes; geldigheid "tot ongeldig"
| Markt | 38,2% · zonder trend | 61,8% · zonder trend | 38,2% · H1+H4 mee | 61,8% · H1+H4 mee |
|---|---|---|---|---|
| EURUSD | −0,13 (1803) | −0,10 (1407) | −0,10 (157) | +0,02 (120) |
| GBPUSD | −0,15 (1748) | −0,20 (1412) | −0,13 (174) | −0,21 (142) |
| XAUUSD | −0,12 (415) | −0,15 (305) | −0,21 (32) | −0,36 (21) |
"Max 24 uur" geeft bijna dezelfde cijfers (de meeste orders worden binnen een dag gevuld of geannuleerd).

## Zonder enige kosten (geen spread, slippage, commissie, swap; geen kostenplafond)
| Markt | 38,2% · zonder trend | 61,8% · zonder trend | 38,2% · mee | 61,8% · mee |
|---|---|---|---|---|
| EURUSD | −0,04 | −0,00 | −0,18 | −0,09 |
| GBPUSD | −0,03 | −0,05 | −0,01 | −0,04 |
| XAUUSD | −0,01 | −0,06 | −0,08 | −0,18 |

## Wat we leren
1. **Winrate 34–42% bij een gemiddelde geplande RR van 1,5–1,7.** Quitte zonder kosten ligt bij ~38–40%: precies
   waar de winrate uitkomt. Het patroon gedraagt zich als toeval.
2. **38,2% tegenover 61,8% diep:** geen vaste winnaar. Dieper (61,8%) wordt minder vaak gevuld (≈46% tegenover 56%);
   op EURUSD iets beter, op GBPUSD en goud slechter.
3. **De trendspotter helpt niet consequent** (zonder kosten zelfs slechter op EURUSD en goud).
4. **Ongeveer de helft van de orders wordt geannuleerd** omdat de koers eerst het doel raakt zonder retest.
5. Consistent met ronde 1–3: na een breuk op M15 is er geen voorsprong in "mee met de breuk instappen op de retest".

## Kanttekening
De regels zijn een benadering van Gitchi's beoordeling. Wat zijn "gevoel" extra filtert (context, marktmoment,
welke FVG "sterk" is) zit er niet in. Dat kan alleen eerlijk gemeten worden door zijn eigen beslissingen vooraf
vast te leggen (bv. een demo-logboek met screenshots vóór de uitkomst), niet door de regels verder bij te schaven
op deze data.

## Aanvulling: welke instapdiepte is het voordeligst? (vraag Gitchi, 12 okt 2026)
Elke setup apart gesimuleerd met entry op 0%, 10%, …, 100% diep in het gat (zonder trendvoorwaarde, geldig tot
ongeldig). Script `scripts/gfvg_entrydiepte.py`, register `research/register_gfvg_entrydiepte.csv` (33 extra pogingen).
| Diepte | EURUSD zonder kosten | GBPUSD zonder kosten | Goud zonder kosten | Vulgraad (gem.) | Winrate EURUSD |
|---|---|---|---|---|---|
| 0% (rand) | −0,050 | −0,025 | −0,031 | 69% | 44% |
| 20% | −0,053 | −0,018 | −0,045 | 63% | 41% |
| 40% | −0,035 | −0,025 | −0,029 | 56% | 39% |
| 50% | −0,014 | −0,038 | −0,053 | 52% | 39% |
| 60% | −0,005 | −0,055 | −0,078 | 47% | 38% |
| 80% | −0,025 | −0,052 | −0,058 | 36% | 38% |
| 100% (verre rand) | −0,032 | −0,043 | −0,085 | 25% | 37% |
Met kosten: op elke diepte en elke markt negatief (EURUSD −0,08 tot −0,14R, GBPUSD −0,13 tot −0,20R, goud −0,07 tot −0,23R).
**Geen enkele diepte is winstgevend, ook niet zonder kosten.** Dieper instappen verbetert de RR, maar de winrate
zakt in dezelfde mate (de diepe retests zijn vaker de trades die doorlopen tot de SL). De "beste" diepte verschilt
per markt (EURUSD 60%, GBPUSD 20%, goud 0–40%) en ligt binnen het toeval rond nul.
