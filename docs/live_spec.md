# KATSU Live — spec v0.2 (21 okt 2026; gebouwd, nog niet op de VPS)

Doel: de drie vastgelegde setups (`katsu/presets.py`, plan `docs/vooruittest_plan.md`) **live** zoeken op de
IC Markets-**demo**, de orders zelf plaatsen en beheren, Gitchi verwittigen via Discord en alles tonen op een eigen
dashboard. Zelfde code als de backtester (werkregel 3). Alleen demo tot de vooruit-test iets bewezen heeft.

Wijzigingen t.o.v. v0.1 staan onderaan (§9).

## 1. Waar en waarmee
- **Windows-VPS** van Gitchi (TransIP), met MT5 (IC Markets-demo, ingelogd) en Python ≥ 3.11. GAMAN en GAMAN-X gaan
  offline (besluit Gitchi 21 okt 2026).
- Koppeling: officieel Python-pakket `MetaTrader5` (gratis; alleen Windows; terminal moet open zijn) — `katsu/live/broker.py`.
- **Data uitsluitend uit MT5** (IC Markets) — geen TradingView (andere bron = andere candles = andere setups; les uit
  GAMAN-X; werkregels 3 en 4).
- Code in de KATSU-repo (`katsu/live/…`), met tests en een nep-MT5 (`katsu/live/fake.py`). Installatie:
  `docs/live_installatie.md`.
- **Geheimen** (MT5-wachtwoord, Discord-webhook, dashboardwachtwoord) in `C:\katsu\config.toml`, **buiten de repo**
  (voorbeeld: `docs/live_config_voorbeeld.toml`).

## 2. Ritme
- **10 s na de sluiting van elke M15-candle:** de laatste **24 maanden** gesloten M15-candles uit MT5 ophalen (de
  candle die nog loopt valt weg), dezelfde rijen bouwen als de vooruit-test (`scripts/vooruittest.rows_for`) en de
  nieuwe signalen van de drie setups nemen (`katsu/live/scan.py`).
  - Getest: 18 en 24 maanden geschiedenis geven exact dezelfde setups als de backtest vanaf 2023 (12 maanden niet).
  - Getest: op 69 afgekapte momenten (sep–okt 2026) vond de scan met alleen data tot dat moment exact dezelfde setups,
    kenmerken en orderplannen als de backtest op alle data → geen vooruitkijken.
- **Elke 10 s:** orderbeheer (§3).
- **Elk uur:** controle backtest ↔ broker (§5) herberekenen.
- Na een onderbreking: signalen van gemiste candles (max. 7 dagen terug) worden nog geplaatst als de backtest de order
  op dit moment nog open zou hebben; anders gelogd als **gemist**.
- De candles worden bij elke scan bewaard in `C:\katsu\data\bars\<PAIR>_M15_live.pkl` (ook bruikbaar voor de vooruit-test).

## 3. Orders (gelijk aan de backtest)
| Setup | Order | Geldig | Annuleren | Na vulling |
|---|---|---|---|---|
| Test #1 (FVG) | limiet 38,2% in het gat, SL anchor ± (spread + 0,1 ATR), TP oude high max 2R | 480 M15-candles na het signaal (geteld, zoals de backtest) | TP-niveau eerst geraakt | max. 14 dagen open |
| AMD-extra | markt (C2-E1) of limiet in FVG (C1-E2), SL voorbij manipulatie, TP overkant Azië-range | E2 tot 18:00 server | TP eerst geraakt (E2) | sluiten om **23:55 server** |
| Zone GBPUSD | limiet op de rand, SL onder de zone | 7 dagen | geen | TP = oude high vóór de vulling, max 2R (bij de vulling gezet; tot dan voorlopig 2R) |

- **Eén trade tegelijk per setup per pair** (zoals `one_at_a_time` in de backtest): meerdere limieten van dezelfde
  setup op hetzelfde pair mogen klaarstaan; zodra er één vult, gaan de andere van de broker af (**wacht**). Is de trade
  dicht, dan gaan ze terug naar de broker — tenzij de koers hun limiet raakte terwijl de trade liep (**geblokkeerd**,
  de backtest slaat die ook over). Een marktorder terwijl er een trade loopt: geblokkeerd. Setups blokkeren elkaar niet.
- Vullen twee limieten van dezelfde groep in dezelfde seconden: de vroegste blijft, de andere wordt meteen gesloten.
- Een limiet die bij het plaatsen al voorbij de koers ligt, wordt een marktorder (backtest: vulling op de open).
- SL bij het plaatsen: met de **minimumspread** van het instrument (de backtest gebruikt de spread van de vulcandle;
  die is vooraf onbekend en in de IC-data meestal ≤ het minimum). TP wordt bij de vulling herrekend met de echte
  vulprijs (zelfde formule als de backtest; test: gelijk aan `simulate`).
- Max. duur valt in het weekend → sluiten vrijdag 23:50 server.
- Elke setup heeft een eigen *magic number* (710101 / 710102 / 710103); commentaar = order-ID.
- Vaste lots (instelbaar, max. 1,0): EURUSD 0,10 · GBPUSD 0,10 · XAUUSD 0,02.
- Geen dagstop (zoals de backtest van deze setups); wel een **noodknop** (alles annuleren/sluiten, scanner pauzeren).
- Toestanden (`katsu/live/orders.py`): log · geplaatst · wacht · gevuld · gesloten · geannuleerd · geblokkeerd ·
  geweigerd · gemist.

