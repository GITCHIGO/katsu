# KATSU — spec: dashboard met bouwstenen (12 okt 2026)

> **v3 (zelfde dag):** Gitchi kiest zelf de periode, ook vóór 2025 (zie §9). Even maanden 2020–2024 blijven eruit.
> **Besluit Gitchi, 12 okt 2026 (v2):** het dashboard toont **alleen 2025 – 9 okt 2026** (zonder zijn 6 screenshotdagen),
> niets ervoor. Daarmee is 2025–2026 vanaf nu **verkenningsdata** (werkregel 7 aangepast). Bewijs voor een bevroren
> combinatie komt van de **even maanden 2020–2024** (nooit bekeken) en daarna van een demo. §1 en de split
> "vóór 2020 / 2020–24" hieronder gelden voor v1 (verkenningshelft) en blijven als script-optie bestaan.

Doel: Gitchi kan bouwstenen (setups en filters) vrij combineren en ziet meteen hoe die combinatie het deed op de
**verkenningsdata**. Het dashboard is om ideeën te **zoeken**; bewijs komt alleen van de **bevestigingshelft**
(even maanden 2020–2024, nooit bekeken), en daarna van een demo.

## 1. Data
EURUSD, GBPUSD, XAUUSD · M15 · verkenningshelft (FX 2010–2019, goud feb 2016–2019, + oneven maanden 2020–2024).
Uitvoering op M15-candles (M1 bestaat pas vanaf 2020), met alle kosten. Elke setup wordt **apart** gesimuleerd
(geen portefeuille: overlappende setups tellen allemaal mee). Tijden in Belgische tijd (server − 1 u).

## 2. Soorten setups (LONG; SHORT gespiegeld)
| Soort | Definitie | Signaal |
|---|---|---|
| **FVG** | elke bullish FVG: low(candle 3) > high(candle 1). **"FVG na breuk"** = filter *breuk* ≠ geen: de middelste candle sluit voorbij de laatste bevestigde, intacte swing high (L = 3), zoals spec v0.4 | einde candle 3 |
| **IFVG** | een bearish FVG waar binnen 48 candles een candle **boven** sluit (boven de bovenrand van het gat): het gat wordt steun → long | einde van die candle |
Sweep+CHoCH, BOS, enz. zijn **filters** op deze setups (zie §4), geen aparte soorten.

## 3. Uitstap (jouw regels, voor alle soorten gelijk)
- Entry: limiet op **38,2% diep** in het gat (vanaf de rand die de koers eerst raakt). Geldig tot ongeldig:
  vangnet 5 handelsdagen; geannuleerd als de TP eerst geraakt wordt.
- SL-basis: FVG met breuk = laagste low van het order block (laatste tegengestelde candle tussen de oorsprong van het
  been en candle 1) t/m candle 2 (spec v0.4). FVG zonder breuk = laagste low van de laatste tegengestelde candle
  binnen 10 candles vóór candle 1 t/m candle 2 (geen: candle 1–2). IFVG = laagste low
  tussen candle 1 van de oorspronkelijke FVG en de omkeer-candle. Buffer spread + 0,1 ATR. **Geen** minimum-SL en
  **geen** kostenplafond: de SL-grootte en de kosten zijn filters.
- TP: laagste ongeraakte swing high (L = 3) boven de top van de beweging, maximaal 2R; geen: 2R.
- Maximale looptijd 14 kalenderdagen.

