"""
Berichtenvenster met de agent in het dashboard (docs/agent_spec.md §7).

- Gitchi typt een vraag in het dashboard → `<data_dir>/agent_vragen.json` (de verzamelaar zet die als `vragen.json`
  in de privé-repo katsu-data).
- De agent (geplande taak, 07:10 en 19:10) beantwoordt open vragen in `katsu-data/antwoorden.json` en schrijft zijn
  logboeken in `katsu-data/logboek/`. De verzamelaar haalt die elk uur binnen op de VPS.
- Het dashboard toont vragen en antwoorden als één gesprek, plus de logboeken.
"""
from __future__ import annotations

import html
import json
import os
import re
import uuid
from datetime import datetime, timezone

MAX_LEN = 2000


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def add_question(path: str, text: str, now: datetime | None = None) -> dict | None:
    text = (text or "").strip()[:MAX_LEN]
    if not text:
        return None
    now = now or datetime.now(timezone.utc)
    data = _read(path, {"vragen": []})
    q = {"id": uuid.uuid4().hex[:10], "tijd": now.isoformat(timespec="seconds"), "tekst": text}
    data.setdefault("vragen", []).append(q)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return q


def thread(vragen_path: str, antwoorden_path: str) -> list[dict]:
    """Gesprek: elke vraag gevolgd door zijn antwoord(en); open vragen gemarkeerd. Oudste eerst."""
    vragen = _read(vragen_path, {}).get("vragen", [])
    antw = _read(antwoorden_path, {}).get("antwoorden", [])
    by_q: dict = {}
    for a in antw:
        by_q.setdefault(a.get("vraag_id"), []).append(a)
    out = []
    for q in sorted(vragen, key=lambda x: x.get("tijd", "")):
        out.append({"van": "gitchi", "tijd": q.get("tijd"), "tekst": q.get("tekst", ""), "open": q["id"] not in by_q})
        for a in sorted(by_q.get(q["id"], []), key=lambda x: x.get("tijd", "")):
            out.append({"van": "agent", "tijd": a.get("tijd"), "tekst": a.get("tekst", "")})
    for a in antw:                                    # berichten van de agent zonder vraag (bv. een waarschuwing)
        if not a.get("vraag_id"):
            out.append({"van": "agent", "tijd": a.get("tijd"), "tekst": a.get("tekst", "")})
    return sorted(out, key=lambda x: (x.get("tijd") or ""))


def logbooks(repo_dir: str, limit: int = 30) -> list[dict]:
    folder = os.path.join(repo_dir, "logboek")
    if not os.path.isdir(folder):
        return []
    out = []
    for f in sorted(os.listdir(folder), reverse=True):
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(dag|week)\.md$", f)
        if not m:
            continue
        with open(os.path.join(folder, f), encoding="utf-8") as fh:
            out.append({"datum": m.group(1), "soort": m.group(2), "tekst": fh.read()})
        if len(out) >= limit:
            break
    return out


def md_to_html(text: str) -> str:
    """Kleine, veilige markdown-weergave: koppen, lijsten, tabellen, vet, code. Alles wordt eerst ge-escaped."""
    def inline(s):
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        return s
    lines, out, i = text.splitlines(), [], 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|?$", lines[i + 1].strip()):
            head = [c.strip() for c in ln.strip("|").split("|")]
            rows = []
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append("<div class='tw'><table><tr>" + "".join(f"<th>{inline(h)}</th>" for h in head) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
                       + "</table></div>")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)", ln)
        if m:
            out.append(f"<h3 class='mdh'>{inline(m.group(2))}</h3>")
        elif re.match(r"^\s*([-*]|\d+\.)\s+", ln):
            items = []
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]))
                i += 1
            out.append("<ul class='mdl'>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ul>")
            continue
        elif ln.strip():
            out.append(f"<p class='mdp'>{inline(ln)}</p>")
        i += 1
    return "".join(out)


