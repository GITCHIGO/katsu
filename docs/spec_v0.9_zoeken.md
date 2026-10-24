# KATSU — spec v0.9: automatisch zoeken op 2025, controle op 2026 (24 okt 2026, wens Gitchi)

Wens Gitchi: "doe er enkele op 2025 en test die op 2026". Een computer zoekt combinaties zoals Gitchi in het
bouwstenen-dashboard klikt, maar **alleen op 2025**. Januari – 9 oktober 2026 dient als controle die het zoeken nooit
ziet. Vastgelegd vóór de eerste zoekstap.

## 1. Data
- Exact de rijen van het bouwstenen-dashboard (`KATSU Bouwstenen`: zelfde setups, kenmerken, kosten, uitvoering op
  M15, "één trade tegelijk per markt"). Markten **EURUSD, GBPUSD, XAUUSD** (zilver en US500 niet, besluit 21 okt).
- **Zoekdata:** signalen in 2025. **Controle:** signalen 1 jan – 9 okt 2026. **Achtergrond:** de dashboard-data vóór
  2025 (2010–2019 en oneven maanden 2020–2024) — alleen gerapporteerd, nooit gebruikt om te kiezen.

## 2. Zoekregel (vast)
- Vertrek: één soort setup (FVG, IFVG, AMD, Zone) op de drie markten. Dat geeft **4 zoektochten**.
- Elke stap: probeer elke mogelijke "chip uit" (één waarde van één kenmerk weglaten, behalve markt en "onbekend"),
  en ook één markt weglaten. Kies de stap met de **hoogste t-waarde op 2025** (geclusterd per week), mits er daarna
  nog **≥ 80 trades in 2025** zijn. Stop als geen enkele stap de t verhoogt, of na **8 stappen**.
- Resultaat: per zoektocht één combinatie = **4 kandidaten**. Elke geprobeerde combinatie wordt geteld.

## 3. Controle op 2026 (één keer, geen aanpassing daarna)
Een kandidaat **slaagt** als in 2026: ≥ 30 trades, gemiddeld ≥ +0,10R na kosten, zonder kosten beter dan de placebo.
De achtergrond (vóór 2025) mag niet duidelijk negatief zijn (gem. > −0,05R); dat staat erbij ter info en als
tweede voorwaarde.

## 4. Wat daarna
- Slaagt er een: bevriezen, met één eindtest op de even maanden 2020–2024 (nog nooit bekeken; spec v0.8 haalde
  de poort niet, dus die zijn nog vrij). Daarna demo, naast de drie bevroren setups.
- Slaagt er geen: noteren. Niet opnieuw zoeken op 2025 met andere instellingen (dan wordt 2026 ook zoekdata).

## v0.9b — zoeken op 2025 + 2026 samen, zonder losse uren (24 okt 2026, wens Gitchi)
Wens Gitchi: "combinaties die positief waren in 2025 en 2026, maar niet met uren werken" (een sessie als "nacht"
mag wel, een los uur niet). Vastgelegd vóór de run.
- **Zoekdata:** 2025 én 1 jan – 9 okt 2026 samen. Het kenmerk **"uur" is uitgesloten**; sessie, Silver Bullet-venster
  en weekdag blijven mogelijk.
- **Zoekregel:** zoals §2 (greedy "chip uit", max. 8 stappen, 4 zoektochten FVG/IFVG/AMD/Zone), op de hoogste t over
  2025–26, met als voorwaarden ≥ 100 trades samen, ≥ 40 per jaar, en **gemiddeld positief in 2025 én in 2026**.
- **Controle (nooit gezien tijdens het zoeken):** de dashboard-data vóór 2025 (2010–2019 en oneven maanden
  2020–2024). Een kandidaat slaagt als hij daar ≥ 100 trades heeft en gemiddeld **≥ 0R** na kosten, en zonder kosten
  beter dan de placebo. Wat slaagt → eindtest even maanden 2020–2024 (één keer), daarna demo.
- Wat faalt: noteren; geen nieuwe zoekronde op 2025–26.