## 4. Kenmerken (filters) — alleen wat op het signaalmoment bekend is
| Groep | Kenmerk | Waarden |
|---|---|---|
| Basis | markt, soort, richting | |
| Structuur | breuk | geen / BOS (M15-trend al mee) / CHoCH (M15-trend tegen) / breuk uit neutraal |
| | sweep vooraf (20 candles vóór candle 1) | swing-low geveegd (wick eronder, close erboven) ja/nee |
| | sweep vorige dag / Azië | low van gisteren / van de Azië-sessie (01–08 BE) vandaag geveegd vóór het signaal: ja/nee |
| | order block | tegengestelde candle binnen 10 candles vóór candle 1: ja/nee |
| | FVG-nummer | eerste / tweede / derde+ FVG in dezelfde richting binnen 20 candles |
| Trend | M15, H1, H4, D1 | mee / tegen / neutraal (trendspotter, alleen gesloten candles) |
| | premium/discount | entry in de goedkope helft van de range van gisteren (long) = "mee", anders "tegen" |
| Tijd | sessie | Azië 01–08 · Londen 08–13 · overlap 13–17 · New York 17–22 · nacht 22–01 (BE) |
| | uur, weekdag | |
| | Silver Bullet-venster | 09–10 / 16–17 / 20–21 BE: ja/nee |
| Vorm & markt | grootte gat (× ATR) | < 0,25 · 0,25–0,5 · 0,5–1 · 1–2 · > 2 |
| | displacement (body candle 2 × ATR) | < 0,5 · 0,5–1 · 1–2 · > 2 |
| | candle 3 vol | body/range < 25% · 25–50% · ≥ 50% |
| | SL (× ATR) | < 1 · 1–2 · 2–3 · > 3 |
| | geplande RR | < 1 · 1–1,5 · 1,5–2 · 2 |
| | kosten (R) | < 0,1 · 0,1–0,2 · > 0,2 |
| | volatiliteit | ATR t.o.v. mediaan van 20 dagen: laag (< 0,8) · normaal · hoog (> 1,25) |
| | NFP-dag | eerste vrijdag van de maand: ja/nee (andere nieuwsdata later) |

## 5. Uitkomst per setup
gevuld of niet · TP/SL/max. duur · netto R · netto pips · R zonder kosten · duur.
**Vergelijkingstrade (placebo):** dezelfde richting, SL- en TP-afstand, op hetzelfde uur van een willekeurige andere
dag (zelfde markt, verkenningsdata), als markt-order. Zo zie je of een filter beter doet dan "gewoon op dat uur traden".

## 6. Wat het dashboard toont
Aantal (gevuld), winrate, gem. R netto, gem. pips per markt, R zonder kosten, placebo, t (geclusterd per week),
curve (cumulatieve R), per jaar, vóór 2020 vs 2020–24, en een uitsplitsing "per waarde" voor elk kenmerk.

## 7. Vangrails
- **Pogingenteller:** elke nieuwe filtercombinatie die je bekijkt, telt (bewaard). Het dashboard toont de lat:
  bij N pogingen is een toevalstreffer van t ≈ √(2·ln N) normaal; pas wat daar ruim boven ligt, is interessant.
- **Bevriezen:** maximaal **3** combinaties. Een bevroren combinatie wordt door Claude één keer getest op de
  bevestigingshelft (zelfde regels, met portefeuille: één positie per markt, dagstop). Alleen die uitslag telt.
  Poort: n ≥ 100, gem. netto ≥ +0,10R, t ≥ 2,0, positief in 2020–22 én 2023–24.
- 2025–2026 wordt niet gebruikt.

## 8. v2: lotgrootte en één trade tegelijk (12 okt 2026)
- **Eenheid:** $ bij vast lot per pair (standaard EURUSD 0,10 · GBPUSD 0,10 · goud 0,02; in te stellen, onthouden in
  de browser) of R. $ = netto pips × 10 $ × lot; zonder kosten en placebo: R × SL-afstand in pips × 10 $ × lot.
- **Eén trade tegelijk per markt** (standaard aan, benadering): op volgorde van vulling telt een trade alleen als de
  vorige in dezelfde markt gesloten is. Zonder dit vinkje tellen alle overlappende setups (totalen dan onrealistisch).
