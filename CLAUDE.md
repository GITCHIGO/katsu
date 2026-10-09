# KATSU — werkregels voor elke Claude-sessie in deze repo

Eigenaar: Gitchi. Communiceer in het Nederlands. Gitchi kan code niet zelf controleren: leg elke wijziging in gewone taal uit, en lever tests mee.

## Rol
- Wees kritisch en spreek tegen als iets niet klopt. Stel vragen vóór het bouwen.
- Denk actief mee over wat ontbreekt of beter kan.

## Vaste regels (lessen uit GAMAN en GAMAN-X — nooit meer)
1. Eerst de spec (`docs/spec_v*.md`), dan code. Wat niet in de spec staat, wordt niet gebouwd.
2. Eén markt, één strategie tegelijk.
3. Backtest en live gebruiken dezelfde code.
4. Realistische fills: alleen gesloten candles, entry op een prijs die echt bestond, spread (met minimum) + commissie + slippage, SL/TP gecontroleerd op M1-high/low, bij twijfel binnen één M1-candle telt SL. Nooit data van een ander instrument als fallback.
5. Verificatie: de eerste 20 live/demo-trades lijn per lijn vergelijken met MT5. Onder 90% overeenkomst: niets verder bouwen.
6. Alles in R, vast risico per trade (1%), dagstop −2R.
7. Testplan ligt vooraf vast. Out-of-sample (2025–2026) wordt maar één keer bekeken, nadat de spec bevroren is.
8. Log alles: context, geblokkeerde signalen, echte broker-resultaten.
9. Elke wijziging komt met tests (`pytest`); alle tests moeten slagen.

## Structuur
- `katsu/` — de code (data, structuur, signalen, uitvoering)
- `tests/` — tests met vooraf met de hand uitgerekende scenario's
- `docs/` — spec en onderzoek
- `data/` — koersdata (niet in git)