## 4. Discord
**Sinds 22 okt 2026 (keuze Gitchi): alleen dringend + trades** — fout/noodknop, geweigerd, gevuld, gesloten, plus de waakhond (docs/agent_spec.md §8). De rest staat in het dashboard.

Oorspronkelijk: Berichten: nieuw signaal (stand loggen) · order geplaatst (setup, pair, richting, entry, SL, TP, lot, geldig tot) ·
gevuld · gesloten (TP/SL/einde dag/max duur, R, pips, bedrag) · geannuleerd (reden) · geblokkeerd · geweigerd ·
fout of verbinding weg. Dagoverzicht om 23:00 BE. Een mislukt Discord-bericht stopt KATSU nooit.

## 5. Dashboard (stijl B 'Glas Aurora', gekozen 21 okt 2026)
Flask op de VPS, poort 8080, via **http** op het IP van de VPS (keuze Gitchi). Wachtwoord ≥ 4 tekens (keuze Gitchi; uniek!),
max. 5 foute pogingen per 15 min per IP en 20 per 24 u in totaal, sessiecookie (HttpOnly, SameSite=Strict), CSRF-sleutel op elke knop.
Werkt op gsm (onderbalk met 4 tabs) en desktop.
- **Nu:** status (verbonden, demo/live, laatste en volgende scan), netto deze maand + curve, lopende trades met live R
  (balk van SL naar TP), klaarstaande en wachtende orders, per setup deze maand. Ververst elke 20 s.
- **Resultaten:** deze maand / alles; trades, winrate, gem. R, totaal R, totale winst, totaal verlies, netto, lopend;
  per setup en per setup × pair (ook pips); curve per setup (R); lijst van trades. Bedragen = echte MT5-cijfers
  (winst + commissie + swap) in de rekeningmunt; R = netto / bedrag op het spel bij de vulling (MT5 `order_calc_profit`).
- **Controle (werkregel 5):** elke trade backtest ↔ MT5 naast elkaar (vulprijs, slippage in pips, uitkomst, R,
  commissie, swap) en signalen backtest ↔ live. **Gelijk** = in beide, zelfde uitkomst (TP / SL / tijd) en < 0,25R
  verschil. Overeenkomst = gelijk / alle trades. Doel ≥ 90 % op de eerste 20 trades; daaronder: niets verder bouwen.
- **Log:** alle scans, signalen, orders, geblokkeerde en gemiste signalen, fouten (werkregel 8). Bestanden:
  `C:\katsu\data\log\<datum>.jsonl`.

## 6. Veiligheid
- Alleen demo: KATSU stopt bij de start als het account geen demo is (tenzij `allow_live = true`, bewust).
- Maximaal 1 open trade per setup per pair; elke order met SL en TP bij de broker (ontbreken ze, dan zet KATSU ze
  opnieuw en meldt het).
- Herstart veilig: toestand in `C:\katsu\data\state.json`; bij de start vergelijkt KATSU met de open orders en
  posities in MT5 (vulling of sluiting tijdens de stilstand wordt opgepikt). Onbekende orders met een KATSU-magic
  worden gemeld, niet aangeraakt.
- Een fout in één ronde stopt het programma niet (log + Discord).
- Kill-switch op het dashboard (met bevestiging).

## 7. Bouwvolgorde en tests (status)
1. MT5-adapter + nep-MT5 — klaar.
2. Live-scan = dezelfde functies als de vooruit-test — klaar; tests: SL/TP gelijk aan `simulate`, scan op
   afgekapte data = backtest.
3. Orderbeheer als toestandsmachine — klaar; handberekende tests (vulling, TP/SL, R en bedrag, verlopen in candles
   en in tijd, annuleren op tick en op candle, wachten/terugzetten/blokkeren, marktorder, einde dag, max duur,
   zone-TP bij vulling, herstart, noodknop, weigering, dubbele vulling, ontbrekende SL/TP).
4. Discord + dashboard + runner + controle — klaar; tests (login, pogingen, CSRF, pagina's, runner-ronde, weigert
   live-account).
5. **Naspelen** (`scripts/live_replay.py`): het echte orderbeheer met de nep-MT5 op juni – 9 okt 2026 →
   **51/51 trades gelijk** aan de backtest (ideale broker: geen slippage; de echte demo zal afwijken — daarvoor is §5).
6. Proef op de VPS: één week stand **loggen** (geen orders), signalen vergelijken op de pagina Controle; daarna
   stand **orders** op demo.

## 8. Bekende verschillen live ↔ backtest (verwacht, zichtbaar op Controle)
- Slippage, echte spread en commissie/swap van IC Markets i.p.v. de vaste kosten van de backtest.
- Binnen één M15-candle neemt de backtest bij twijfel de ongunstigste volgorde (SL eerst, annuleren eerst, geen TP in
  de vulcandle). Live gebeurt wat echt gebeurt → live kan iets beter uitvallen; dat is geen fout.
- AMD sluit live om 23:55 i.p.v. op de close van de 23:45-candle (goud sluit bij IC om 23:58).

## 9. Wijzigingen t.o.v. v0.1
- §3: "maximaal 1 order per setup per pair" vervangen door de backtestregel (meerdere limieten mogen klaarstaan,
  max. 1 trade; wacht/geblokkeerd). v0.1 week daarin af van de backtest.
- §2: geschiedenis 24 maanden (v0.1: ±18) — getest.
- §3: SL met minimumspread; AMD sluit 23:55; max. duur in weekend → vrijdag 23:50; marktbare limiet → marktorder.
- §5: dashboard via http op poort 8080 met de beveiliging hierboven; stijl B.
- §5: definitie van "gelijk" en "overeenkomst" vastgelegd.
