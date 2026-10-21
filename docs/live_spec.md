# KATSU Live — spec v0.1 (21 okt 2026, ontwerp; nog niet gebouwd)

Doel: de drie vastgelegde setups (`katsu/presets.py`, plan `docs/vooruittest_plan.md`) **live** zoeken op de
IC Markets-**demo**, de orders zelf plaatsen en beheren, Gitchi verwittigen via Discord en alles tonen op een eigen
dashboard. Zelfde code als de backtester (werkregel 3). Alleen demo tot de vooruit-test iets bewezen heeft.

## 1. Waar en waarmee
- **Windows-VPS** van Gitchi, met MT5 (IC Markets-demo, ingelogd) en Python.
- Koppeling: officieel Python-pakket `MetaTrader5` (gratis; alleen Windows; terminal moet open zijn).
- **Data uitsluitend uit MT5** (IC Markets) — geen TradingView (andere bron = andere candles = andere setups; les uit
  GAMAN-X; werkregels 3 en 4).
- Code in de KATSU-repo (`katsu/live/…`), met tests. Gitchi zet ze met een stappenplan op de VPS (git pull).
- **Geheimen** (Discord-webhook, dashboardwachtwoord, accountnummer) in `C:\katsu\config.toml`, **buiten de repo**.

## 2. Ritme
- **Elke 15 minuten, 10 s na de sluiting van een M15-candle:** gesloten candles ophalen (M15; H1/H4/D1 opgebouwd uit
  M15 zoals in de backtest), setups zoeken met dezelfde functies als het dashboard/vooruit-test.
- **Elke 10 s:** orderbeheer (zie §3): annuleren als de TP eerst geraakt wordt, TP zetten bij vulling (zones),
  sluiten op dagclose (AMD) of na 14 dagen, controleren of SL/TP bij de broker staan.
- Opwarming bij de start: ±18 maanden M15 uit MT5 (voor trends, swings en ATR).

## 3. Orders (gelijk aan de backtest)
| Setup | Order | Geldig | Annuleren | Na vulling |
|---|---|---|---|---|
| Test #1 (FVG) | limiet 38,2% in het gat, SL onder OB (+spread+0,1 ATR), TP oude high max 2R | 5 handelsdagen | TP eerst geraakt | max. 14 dagen open |
| AMD-extra | markt (C2-E1) of limiet in FVG (C1-E2), SL voorbij manipulatie, TP overkant Azië-range | E2 tot 18:00 server | TP eerst geraakt (E2) | sluiten op dagclose (00:00 server) |
| Zone GBPUSD | limiet op de rand, SL onder de zone | 7 dagen | geen | TP = oude high vóór de vulling, max 2R (TP wordt bij vulling gezet) |
- Eén trade tegelijk **per setup per pair**; setups blokkeren elkaar niet. Elke setup heeft een eigen *magic number*.
- Vaste lots (instelbaar): EURUSD 0,10 · GBPUSD 0,10 · XAUUSD 0,02.
- Geen dagstop (zoals in de backtest van deze setups); wel een **noodknop** (alles annuleren/sluiten, scanner pauzeren).

## 4. Discord
Berichten: nieuwe setup/order geplaatst (setup, pair, richting, entry, SL, TP, lot, geldig tot) · gevuld · gesloten
(TP/SL/einde dag/max duur, R, pips, $) · geannuleerd (reden) · fout of verbinding weg. Dagoverzicht om 23:00 BE.

## 5. Dashboard (eigen stijl: modern, compact, overzichtelijk, licht neon-futuristisch)
Kleine webserver op de VPS (Flask), met wachtwoord; werkt op gsm.
- **Nu:** status (verbonden, laatste scan, volgende scan), klaarstaande orders, lopende trades met live R.
- **Resultaten:** algemeen + per setup + per setup×pair (trades, winrate, winst, verlies, netto, R, pips) —
  zoals het vooruit-rapport; curve per setup.
- **Controle (werkregel 5):** elke trade backtest ↔ broker naast elkaar (vulprijs, slippage, spread, commissie, swap,
  resultaat) en het % dat overeenkomt (doel ≥ 90%; daaronder: niets verder bouwen).
- **Log:** alle scans, gevonden setups, geblokkeerde signalen (bv. al een trade open) en fouten (werkregel 8).

## 6. Veiligheid
Alleen demo (het script weigert een live-account tenzij een aparte instelling bewust aangezet is); maximaal 1 order per
setup per pair; elke order met SL en TP bij de broker; herstart veilig (leest open orders/posities uit MT5 en gaat
verder); kill-switch op het dashboard.

## 7. Bouwvolgorde en tests
1. MT5-adapter met een **nep-MT5** voor tests (geen terminal nodig in de tests).
2. Live-scan = dezelfde functies als `scripts/vooruittest.py`; test: de live-scan op historische data geeft exact
   dezelfde setups als de backtest.
3. Orderbeheer als toestandsmachine (wacht → geplaatst → gevuld → gesloten / geannuleerd), met handberekende tests.
4. Discord + dashboard.
5. Proef op de VPS: één week alleen loggen (geen orders), daarna orders op demo.
