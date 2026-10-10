# KATSU

Systematisch tradingmodel op goud (XAUUSD), van nul opgebouwd.

Kernprincipes:
- **Eerst een spec, dan code.** Zie [`docs/spec_v0.1.md`](docs/spec_v0.1.md).
- **Meten op prijzen die je echt kon krijgen**: gesloten candles, spread, commissie, slippage.
- **Testplan vooraf vastgelegd**: kiezen op 2020–2024, één eindtest op 2025–2026.

Onderzoek dat tot de eerste spec leidde: [`docs/onderzoek_forexdetective.md`](docs/onderzoek_forexdetective.md).

## Status
- [x] Data-loader met controle (`katsu/data.py`)
- [x] Swings en trend zonder vooruitkijken (`katsu/structure.py`)
- [x] Sweep + CHoCH-detectie met tegenbeweging, trend M15/H1/H4/D1 gelogd (`katsu/signals.py`)
- [x] Uitvoering op M1: fills, SL/TP, kosten, 1 positie, dagstop (`katsu/execution.py`)
- [x] Backtest 2020–2024 in R — bouwsteen 1 (sweep + CHoCH) faalt, zie docs/stap4_resultaat_bouwsteen1.md
- [x] Bouwsteen 2: spec v0.2 goedgekeurd, BOS-detectie + tests, controlegrafieken
- [x] Bouwsteen 2: kostenplafond 0,2R, backtest 2020–2024 — faalt, zie docs/stap4_resultaat_bouwsteen2.md
- [x] Bouwsteen 3: spec v0.3 goedgekeurd, FVG-detectie + trendspotter (snel) + tests, controlegrafieken
- [x] Bouwsteen 3: backtest 2020–2024 — formeel faalt, maar M15 + H1/H4 toont voorsprong vóór kosten, zie docs/stap4_resultaat_bouwsteen3.md

## Tests draaien
```
pip install -r requirements.txt
python -m pytest
```
- [x] Fase 2, laag 1, ronde 1 (signaalonderzoek, 5 markten, M15/H1/H4, verkenningshelft): 615 combinaties, 0 door de poort — zie docs/ronde1_resultaat.md en research/register_ronde1.csv