- Kerncijfers erbij: totaal over de periode en grootste daling (top tot dal). Oordeel: positief in **elk jaar**
  (2025 en 2026, elk ≥ 20 trades). Grafiek per maand i.p.v. per jaar. Pogingenteller opnieuw vanaf 0
  (`teller/pogingen_2025`), omdat het nieuwe data is.
- Rekenregels in Python: `katsu/dashboard_calc.py` (tests `tests/test_dashboard_calc.py`); de pagina geeft exact
  dezelfde cijfers (alles, $ één tegelijk: 5 000 trades, −1,99 $ per trade, totaal −9 943 $, t −3,81).
- Data: `python -m scripts.dashboard_build <htf> <uit> 2025` → `dashboard_events_2025.pkl`.

## 9. v3: zelf de periode kiezen (12 okt 2026, wens Gitchi)
- Data = verkenningshelft (FX 2010–2019, goud 2016–2019, oneven maanden 2020–2024) **+** 2025 – 9 okt 2026.
  De **even maanden 2020–2024 zitten er niet in** (schoon voor de bevestiging van bevroren combinaties).
- Van–tot per maand (standaard 2025-01 tot laatste maand) en snelkeuzes "2025–26", "vóór 2025", "alles".
  Een setup hoort bij de maand van zijn signaal (1 minuut terug: een signaal om 00:00 hoort bij de maand ervoor).
- Oordeel: positief in **beide helften** van de gekozen periode (elk ≥ 20 trades) en
  **"buiten je periode"**: dezelfde filters op alle andere beschikbare data. Is die met ≥ 100 trades niet positief,
  dan krijgt de combinatie "alleen hier" i.p.v. "kandidaat".
- Grafiek per maand tot 36 maanden, daarna per jaar. Een andere periode dan de standaard telt als aparte poging.
- Gecontroleerd tegen Python: combinatie #21 (GBPUSD+goud, IFVG, geen sweep, eerste FVG, M15 tegen, H1 tegen/neutraal),
  één tegelijk: 2025–26 85 trades +0,156R; buiten = 419 trades −0,233R (t −4,04); alles 504 trades −0,167R;
  2016–2019 176 trades −0,371R.
- Export: `python -m scripts.dashboard_export <uit> dashboard_events_verkenning.pkl dashboard_events_2025.pkl`.

## 10. Publicatie en controle v1 (12 okt 2026)
Pagina `dashboard/page.html`; data met `python -m scripts.dashboard_build` → `dashboard_events.pkl`, daarna
`python -m scripts.dashboard_export <pkl> <map>/data` (base64 gzip-JSON per markt). Gepubliceerd als artifact
"KATSU Bouwstenen" met db-opslag: `teller/pogingen` (bekeken combinaties) en `bevroren/<id>` (max. 3).
Controle: de pagina geeft exact dezelfde cijfers als Python op `dashboard_events.pkl`
(alles: 179 996 gevulde trades, −0,200R, zonder kosten −0,062R, placebo zonder kosten −0,021R;
FVG + BOS: 5 917 trades, −0,228R).

## 11. AMD in het dashboard (13 okt 2026, wens Gitchi)
- **Soort "AMD"** (spec v0.6), 4 versies als filter "AMD-versie": C1/C2 (terug in range / terug over de midnight open)
  × E1/E2 (markt / FVG 38,2%). Geen bias in de setup: gebruik de filter Trend D1. **Eigen uitstap:** TP = overkant
  van de Azië-range (geen plafond), SL voorbij het manipulatie-extreem, sluiten op de dagclose (NY 17:00).
  Kenmerken die niet bestaan voor AMD staan op "n.v.t." (breuk, sweep swing, order block, FVG-nummer) of "onbekend"
  (displacement, candle 3; gat × ATR alleen bij E2). Geplande RR "≥2" (bij FVG/IFVG betekent dat precies 2).
- **Kenmerk "AMD-dag"** op alle setups: was er eerder die serverdag (op of vóór het signaal) een bevestigde AMD-beweging
  volgens C2? mee / tegen / geen. AMD-setups zelf: mee.
