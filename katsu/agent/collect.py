"""
Verzamelaar en waakhond (docs/agent_spec.md §2–3). Leest alleen; raakt KATSU en MT5 nooit aan.

    python -m katsu.agent.collect C:\\katsu\\config.toml waakhond     elke 15 min (Taakplanner)
    python -m katsu.agent.collect C:\\katsu\\config.toml verzamel     elk uur (Taakplanner)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

from katsu.live.config import load_config, paths
from katsu.live.notify import Discord

STIL_NA = 10 * 60          # s zonder hartslag → KATSU staat stil
MT5_WEG_NA = 10 * 60       # s niet verbonden → melding
VERZAMEL_TE_OUD = 3 * 3600 # s zonder geslaagde verzameling → melding
LOG_DAGEN = 30
FILES = {"status": "status.json", "state": "orders.json", "control": "controle.json", "forward": "vooruittest.json",
         "deals": "deals.json", "vragen": "vragen.json"}


def _now():
    return time.time()


def _read(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, default=str)
    os.replace(tmp, path)


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).astimezone().strftime("%d-%m %H:%M")


# ------------------------------------------------------------------ waakhond

def diagnose(p: dict, now: float) -> tuple[str | None, str]:
    """(probleem, uitleg). probleem: None, 'stil', 'mt5' of 'verzamelaar'."""
    try:
        age = now - os.path.getmtime(p["status"])
    except OSError:
        return "stil", "geen hartslag gevonden (status.json ontbreekt): KATSU draait niet"
    if age > STIL_NA:
        return "stil", f"KATSU staat stil: laatste hartslag {int(age // 60)} min geleden ({_iso(now - age)})"
    st = _read(p["status"], {}) or {}
    if not st.get("verbonden", True) and st.get("niet_verbonden_sinds"):
        # tijd in servertijd: vergelijk met de servertijd in dezelfde status
        try:
            import pandas as pd
            gap = (pd.Timestamp(st["tijd_server"]) - pd.Timestamp(st["niet_verbonden_sinds"])).total_seconds()
        except Exception:
            gap = MT5_WEG_NA + 1
        if gap > MT5_WEG_NA:
            return "mt5", f"KATSU draait, maar MT5 is al {int(gap // 60)} min niet verbonden"
    vz = _read(os.path.join(p["data"], "verzamel.json"), {}) or {}
    if vz.get("laatste_ok") and now - vz["laatste_ok"] > VERZAMEL_TE_OUD:
        return "verzamelaar", f"de verzamelaar heeft sinds {_iso(vz['laatste_ok'])} niets meer kunnen doorsturen " \
                              f"({vz.get('laatste_fout', '?')})"
    return None, "alles in orde"


def watchdog(cfg, now: float | None = None, discord: Discord | None = None) -> str | None:
    p = paths(cfg)
    now = _now() if now is None else now
    discord = discord or Discord(cfg.webhook)
    sp = os.path.join(p["data"], "waakhond.json")
    prev = _read(sp, {}) or {}
    prob, text = diagnose(p, now)
    if prob != prev.get("probleem"):
        if prob is None:
            discord.send(f"✅ **Waakhond** · terug in orde (probleem was: {prev.get('uitleg', '?')})")
        else:
            discord.send(f"🚨 **Waakhond** · {text}")
        prev = {"probleem": prob, "uitleg": text, "sinds": now}
    prev["laatste_controle"] = now
    _write(sp, prev)
    return prob


# ------------------------------------------------------------------ verzamelaar

def _git(repo, *args, check=True):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=check)


def gather(cfg, now: float | None = None) -> list[str]:
    """Kopieert alles naar de map van de privé-repo. Geeft de lijst gekopieerde bestanden."""
    p = paths(cfg)
    now = _now() if now is None else now
    repo = cfg.agent_repo
    os.makedirs(os.path.join(repo, "log"), exist_ok=True)
    out = []
    for key, name in FILES.items():
        src = p[key]
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(repo, name))
            out.append(name)
    cutoff = datetime.fromtimestamp(now, timezone.utc).date().toordinal() - LOG_DAGEN
    for f in sorted(os.listdir(p["log"])):
        if not f.endswith(".jsonl"):
            continue
        try:
            day = datetime.strptime(f[:10], "%Y-%m-%d").date().toordinal()
        except ValueError:
            continue
        if day >= cutoff:
            shutil.copyfile(os.path.join(p["log"], f), os.path.join(repo, "log", f))
            out.append("log/" + f)
    for f in os.listdir(os.path.join(repo, "log")):              # oudere logs weg uit de repo (blijven op de VPS)
        if f.endswith(".jsonl") and f not in {x[4:] for x in out if x.startswith("log/")}:
            os.remove(os.path.join(repo, "log", f))
    du = shutil.disk_usage(p["data"])
    _write(os.path.join(repo, "vps.json"), {
        "verzameld": datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds"),
        "schijf_vrij_gb": round(du.free / 1e9, 1), "schijf_totaal_gb": round(du.total / 1e9, 1),
        "waakhond": _read(os.path.join(p["data"], "waakhond.json"), {})})
    out.append("vps.json")
    if not os.path.exists(os.path.join(repo, "README.md")):
        with open(os.path.join(repo, "README.md"), "w", encoding="utf-8") as fh:
            fh.write("# katsu-data (privé)\n\nAutomatisch verzameld door de VPS (katsu/agent/collect.py). Niet met de "
                     "hand aanpassen. Logboeken van de agent staan in `logboek/`.\n")
    return out


def collect(cfg, now: float | None = None) -> str:
    p = paths(cfg)
    now = _now() if now is None else now
    vz_path = os.path.join(p["data"], "verzamel.json")
    vz = _read(vz_path, {}) or {}
    try:
        if not os.path.isdir(os.path.join(cfg.agent_repo, ".git")):
            raise RuntimeError(f"{cfg.agent_repo} is geen git-kloon van katsu-data (zie installatie §11)")
        gather(cfg, now)
        if not _git(cfg.agent_repo, "config", "user.name", check=False).stdout.strip():
            _git(cfg.agent_repo, "config", "user.name", "KATSU VPS")
            _git(cfg.agent_repo, "config", "user.email", "katsu-vps@localhost")
        _git(cfg.agent_repo, "add", "-A")
        changed = _git(cfg.agent_repo, "diff", "--cached", "--quiet", check=False).returncode != 0
        if changed:
            st = _read(p["status"], {}) or {}
            stamp = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            _git(cfg.agent_repo, "commit", "--quiet", "-m",
                 f"VPS {stamp} · verbonden={st.get('verbonden')} · open trades {len(st.get('open_trades', []))}")
        has_remote = bool(_git(cfg.agent_repo, "remote", check=False).stdout.strip())
        if has_remote:
            if _git(cfg.agent_repo, "ls-remote", "--heads", "origin", check=False).stdout.strip():   # repo niet leeg
                r = _git(cfg.agent_repo, "pull", "--rebase", "--quiet", "origin", "HEAD", check=False)  # logboeken agent
                if r.returncode != 0:
                    _git(cfg.agent_repo, "rebase", "--abort", check=False)
                    raise RuntimeError(f"pull mislukt: {r.stderr.strip()[:200]}")
            r = _git(cfg.agent_repo, "push", "--quiet", "-u", "origin", "HEAD", check=False)
            if r.returncode != 0:
                raise RuntimeError(f"push mislukt: {r.stderr.strip()[:200]}")
        msg = "doorgestuurd" if changed else "niets nieuws"
        vz.update(laatste_ok=now, laatste_fout=None)
    except Exception as ex:
        vz.update(laatste_fout=f"{ex}"[:300])
        vz.setdefault("laatste_ok", now)      # eerste keer: de waakhond meldt pas na 3 u zonder succes
        msg = f"FOUT: {ex}"
    _write(vz_path, vz)
    return msg


if __name__ == "__main__":
    cfg = load_config(sys.argv[1] if len(sys.argv) > 1 else r"C:\katsu\config.toml")
    what = sys.argv[2] if len(sys.argv) > 2 else "verzamel"
    if what == "waakhond":
        print("waakhond:", watchdog(cfg) or "alles in orde")
    else:
        print("verzamel:", collect(cfg))
