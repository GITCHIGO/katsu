# KATSU — resultaat spec v0.8: intraday met vector candles, ADR en ronde getallen (24 okt 2026)

Spec: `docs/spec_v0.8.md` (vooraf vastgelegd, akkoord Gitchi). Code: `katsu/scalp.py`, `scripts/scalp_test.py`,
tests `tests/test_scalp.py`. EURUSD + XAUUSD, M5-signalen, uitvoering op M1, alle kosten, intraday (dicht 22:45 BE),
één trade tegelijk per variant per markt. Even maanden 2020–2024 **niet aangeraakt**.

## Uitslag: 0 van 4 varianten haalt de poort

| Variant | 2025–26: trades | win | gem. R | t | zonder kosten | placebo z.k. | oneven 2020–24: gem. R (n) |
|---|---|---|---|---|---|---|---|
| V1 vector-recovery | 3.712 | 39% | −0,14 | −7,0 | −0,01 | −0,02 | −0,15 (5.534) |
| V2 vector aan ADR-uiterste | 516 | 40% | −0,09 | −1,6 | +0,04 | −0,04 | −0,20 (697) |
| V3 kering aan rond getal | 403 | 38% | −0,15 | −2,4 | −0,00 | −0,05 | −0,20 (592) |
| V4 doorbraak rond getal | 2.467 | 38% | −0,11 | −4,1 | +0,01 | +0,02 | −0,18 (1.856) |

Elke variant is negatief op beide markten en in elk jaar (2020–2026). Twijfel binnen één M1-candle ≤ 0,2%: de
M1-uitvoering is hier betrouwbaar, tick-data is niet nodig.

## Wat dit betekent
- **Zonder kosten liggen alle vier rond 0** (−0,01 tot +0,04R), even goed als een willekeurige trade op hetzelfde uur.
  Het probleem zijn niet de kosten: de signalen zelf voorspellen niets. Met kosten (spread, slippage, commissie) wordt
  het −0,1 à −0,2R per trade.
- **Vector candles op tick-volume:** een candle met veel volume zegt niets over de volgende beweging, mee of tegen.
- **Ronde getallen (Osler 2003):** het effect uit de orderboeken van 1999–2000 is in 2020–2026 op M5 niet bruikbaar,
  niet als kering en niet als doorbraak.
- **ADR als filter/plafond** kon de varianten niet redden.

## Handcontrole
- V3 EURUSD 16-01-2025: close 1.02901 (9,9 pips onder 1.0300), laagste low uur ervoor 1.0282 (18 pips) → sell limit
  1.0299, SL 1.0306 + spread = 1.03061, TP 1,5R = 1.02883; gevuld 09:15, TP 10:33 (low 1.02879). Klopt.
- V4 EURUSD 10-01-2025: close 1.03035 ≥ 1.0300 + 2 pips → marktorder 1.03039, SL 1.02939, TP 1.03189; low daarna
  1.02414 → SL, −1,11R. Klopt.

Bestanden: `katsu_research/scalp/scalp_resultaat.json`, `scalp_trades.pkl`.
