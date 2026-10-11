# KATSU — ronde 3: resultaat (resterende bouwstenen)

Datum: 11 oktober 2026 · Alleen de verkenningshelft · Opzet vooraf vastgelegd in `onderzoeksplan_edge.md` §12.
Code: `katsu/blocks.py`, `scripts/ronde3.py`, `scripts/laag2_ronde3.py` (tests: `tests/test_blocks.py`). Registers: `research/register_ronde3.csv`, `research/register_laag2_ronde3.csv`.
Ook nieuw in de uitvoering (met tests): maximale looptijd per trade, swap als % van de prijs, stoporders.

## In één zin
**435 combinaties; 2 haalden de poort van laag 1 — allebei "omgekeerd" — en geen van beide overleeft laag 2 met de echte regels.**

## Laag 1 per bouwsteen (hoofdmaat 1,5R; quitte zonder kosten bij 40% winrate)
| Bouwsteen | Tests | Beter dan willekeurig (t ≥ 2) | Slechter (t ≤ −2) | Winrate M15 / H1 / H4 |
|---|---|---|---|---|
| Order block | 135 | 0 | 14 | 37,5 / 37,5 / 37,4% |
| Fibonacci 61,8% | 90 | 2 | 16 | 37,0 / 35,3 / 37,1% |
| Fibonacci 70,5% | 45 | 0 | 7 | 37,9 / 35,2 / 37,4% |
| RSI-divergentie | 90 | 3 | 3 | 38,8 / 39,3 / 39,5% |
| BPR | 15 | 2 | 1 | 38,4 / 39,8 / 38,3% |
| Exhaustion-FVG | 15 | 1 | 2 | 39,8 / 37,3 / 37,0% |
| Range-FVG | 15 | 1 | 3 | 37,8 / 39,8 / 40,1% |
| Equal highs/lows | 30 | 2 | 2 | 39,5 / 38,7 / 46,4% (H4: weinig trades) |
- **Order block en Fibonacci doen het systematisch slechter dan willekeurig** (30+ keer t ≤ −2, nul keer t ≥ 2 voor OB). Wie na een BOS koopt op de terugloop naar het OB of naar 61,8–70,5%, koopt vooral in bewegingen die verder doorzakken.
- **RSI-divergentie** is het minst slecht (winrate rond 39%), maar ook niet significant.

## Laag 2 voor de 2 kandidaten (omgekeerde trade, echte regels)
De poort liet US500 · Fibonacci 70,5% (H1 L3 en H4 L1) door in de *omgekeerde* richting: na een bullish BOS en een terugloop tot 70,5% zakt de koers vaker verder. Getest als sell-stop op het niveau, SL voorbij de top van het been, TP 1,5R, kosten, maximale looptijd.
| Kandidaat | Trades | Winrate | Gem. netto R | t | vóór 2020 | 2020–24 |
|---|---|---|---|---|---|---|
| US500 H1 Fib 70,5 L3, omgekeerd | 99 | 37% | −0,14 | −1,1 | −0,13 | −0,15 |
| US500 H4 Fib 70,5 L1, omgekeerd | 86 | 48% | +0,12 | +0,9 | +0,03 | +0,25 |
Geen van beide haalt de poort (H1 negatief; H4 te weinig trades en niet significant).

## Totaalbeeld na drie rondes
- Getest: 1.317 (ronde 1–2) + 435 + 2 = **1.754 combinaties**, plus 48 in bouwsteen 1–3. Alles staat in de registers.
- Alle bouwstenen uit de oorspronkelijke spec (sweep, CHoCH, BOS, FVG, order block, Fibonacci, RSI-divergentie) zijn nu getest, ook de varianten en de extra FVG-soorten, op 5 markten en M15/H1/H4.
- **Geen enkele bouwsteen geeft op zichzelf een edge die de kosten overleeft.** Bevestigingshelft en eindtest 2025–2026 blijven onaangeroerd.
