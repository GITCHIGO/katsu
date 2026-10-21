"""
Discord-berichten (spec §4) en het logboek (werkregel 8). Een mislukt bericht stopt KATSU nooit; het komt in het log.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime

ICON = {"signaal": "🔎", "geplaatst": "📝", "gevuld": "✅", "gesloten": "🏁", "geannuleerd": "✖️", "wacht": "⏸️",
        "geblokkeerd": "⛔", "geweigerd": "⚠️", "gemist": "⏭️", "fout": "🚨", "info": "ℹ️", "scan": "🔁",
        "overzicht": "📊"}


class Discord:
    def __init__(self, webhook: str, timeout: float = 6.0):
        self.webhook = webhook.strip()
        self.timeout = timeout
        self.last_error = ""

    def send(self, text: str) -> bool:
        if not self.webhook:
            self.last_error = "geen webhook ingevuld in config.toml"
            return False
        if not self.webhook.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")):
            self.last_error = "webhook moet beginnen met https://discord.com/api/webhooks/"
            return False
        body = json.dumps({"content": text[:1900], "username": "KATSU Live"}).encode()
        req = urllib.request.Request(self.webhook, data=body, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "DiscordBot (https://github.com/GITCHIGO/katsu, 1.0)"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                ok = 200 <= r.status < 300
                self.last_error = "" if ok else f"Discord antwoordde {r.status}"
                return ok
        except urllib.error.HTTPError as ex:
            detail = ex.read()[:200].decode(errors="replace")
            self.last_error = f"Discord antwoordde {ex.code}: {detail}"
            if ex.code in (401, 404):
                self.last_error += " (webhook bestaat niet of is fout gekopieerd)"
            return False
        except Exception as ex:
            self.last_error = f"geen verbinding met Discord: {ex!r}"
            return False


def format_event(ev) -> str:
    return f"{ICON.get(ev.kind, '•')} **{ev.kind}** · {ev.text}"


class Logbook:
    """Eén JSON-regel per gebeurtenis, één bestand per dag (servertijd)."""

    def __init__(self, folder: str):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)

    def write(self, ev: dict):
        day = str(ev.get("time", datetime.now()))[:10]
        with open(os.path.join(self.folder, f"{day}.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(ev, ensure_ascii=False, default=str) + "\n")

    def tail(self, n: int = 200) -> list[dict]:
        out = []
        for f in sorted(os.listdir(self.folder), reverse=True):
            if not f.endswith(".jsonl"):
                continue
            with open(os.path.join(self.folder, f), encoding="utf-8") as fh:
                lines = [json.loads(x) for x in fh if x.strip()]
            out += lines[::-1]                     # nieuwste eerst
            if len(out) >= n:
                break
        return out[:n]
