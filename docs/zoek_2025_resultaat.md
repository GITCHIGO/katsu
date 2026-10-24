# KATSU — resultaat spec v0.9: zoeken op 2025, controle op 2026 (24 okt 2026)

Spec: `docs/spec_v0.9_zoeken.md` (vastgelegd en gepusht vóór de run). Code: `scripts/zoek_2025.py`,
tests `tests/test_zoek_2025.py`. Data = rijen van het bouwstenen-dashboard (EURUSD, GBPUSD, XAUUSD; controle:
preset Test #1 op 2025–26 geeft exact 149 trades, +0,224R, zoals het dashboard). 2.255 combinaties geprobeerd.

## Uitslag: 0 van 4 kandidaten houdt stand in 2026

| Kandidaat | 2025 (gezocht) | 2026 (controle) | vóór 2025 |
|---|---|---|---|
| FVG (8 stappen) | 81 · +0,31R · t 5,8 | 57 · **−0,42R** · t −3,5 | 901 · −0,21R |
| IFVG (8 stappen) | 80 · +0,42R · t 7,8 | 50 · **−0,29R** · t −1,9 | 636 · −0,17R |
| AMD (3 stappen) | 83 · +0,36R · t 1,6 | 61 · **−0,05R** · t −0,2 | 862 · −0,13R |
| Zone (7 stappen) | 80 · +0,20R · t 1,7 | 59 · **−0,30R** · t −1,9 | 735 · −0,24R |

## Wat dit betekent
- Hoe harder er gezocht wordt, hoe mooier 2025 en hoe slechter 2026: de IFVG-kandidaat haalt t 7,8 op 2025 en
  verliest in 2026. De gekozen filters zijn toevallig ("niet om 5u, 15u en 17u", "alleen NFP-dagen"): ze beschrijven
  2025, niet een patroon.
- Dit is de klassieke overfitting die KATSU wil vermijden, nu zichtbaar gemaakt met één zuivere controle.
- Volgens de spec: niets bevroren, en niet opnieuw zoeken op 2025 met andere instellingen. De even maanden 2020–2024
  blijven onaangeroerd.

# v0.9b — zoeken op 2025 + 2026 samen (beide jaren positief), zonder losse uren

1.657 combinaties geprobeerd (incl. de eerste, mislukte run zonder stappen; zie de correctie in de spec).

| Kandidaat | 2025–26 (gezocht) | 2025 / 2026 | vóór 2025 (controle) |
|---|---|---|---|
| FVG (5 stappen) | 106 · +0,16R · t 1,2 | +0,16 / +0,17 | 571 · **−0,28R** · t −4,6 |
| IFVG (6 stappen) | 108 · +0,18R · t 1,5 | +0,19 / +0,16 | 535 · **−0,23R** · t −4,2 |
| AMD (5 stappen) | 102 · +0,26R · t 2,4 | +0,23 / +0,29 | 935 · **−0,19R** · t −5,9 |
| Zone (2 stappen) | 106 · −0,22R | negatief in beide | — (geen kandidaat) |

- FVG en IFVG kozen als eerste stap **"alleen NFP-dagen"** (22 dagen in 22 maanden): even toevallig als losse uren.
- AMD (variant C1-E2/C2-E2, volatiliteit niet normaal, H1 niet mee, gat ≥ 0,25 ATR, geplande RR < 2): positief in
  2025 én 2026, t 2,4 — en over 935 trades vóór 2025 −0,19R.
- **0 van 4 slaagt.** Positief in beide jaren is makkelijk te vinden als je ervoor zoekt; het zegt niets over
  data die het zoeken niet zag. Volgens de spec: niets bevroren, geen nieuwe zoekronde op 2025–26.
