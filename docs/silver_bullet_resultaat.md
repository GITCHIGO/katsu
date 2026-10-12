# KATSU — Silver Bullet (spec v0.5): resultaat

Datum: 12 oktober 2026 · Alleen de **verkenningshelft** · Testplan vooraf vastgelegd (spec v0.5, commit vóór de run).
Code: `katsu/silver.py` (tests: `tests/test_silver.py`), `scripts/silver_test.py`. Register: `research/register_silver_bullet.csv`.

## In één zin
**0 van 45 door de poort.** Met kosten zijn 37 van de 45 combinaties negatief; zonder kosten liggen ze rond nul
(21 van 45 positief, zoals bij toeval te verwachten).

## Gemiddeld per venster en filter (over markten en timeframes)
| | Met kosten | Zonder kosten |
|---|---|---|
| London (03–04 NY) | −0,12R | −0,12R |
| NY AM (10–11 NY) | −0,07R | +0,02R |
| NY PM (14–15 NY) | −0,19R | −0,02R |
| filter: alle | −0,13R | −0,06R |
| filter: sweep | −0,14R | +0,03R |
| filter: bias (H1) | −0,11R | −0,09R |

## Beste combinaties (geen enkele haalt de poort)
| Combinatie | Trades | Netto R | t | Zonder kosten |
|---|---|---|---|---|
| GBPUSD M15 NY PM bias | 43 | +0,13 | 0,7 | +0,06 |
| XAUUSD M5 London bias | 22 | +0,13 | 0,6 | −0,02 |
| EURUSD M5 NY PM bias | 28 | +0,10 | 0,4 | +0,10 |
| EURUSD M15 NY AM sweep | 75 | +0,08 | 0,6 | +0,17 |
| EURUSD M5 NY AM bias | 94 | +0,03 | 0,2 | +0,21 |
Allemaal te weinig trades en ver onder t = 2. Bij 45 pogingen zijn een paar uitschieters van ±0,2R normaal.

## Wat we leren
1. **Kosten wegen zwaar**: de SL binnen één uur is klein. Het kostenplafond (0,2R) schrapt veel setups
   (bv. goud M15 London: 180 trades zonder plafond, 40 met), en wat overblijft verliest gemiddeld 0,1–0,2R aan kosten.
2. **Het NY AM-venster** is het minst slecht (zonder kosten +0,02R gemiddeld), London en NY PM zijn negatief.
   Dat is een zwakke aanwijzing, geen voorsprong.
3. **Sweep vooraf** helpt zonder kosten een klein beetje (+0,03R), de H1-bias niet.
4. Bevestigt ronde 2 (smalle versie: bruto 0,00R). De Silver Bullet is op EURUSD, GBPUSD en goud geen edge.
