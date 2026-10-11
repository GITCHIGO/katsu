# ICT-boek: wat er precies testbaar in staat

Bron: *Unlocking Success in ICT 2022 Mentorship — The Full ICT Day Trading Model* (LumiTraders, 2023, 407 blz.), aangeleverd door Gitchi op 11 okt 2026. Samenvatting gemaakt voor KATSU ronde 2.

## Algemeen
- Een samenvatting van ICT-concepten door derden, geschreven voor futures (ES/NQ); afstanden staan in indexpunten.
- **Er staat geen enkele gebackteste statistiek in het boek.** Alleen uitspraken als "most of the time", "OTE works 80% of the time", één handgekozen maand met "6 winnaars, 1 verliezer".
- Veel kernbegrippen zijn niet exact gedefinieerd: "displacement", "HTF PD array", "draw on liquidity", "narrative". Die moeten wij zelf vastleggen voor een test.
- Tijden in New York-tijd. IC Markets-server = NY + 7 uur, het hele jaar (gecontroleerd in de data).

## Tijdvensters (NY → server)
| Venster | NY | Server |
|---|---|---|
| Azië-range | 20:00–00:00 | 03:00–07:00 |
| Midnight open | 00:00 | 07:00 |
| London killzone | 02:00–05:00 | 09:00–12:00 |
| NY killzone | 07:00–10:00 | 14:00–17:00 |
| NY opening / Judas (indices) | 09:30–10:00 | 16:30–17:00 |
| Silver Bullet | 10:00–11:00 | 17:00–18:00 |
| London close | 10:00–12:00 | 17:00–19:00 |
| Lunch (niet traden) | 12:00–13:30 | 19:00–20:30 |
| CBDR | 14:00–20:00 | 21:00–03:00 |

## Modellen die in ronde 2 getest zijn
1. **London Judas** — sweep van de Azië-range in de London killzone, terug binnen, richting de andere kant (H11, H13, H22). Filters uit het boek: smalle Azië-range, ma–wo, dagbias, SMT EURUSD/GBPUSD.
2. **Silver Bullet** — sweep van London-high/low bij de NY-opening, daarna FVG tussen 10 en 11 NY, instap op het midden (H19, H28).
3. **Monday range** — sweep van de maandag-high/low later in de week, terug binnen (H22).
4. **Dagbias** — gisteren boven de high van eergisteren maar eronder gesloten → verwacht de low (H12).
5. **London close** — dag met range > ADR5 om 10:00 NY → terugval (H11).

## Nog niet getest (backlog)
CBDR-projecties (standaarddeviaties van de 14–20u-range), NWOG/NDOG (openingsgaten, terug naar het midden), dagbias via D1-swings met "candle 3"-raid, NY 07–09u retracement naar 62%, OTE 62–79%, breaker/mitigation/rejection blocks, IPDA 20/40/60-dagen, seizoenspatronen per maand, de week-high/low op di/wo.
