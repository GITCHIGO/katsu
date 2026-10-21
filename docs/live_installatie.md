# KATSU Live — installatie op de Windows-VPS (stappenplan)

Alles gebeurt via Extern bureaublad (RDP) op de VPS. Kopieer de commando's precies over in **PowerShell**.
Loopt iets anders dan hier staat: stop, maak een screenshot en stuur hem door.

## 0. GAMAN en GAMAN-X stoppen
1. Sluit de vensters van GAMAN en GAMAN-X (zwarte consolevensters of Python-vensters).
2. Start ze automatisch op? Open **Taakplanner** (Task Scheduler) → zoek taken met GAMAN → rechtsklik → **Uitschakelen**.
3. Laat MT5 staan; die gebruiken we opnieuw.

## 1. MT5 klaarzetten
1. Open de IC Markets-MT5 en log in op je **KATSU-demoaccount** (€5 000). Vink **Wachtwoord opslaan** aan.
2. Menu **Extra → Opties → Expert Advisors**: vink **Algoritmisch handelen toestaan** aan. Zet ook de knop
   **Algo Trading** bovenaan op groen.
3. Menu **Extra → Opties → Grafieken**: zet **Max. bars in grafiek** op **Unlimited** (KATSU heeft 24 maanden M15 nodig).
4. **Marktoverzicht**: zorg dat EURUSD, GBPUSD en XAUUSD erin staan (rechtsklik → Symbolen).
5. Laat MT5 open staan.

## 2. Python en Git controleren
```
python --version
git --version
```
- Python moet **3.11 of nieuwer** zijn. Zo niet: installeer Python 3.12 (64-bit) van python.org en vink
  **Add python.exe to PATH** aan.
- Git ontbreekt? Installeer "Git for Windows" (standaardopties).

## 3. Code ophalen
```
mkdir C:\katsu
cd C:\katsu
git clone https://github.com/GITCHIGO/katsu.git code
cd C:\katsu\code
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-live.txt
```
(Krijg je een fout over "running scripts is disabled": eerst `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`,
antwoord **J**, en dan opnieuw.)

## 4. Instellingen (buiten de repo)
```
copy C:\katsu\code\docs\live_config_voorbeeld.toml C:\katsu\config.toml
notepad C:\katsu\config.toml
```
Vul in:
- `login`, `password`, `server` van je KATSU-demoaccount (server staat in MT5: Bestand → Inloggen).
- `terminal`: pad naar `terminal64.exe` (rechtsklik op het MT5-icoon → Bestandslocatie openen).
- `webhook`: Discord → jouw server → kanaal → ⚙ Kanaal bewerken → Integraties → Webhooks → Nieuwe webhook → URL kopiëren.
- `password` (dashboard): minstens 12 tekens, **niet** hetzelfde als een ander wachtwoord.
- `secret`: maak hem met `python -c "import secrets; print(secrets.token_hex(32))"` en plak het resultaat.
- `mode` blijft de eerste week **"loggen"**.

## 5. Controle (leest alleen, plaatst niets)
```
cd C:\katsu\code
.\.venv\Scripts\Activate.ps1
python -m katsu.live.check C:\katsu\config.toml discord
```
Onderaan moet **ALLES OK** staan, en in Discord moet een testbericht verschijnen. Stuur de uitvoer door.

## 6. Dashboard bereikbaar maken (poort 8080)
In PowerShell **als administrator**:
```
New-NetFirewallRule -DisplayName "KATSU dashboard" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
```
Heeft je VPS bij TransIP een eigen firewall in het controlepaneel aan staan: zet daar ook TCP 8080 open.

## 7. Starten
```
cd C:\katsu\code
.\.venv\Scripts\Activate.ps1
python -m katsu.live.runner C:\katsu\config.toml
```
- Op je gsm: `http://<IP-van-je-VPS>:8080` → inloggen met je dashboardwachtwoord.
- Laat het venster open. **RDP sluiten met het kruisje** (niet afmelden!): dan blijven MT5 en KATSU draaien.

## 8. Automatisch starten na een herstart
Taakplanner → **Basistaak maken** → naam "KATSU Live" → **Bij aanmelden** → **Een programma starten**:
- Programma: `C:\katsu\code\.venv\Scripts\python.exe`
- Argumenten: `-m katsu.live.runner C:\katsu\config.toml`
- Beginnen in: `C:\katsu\code`
Na een herstart van de VPS (bv. Windows-update) moet je één keer inloggen via RDP; dan starten MT5 en KATSU.

## 9. Na een week loggen → orders op demo
1. Kijk samen met Claude naar **Controle** (signalen live ↔ backtest).
2. Is alles in orde: zet in `C:\katsu\config.toml` `mode = "orders"`, stop KATSU (Ctrl+C) en start opnieuw (stap 7).

## 10. Bijwerken
```
cd C:\katsu\code
git pull
.\.venv\Scripts\Activate.ps1
pip install -r requirements-live.txt
```
Daarna KATSU herstarten. Open orders en trades blijven bij MT5 staan (met SL en TP) en worden na de herstart opgepikt.
