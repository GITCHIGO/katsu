"""
Instellingen van KATSU Live. Het bestand staat BUITEN de repo (standaard C:\\katsu\\config.toml) omdat er
geheimen in staan: MT5-wachtwoord, Discord-webhook, dashboardwachtwoord. Nooit in git zetten.
Voorbeeld: docs/live_config_voorbeeld.toml
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field

MARKETS = ("EURUSD", "GBPUSD", "XAUUSD")


@dataclass
class Config:
    login: int | None = None
    password: str | None = None
    server: str | None = None
    terminal: str | None = None
    allow_live: bool = False
    mode: str = "loggen"
    data_dir: str = r"C:\katsu\data"
    lots: dict = field(default_factory=lambda: {"EURUSD": 0.10, "GBPUSD": 0.10, "XAUUSD": 0.02})
    symbols: dict = field(default_factory=lambda: {m: m for m in MARKETS})
    webhook: str = ""
    # Welke meldingen naar Discord gaan (besluit Gitchi 22 okt 2026: alleen dringend + trades). De rest: dashboard.
    discord_kinds: tuple = ("fout", "geweigerd", "gevuld", "gesloten")
    dash_password: str = ""
    dash_secret: str = ""
    port: int = 8080
    host: str = "0.0.0.0"
    agent_repo: str = r"C:\katsu\katsu-data"      # lokale kloon van de privé-repo GITCHIGO/katsu-data (agent)


def load_config(path: str) -> Config:
    with open(path, "rb") as fh:
        d = tomllib.load(fh)
    mt5, k, dc, db = d.get("mt5", {}), d.get("katsu", {}), d.get("discord", {}), d.get("dashboard", {})
    c = Config(login=int(mt5["login"]) if mt5.get("login") else None, password=mt5.get("password") or None,
               server=mt5.get("server") or None, terminal=mt5.get("terminal") or None,
               allow_live=bool(mt5.get("allow_live", False)), mode=k.get("mode", "loggen"),
               data_dir=k.get("data_dir", Config.data_dir), webhook=dc.get("webhook", ""),
               dash_password=db.get("password", ""), dash_secret=db.get("secret", ""), port=int(db.get("port", 8080)),
               host=db.get("host", "0.0.0.0"), agent_repo=d.get("agent", {}).get("repo_dir", Config.agent_repo))
    if "lots" in k:
        c.lots = {m: float(v) for m, v in k["lots"].items()}
    if "meldingen" in dc:
        c.discord_kinds = tuple(dc["meldingen"])
    if "symbols" in k:
        c.symbols = {**c.symbols, **k["symbols"]}
    check(c)
    return c


def check(c: Config):
    errors = []
    if c.mode not in ("loggen", "orders"):
        errors.append("katsu.mode moet 'loggen' of 'orders' zijn")
    for m in MARKETS:
        if not (0 < c.lots.get(m, 0) <= 1.0):
            errors.append(f"lot voor {m} ontbreekt of is groter dan 1,0 (veiligheidsgrens)")
    if len(c.dash_password) < 4:
        errors.append("dashboard.password moet minstens 4 tekens hebben")
    if len(c.dash_secret) < 32:
        errors.append("dashboard.secret moet minstens 32 willekeurige tekens hebben")
    if errors:
        raise ValueError("Fout in config.toml:\n- " + "\n- ".join(errors))


def paths(c: Config) -> dict:
    p = {"data": c.data_dir, "bars": os.path.join(c.data_dir, "bars"), "log": os.path.join(c.data_dir, "log"),
         "state": os.path.join(c.data_dir, "state.json"), "control": os.path.join(c.data_dir, "controle.json"),
         "status": os.path.join(c.data_dir, "status.json"), "deals": os.path.join(c.data_dir, "deals.json"),
         "forward": os.path.join(c.data_dir, "vooruittest.json"),
         "vragen": os.path.join(c.data_dir, "agent_vragen.json")}
    for k in ("data", "bars", "log"):
        os.makedirs(p[k], exist_ok=True)
    return p