# ------------------------------------------------------------------ avatar en status (keuze Gitchi 23 okt 2026: A · 勝)
KANJI_PATH = "M29.07 18.23 28.73 18.35C29.39 19.72 30.1 21.71 30.16 23.4C32.53 25.64 35.55 20.94 29.07 18.23ZM21.98 20.19H24.16V26.41H21.98ZM40.71 18.17C40.34 19.66 39.34 22.52 38.5 24.55H36.64C37.23 22.68 37.66 20.78 37.98 18.95C38.82 18.85 39.06 18.6 39.13 18.2L34.55 17.45C34.43 19.79 34.12 22.21 33.56 24.55H28.08L28.33 25.42H33.31C33 26.6 32.59 27.78 32.09 28.9H27.67L27.92 29.77H31.69C30.63 31.92 29.23 33.88 27.36 35.5V20.59C27.89 20.47 28.27 20.25 28.42 20.07L25.31 17.64L23.88 19.32H22.51L18.8 17.95V29.9C18.8 35.53 18.87 41.57 17 46.27L17.4 46.52C20.67 43.16 21.61 38.83 21.89 34.63H24.16V42.22C24.16 42.6 24.06 42.78 23.6 42.78C23.16 42.78 21.17 42.66 21.17 42.66V43.09C22.26 43.31 22.73 43.65 23.07 44.15C23.35 44.62 23.47 45.46 23.54 46.52C26.96 46.21 27.36 44.9 27.36 42.6V36.15C30.44 34.57 32.65 32.33 34.24 29.77H39.22C40.4 32.39 42.08 34.32 44.45 35.69C44.82 33.98 45.72 32.92 46.97 32.61L47 32.26C45.2 31.77 43.45 30.93 41.99 29.77H46.1C46.53 29.77 46.84 29.62 46.91 29.28C45.76 28.22 43.83 26.69 43.83 26.69L42.08 28.9H40.96C39.9 27.91 39.03 26.73 38.38 25.42H45.32C45.76 25.42 46.1 25.26 46.16 24.92C44.98 23.89 43.11 22.46 43.11 22.46L41.43 24.55H39.19C40.87 23.12 42.61 21.28 43.51 20.16C44.17 20.22 44.54 19.91 44.67 19.6ZM21.98 27.32H24.16V33.76H21.92C21.98 32.45 21.98 31.14 21.98 29.9ZM36.33 25.42H37.79C38.07 26.69 38.44 27.85 38.85 28.9H34.74C35.36 27.78 35.89 26.6 36.33 25.42ZM33.28 31.39C33.37 32.76 33.37 34.19 33.21 35.59H29.17L29.45 36.5H33.12C32.59 40.17 31.04 43.72 27.36 46.18L27.61 46.55C33.34 44.34 35.58 40.67 36.45 36.5H39.81C39.62 40.29 39.31 42.29 38.78 42.72C38.57 42.91 38.35 42.94 37.88 42.94C37.35 42.94 35.89 42.88 35.02 42.78V43.22C36.01 43.44 36.76 43.78 37.17 44.25C37.57 44.68 37.66 45.52 37.63 46.46C39.1 46.46 40.18 46.14 41.02 45.55C42.39 44.56 42.89 42.29 43.17 36.99C43.79 36.9 44.17 36.71 44.35 36.5L41.24 33.95L39.53 35.59H36.61C36.76 34.66 36.85 33.7 36.92 32.73C37.63 32.64 37.98 32.36 38.07 31.86Z"


def avatar_svg(size: int = 40) -> str:
    """Avatar van de agent: ring in de KATSU-kleuren met het teken 勝 ('katsu', winnen) als vectorpad (geen font nodig)."""
    gid = f"ka{size}"
    return (f"<svg viewBox='0 0 64 64' width='{size}' height='{size}' role='img' aria-label='KATSU agent' style='flex:none'>"
            f"<defs><linearGradient id='{gid}' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#FF7AC3'/>"
            f"<stop offset='1' stop-color='#8F6BF2'/></linearGradient></defs>"
            f"<circle cx='32' cy='32' r='30' fill='#14102A' stroke='url(#{gid})' stroke-width='2.5'/>"
            f"<circle cx='32' cy='32' r='25' fill='url(#{gid})' opacity='.16'/>"
            f"<path d='{KANJI_PATH}' fill='#FBEAF6'/></svg>")


RUNS = ((7, 10), (19, 10))          # Belgische tijd van de agent-rondes (dagelijkse check en avondronde)


def next_run(now_be):
    """Volgende ronde van de agent na now_be (naïeve Belgische tijd)."""
    import pandas as pd
    now_be = pd.Timestamp(now_be)
    for day in (0, 1):
        for h, m in RUNS:
            t = now_be.normalize() + pd.Timedelta(days=day, hours=h, minutes=m)
            if t > now_be:
                return t
    return None


def last_status(repo_dir: str):
    """(datum, statusregel) van het nieuwste logboek, of (None, None)."""
    books = logbooks(repo_dir, limit=1)
    if not books:
        return None, None
    line = next((l.strip(" #*") for l in books[0]["tekst"].splitlines() if "Status" in l), None)
    return books[0]["datum"], line
