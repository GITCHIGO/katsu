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
- [ ] Backtest-rapport in R

## Tests draaien
```
pip install -r requirements.txt
python -m pytest
```
