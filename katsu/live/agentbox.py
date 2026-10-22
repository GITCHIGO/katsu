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