- Code: `katsu/amd.py` (`amd_day_map`, `amd_day_labels`, test in `tests/test_amd.py`), `scripts/dashboard_amd.py`.
  Export: `python -m scripts.dashboard_export <uit> dashboard_events_verkenning.pkl dashboard_events_2025.pkl
  dashboard_amd_verkenning.pkl dashboard_amd_2025.pkl`.
- Gecontroleerd tegen Python (alle periodes, alle trades): AMD C2-E1 5 179 trades −0,169R; met D1 mee 1 521 −0,116R;
  FVG met AMD-dag mee 23 014 −0,207R, tegen 21 119 −0,193R, geen 71 404 −0,222R.

## 12. Zones in het dashboard (20 okt 2026, wens Gitchi)
- **Soort "Zone"** = spec v0.7b (supply/demand-zone = order block na een vertrek ≥ 2 × ATR met BOS; limietorder 7 dagen,
  geen annulering; SL voorbij de zone; TP = oude high vlak vóór de vulling, max 2R; max. looptijd 14 dagen).
  Filters: **Zone-timeframe** (M15/H1/H4), **Zone-instap** (rand / 38,2% diep), **Zone: FVG in het vertrek** (ja/nee).
  Andere soorten staan daar op "n.v.t.". Order block = "ja"; breuk, sweep swing, FVG-nummer = "n.v.t.";
  gat/displacement/candle 3 = "onbekend". SL (× ATR) en geplande RR gebruiken de ATR en het vertrekbeen van de
  zone-timeframe; trends, sessie, sweeps, volatiliteit en AMD-dag op de laatste gesloten M15-candle.
- Uitvoering op **M15** (zoals de andere soorten); de aparte zones-test liep voor EURUSD en goud op M1 — kleine
  verschillen zijn normaal (H1 rand + D1 mee: 305 trades −0,021R hier, 306 trades −0,003R op M1).
- Beide periodes (verkenning en 2025–26), zodat "buiten je periode" werkt.
- Code: `scripts/dashboard_zones.py`. Export: zes pkl's (events, amd, zones × verkenning/2025).
- Gecontroleerd tegen Python: Zone H1 rand D1 mee 2025–26, één tegelijk: 305 trades, −0,021R.

## 13. Zilver, US500, presets en gsm-versie (21 okt 2026, wens Gitchi)
- **Markten erbij: XAGUSD en US500**, met alle soorten (FVG/IFVG, AMD, Zone) en beide periodes (vanaf feb 2016).
  Kosten zoals in ronde 1 (zilver: min. spread 0,010 · slippage 0,005 · commissie 0,002 · swap 0,005/nacht) en
  ronde 3 (US500: min. spread 0,30 · slippage 0,25 · swap 3%/jaar). Instrumenten in `scripts/dashboard_build.py`
  (`EXTRA_INS`); de bestaande markten veranderen niet.
- **$ per pip per lot:** EURUSD/GBPUSD/goud 10 $, zilver 50 $ (pip 0,01 × 5 000 oz), US500 1 $ per punt (aanname:
  contract 1; controleren in MT5 → Specificatie). Standaard-lot: zilver 0,02, US500 1,00.
- **Presets** (knoppen bovenaan): Test #1 (FVG) · AMD-extra (#386) · Zone GBPUSD. Een preset zet alle filters en de
  oorspronkelijke markten, periode 2025–26 en "één tegelijk"; de markten kun je daarna vrij aan/uit zetten
  (rij "Markten"). Elke andere combinatie telt zoals altijd als poging.
- **Gsm:** filters achter de knop "Filters (n)" (volledig scherm, "Toon resultaat" om terug te gaan), grotere knopjes,
  kerncijfers in 2 kolommen. **Lang drukken** op een knopje = "alleen deze" (op de computer: Alt-klik).
- Data per markt een eigen bestand (5 bestanden, ±15 MB samen): op gsm het liefst via wifi openen.
