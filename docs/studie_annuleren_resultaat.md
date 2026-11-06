# KATSU — studie: Test #1 met en zonder de annuleerregel (6 nov 2026, ter info)

Vraag Gitchi: wat als limieten niet geannuleerd worden wanneer het TP-niveau eerst geraakt wordt? Zelfde code als de
vooruit-test en KATSU Live (`scripts/vooruittest.rows_for`, preset Test #1, één trade tegelijk), alleen
`cancel_price = None` in de variant. **Niets aan de live strategie veranderd** (besluit Gitchi).
Data: IC Markets M15 (EURUSD, GBPUSD, XAUUSD) t/m 9 okt 2026. Even maanden 2020–2024 niet gebruikt.

| Periode | Variant | Trades | Winrate | Per trade | Totaal | t |
|---|---|---|---|---|---|---|
| 2025 – 9 okt 2026 | met annuleren (live) | 154 | 56% | **+0,23R** | **+35,5R** | 2,6 |
| 2025 – 9 okt 2026 | zonder annuleren | 225 | 52% | +0,14R | +31,8R | 1,8 |
| 2010–2019 + oneven 2020–24 | met annuleren (live) | 1.071 | 41% | −0,14R | −151,8R | −4,0 |
| 2010–2019 + oneven 2020–24 | zonder annuleren | 1.582 | 42% | −0,14R | −220,7R | −4,7 |

(154 i.p.v. 149 trades zoals in het dashboard: het dashboard laat Gitchi's 6 screenshotdagen weg.)

## Conclusie
- De extra trades zonder annuleren (achteraf instappen nadat de beweging al gebeurde) verdienen niets: in 2025–26
  samen −3,7R, vóór 2025 −69R. De regel blijft zoals hij is.
- De vijf live geannuleerde limieten worden apart nagerekend zodra de M15-candles van de VPS binnenkomen.
