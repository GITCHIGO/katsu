# KATSU Agent — spec v0.1 (22 okt 2026, akkoord Gitchi)

Doel: alles rond KATSU Live verzamelen, blijven controleren en Gitchi een logboek geven van wat er gebeurde — met
voorstellen, maar **zonder iets aan te passen** tot Gitchi toestemming geeft.

## 1. Drie delen
| Deel | Waar | Wat | AI? |
|---|---|---|---|
| **Verzamelaar** | VPS, elk uur (Taakplanner) | bundelt alles en zet het in de privé-repo `GITCHIGO/katsu-data` | nee, vaste code |
| **Waakhond** | VPS, elke 15 min (Taakplanner) | leeft KATSU nog? MT5 verbonden? → meteen Discord bij een probleem en bij herstel | nee, vaste code |
| **Agent** | Claude, geplande taak in de cloud | leest de privé-repo, controleert, schrijft het logboek + voorstellen | ja |

Waarom zo: KATSU zelf blijft vaste code (werkregel 3). De AI kijkt mee en oordeelt, maar zit nooit in de handelslus.

## 2. Wat de verzamelaar bundelt (map in `katsu-data`)
- `status.json` — laatste hartslag van KATSU (elke ronde geschreven door de runner): tijd, verbonden, stand,
  gepauzeerd, account (saldo, equity), open trades/orders, laatste scan, fouten.
- `orders.json` — alle KATSU-orders en trades (toestandsmachine, met geschiedenis).
- `controle.json` — controle backtest ↔ MT5 (werkregel 5).
- `vooruittest.json` — vooruit-test vanaf 10 okt 2026 (zelfde code als `scripts/vooruittest.py`), één keer per dag
  berekend door de runner op de MT5-candles.
- `deals.json` — volledige MT5-accounthistoriek sinds de start (ook trades met de hand of van een ander programma).
- `log/<datum>.jsonl` — het logboek van KATSU (laatste 30 dagen).
- `vps.json` — schijfruimte, laatste hartslag, toestand van de waakhond.
- Nooit: `config.toml` of andere geheimen.
Commit-bericht: tijd + korte samenvatting. Geen commit als er niets veranderde.

## 3. Waakhond
- **KATSU staat stil:** `status.json` ouder dan 10 min → Discord "🚨 KATSU staat stil sinds …".
- **MT5 niet verbonden:** status vers maar `connected = false` langer dan 10 min → Discord.
- Eén melding per probleem (geen spam), en "✅ terug in orde" bij herstel.
- Raakt de waakhond zelf niet aan KATSU of MT5 (alleen lezen).

## 4. Agent (Claude)
- **Dagelijks** (elke ochtend 07:10 BE): korte check — draaide alles, nieuwe signalen/trades, fouten, afwijkingen
  backtest ↔ MT5, stopregels. Kort logboek.
- **Wekelijks** (zondag 10:10 BE): volledige review — vooruit-test per setup en per pair, controle per trade,
  kosten/slippage, gedrag van de scanner, opvallende dingen, **voorstellen** (genummerd, met reden en risico).
- Schrijft het logboek in `katsu-data/logboek/<datum>-dag.md` / `-week.md`, en als document in het project
  MODEL KATSU (`claude/katsu_agent_logboek.md`, nieuwste bovenaan). Melding op gsm (push/e-mail) met de samenvatting.
- In elke chat kan Claude dezelfde repo lezen ("lees katsu-data"), zodat Gitchi kan doorvragen.

## 5. Niets aanpassen zonder toestemming
- De agent heeft **alleen leesrecht** op de werkelijkheid: geen toegang tot de VPS, MT5 of het dashboard.
- Hij schrijft alleen in `katsu-data/logboek/` en in het projectdocument. Nooit in de KATSU-code.
- Een voorstel wordt pas uitgevoerd als Gitchi het in een chat goedkeurt; dan volgt de gewone weg: spec → code →
  tests → push → Gitchi doet zelf `git pull` op de VPS. **`git pull` is de toestemmingsknop.**
- Regels van KATSU (spec, presets, stopregels) wijzigen nooit door de agent, ook niet "klein".

## 7. Berichtenvenster in het dashboard (besluit Gitchi 22 okt 2026)
- Tab **Agent** in het KATSU-dashboard: gesprek met de agent + de logboeken (nieuwste bovenaan).
- Gitchi typt een vraag → `C:\katsu\data\agent_vragen.json` → verzamelaar → `katsu-data/vragen.json`.
- De agent beantwoordt open vragen om **07:10** (met de dagelijkse check) en **19:10** (korte run, alleen vragen +
  korte status, zonder gsm-melding) in `katsu-data/antwoorden.json` (`{"antwoorden": [{"vraag_id", "tijd", "tekst"}]}`).
  Antwoorden zijn markdown; het dashboard toont ze veilig (alles ge-escaped). Vraagt Gitchi een wijziging: alleen
  een voorstel, nooit uitvoeren (§5).
- Het antwoord verschijnt in het dashboard zodra de verzamelaar het binnenhaalt (elk uur).

## 8. Discord (besluit Gitchi 22 okt 2026: alleen dringend + trades)
Naar Discord gaan nog: waakhond (KATSU stil, MT5 weg, verzamelaar faalt), fouten (ook de noodknop), geweigerde
orders, gevulde en gesloten trades. Signalen, geplaatste/geannuleerde orders, scans en het dagoverzicht staan
alleen nog in het dashboard. Instelbaar met `[discord] meldingen = [...]` in config.toml.
- MT5 niet verbonden (besluit Gitchi 23 okt 2026): pas een Discord-melding na **2 minuten** zonder verbinding
  (korte haperingen staan alleen in het log); na zo'n melding volgt ook "✅ terug na … min".

## 6. Bouw en tests
- `katsu/agent/collect.py` (verzamelaar + waakhond), runner schrijft `status.json`, `deals.json`, `vooruittest.json`.
- Tests met tijdelijke mappen en een lokale git-repo (geen GitHub nodig in de tests).
- Installatie: `docs/live_installatie.md` §11.
