# KATSU — ronde 2: resultaat (ICT-tijdmodellen, trendvolgen, dips kopen)

Datum: 11 oktober 2026 · Alleen de verkenningshelft · Opzet vooraf vastgelegd in `onderzoeksplan_edge.md` §11.
Code: `katsu/ict.py`, `katsu/trend.py`, `scripts/ronde2.py` (tests: `tests/test_ict.py`, `tests/test_trend.py`). Register: `research/register_ronde2.csv`.

## In één zin
**81 combinaties, 0 door de poort.** Ook de ICT-modellen met hun eigen tijdvensters (London Judas, Silver Bullet, Monday range, dagbias, London close) doen niet beter dan een willekeurige trade op hetzelfde kwartier. Trendvolgen en dips kopen tonen hooguit zwakke, niet-significante aanwijzingen.

## A. ICT-tijdmodellen (1,5R, SL op de structuur, sluiten om 16:00 NY)
| Model | Trades (5 markten) | Winrate | Bruto R | Willekeurig, zelfde kwartier | 
|---|---|---|---|---|
| London Judas | 4.549 | 39% | −0,02 | −0,01 |
| Silver Bullet | 358 | 42% | 0,00 | −0,01 |
| Monday range | 1.299 | 42% | +0,03 | −0,01 |
| Dagbias-trade | 4.168 | 47% | +0,01 | −0,01 |
| London close | 1.711 | 46% | +0,03 | −0,01 |
- Bij 1,5R is quitte ~40% winrate; alle modellen zitten daar rond. Na kosten is alles negatief, bij de Judas sterk (−0,25 tot −0,94R), omdat de SL onder één M15-candle heel klein is en de kosten dan zwaar wegen.
- De filters uit het boek (smalle Azië-range, ma–wo, dagbias, SMT) verbeteren niets betrouwbaar; sommige maken het slechter (GBPUSD Judas met bias: t = −2,1).
- Beste losse aanwijzing: XAUUSD dagbias-trade, edge +0,10R t.o.v. willekeurig (t = 2,6), maar na kosten −0,02R. Silver Bullet met bias op GBPUSD: +0,65R, maar op 13 trades.

## B. Trendvolgen en dips kopen (D1, echte trades na kosten)
| Model | Trades (5 markten) | Bruto R | t (bruto) | Netto R |
|---|---|---|---|---|
| Donchian 20/10 | 383 | −0,06 | −0,7 | −0,25 |
| Donchian 55/20 | 202 | +0,12 | +0,7 | −0,17 |
| Dips RSI2 < 10 | 262 | +0,02 | +0,9 | −0,01 |
| Dips RSI2 < 5 | 128 | +0,04 | +1,1 | +0,01 |
- **US500 dips kopen** is het enige dat er goed uitziet: winrate 78%, +0,13R bruto, +0,10R netto (t = 1,9 bruto) — maar op 54 trades in de verkenningshelft. Te weinig om iets te besluiten; precies wat de literatuur verwacht, dus het verdient een vervolg met meer data (andere indexen).
- **Kanttekening swap:** voor trendvolgen (trades van 1–2 maanden) zat de swap-aanname (goud $0,40/oz per nacht in beide richtingen, EURUSD-shorts ook als kost) te zwaar voor 2010–2019, toen rentes en goudprijzen lager waren. Ook bruto is trendvolgen op deze 5 markten echter niet significant (55/20: +0,12R, t = 0,7).

## Totaalbeeld na ronde 1 en 2
- Getest: 615 + 615 (1,5R) + 6 (laag 2) + 81 = **1.317 combinaties** in het register, plus 48 in bouwsteen 1–3.
- Geen enkele haalt de poort. Het aantal "goede" resultaten ligt rond of onder wat toeval geeft.
- Bevestigingshelft en eindtest 2025–2026 blijven onaangeroerd.
