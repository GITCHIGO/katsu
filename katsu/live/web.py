"""
Dashboard van KATSU Live (spec §5), stijl B 'Glas Aurora' (gekozen door Gitchi, 21 okt 2026).
Kleine Flask-app met wachtwoord. Leest alleen een momentopname die de runner elke 10 s klaarzet; de noodknop zet
een verzoek klaar dat de runner uitvoert (MT5 wordt alleen vanuit de runner aangesproken).

Beveiliging (dashboard staat op internet via http, keuze Gitchi): wachtwoord ≥ 4 tekens (keuze Gitchi), max. 5 foute pogingen per
15 min per IP, sessiecookie (HttpOnly, SameSite=Strict), CSRF-sleutel op elke knop. Zonder https gaat het wachtwoord
onversleuteld over het net: gebruik een uniek wachtwoord dat je nergens anders gebruikt.
"""
from __future__ import annotations

import hmac
import os
import html
import secrets
import threading
import time
from collections import defaultdict, deque

import pandas as pd
from flask import Flask, abort, redirect, request, session

from katsu.live.broker import server_to_be
from katsu.live.scan import SETUPS

COLORS = {"Test #1 (FVG)": "#D9519A", "AMD-extra (#386)": "#8F6BF2", "Zone GBPUSD": "#189CBB"}   # gevalideerd (dataviz)
NAMES = {"Test #1 (FVG)": "Test #1", "AMD-extra (#386)": "AMD", "Zone GBPUSD": "Zone"}
DIGITS = {"EURUSD": 5, "GBPUSD": 5, "XAUUSD": 2}
e = html.escape


class Snapshot:
    """Gedeelde toestand tussen runner (schrijft) en dashboard (leest)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.data: dict = {}
        self.requests: deque = deque()

    def set(self, d: dict):
        with self.lock:
            self.data = d

    def get(self) -> dict:
        with self.lock:
            return dict(self.data)

    def request(self, what: str):
        with self.lock:
            self.requests.append(what)

    def take_requests(self) -> list[str]:
        with self.lock:
            out = list(self.requests)
            self.requests.clear()
            return out


# ------------------------------------------------------------------ opmaak

def fR(x, d=2):
    return "—" if x is None else ("+" if x >= 0 else "−") + f"{abs(x):.{d}f}R"


def fM(x, cur="€"):
    if x is None:
        return "—"
    if abs(x) < 0.005:
        return cur + "0,00"
    return ("+" if x >= 0 else "−") + cur + f"{abs(x):,.2f}".replace(",", " ").replace(".", ",")


def fP(x):
    return "—" if x is None else f"{round(100 * x)}%"


def tone(x):
    return "" if x is None else ("pos" if x >= 0 else "neg")


def be(t, fmt="%d-%m %H:%M"):
    if t in (None, "", "None"):
        return "—"
    return server_to_be(pd.Timestamp(t)).strftime(fmt)


def px(m, v):
    return "—" if v is None else f"{float(v):.{DIGITS.get(m, 5)}f}"


CSS = """
:root{color-scheme:dark;--bg:#0A0716;--fg:#EEEAFB;--muted:#B9B1D9;--dim:#9C93C2;--glass:rgba(255,255,255,.06);
--glass2:rgba(255,255,255,.10);--line:rgba(255,255,255,.12);--up:#5EF0B6;--down:#FF7A96;--warn:#FFC46B;
--ui:'Sora',system-ui,sans-serif;--mono:'IBM Plex Mono',ui-monospace,Menlo,monospace}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;color:var(--fg);font:14px/1.45 var(--ui);background:
radial-gradient(120% 60% at 0% 0%,rgba(255,62,165,.24),transparent 60%),radial-gradient(90% 50% at 100% 20%,rgba(124,92,255,.26),transparent 60%),
radial-gradient(80% 50% at 50% 100%,rgba(34,228,255,.12),transparent 60%),var(--bg);background-attachment:fixed}
a{color:#D7C9FF}
main{max-width:1080px;margin:0 auto;padding:16px 16px 104px;display:grid;grid-template-columns:minmax(0,1fr);gap:14px}
main>*,.cols>*{min-width:0}
header{display:flex;align-items:center;justify-content:space-between;gap:12px}
.brand{font-weight:700;font-size:20px;letter-spacing:.04em;background:linear-gradient(90deg,#FF7AC3,#A98BFF,#6EE7FF);
-webkit-background-clip:text;background-clip:text;color:transparent}
.status{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);flex-wrap:wrap}
.dot{width:8px;height:8px;border-radius:50%;background:var(--up);box-shadow:0 0 10px var(--up)}
.dot.off{background:var(--down);box-shadow:0 0 10px var(--down)}
.stop{width:52px;height:52px;border-radius:50%;border:1px solid rgba(255,122,150,.6);background:rgba(255,122,150,.12);
color:#FFB1C2;font:700 11px var(--ui);cursor:pointer;text-decoration:none;display:grid;place-items:center;flex:none}
.card{background:var(--glass);border:1px solid var(--line);border-radius:22px;padding:16px;backdrop-filter:blur(18px);min-width:0}
.hero{display:grid;gap:8px}
.big{font:600 34px/1.1 var(--mono)}
.k{font-size:12px;color:var(--muted)}
.mono{font-family:var(--mono)}
.pos{color:var(--up)}.neg{color:var(--down)}.warn{color:var(--warn)}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.chip{padding:7px 12px;border-radius:999px;background:var(--glass);font-size:12px;color:var(--muted);text-decoration:none}
.chip.on{background:rgba(255,255,255,.16);color:#fff;font-weight:600}
.list{display:grid;gap:8px}
.item{display:flex;gap:12px;align-items:center;padding:12px 14px;border-radius:18px;background:var(--glass);border:1px solid rgba(255,255,255,.10)}
.bar{width:6px;align-self:stretch;border-radius:6px;flex:none}
.grow{flex:1;min-width:0;display:grid;gap:3px}
.row{display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.tag{font-size:11px;color:#D7C9FF;white-space:nowrap}
.sub{font:500 12px var(--mono);color:#CFC8EA;overflow-wrap:anywhere}
.meta{font-size:11px;color:var(--dim)}
.run{background:linear-gradient(90deg,rgba(94,240,182,.12),rgba(255,255,255,.04));border-color:rgba(94,240,182,.35)}
.track{position:relative;height:6px;border-radius:6px;background:rgba(255,255,255,.12);margin:6px 0 2px}
.track i{position:absolute;top:-4px;width:14px;height:14px;border-radius:50%;background:#fff;box-shadow:0 0 12px #A98BFF}
.track b{position:absolute;top:0;bottom:0;left:0;border-radius:6px;background:rgba(255,122,150,.55)}
.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.mini{padding:12px 10px;border-radius:16px;background:var(--glass);border:1px solid rgba(255,255,255,.10);display:grid;gap:4px;min-width:0}
.kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.kpi{padding:12px;border-radius:16px;background:var(--glass);border:1px solid rgba(255,255,255,.10);display:grid;gap:2px}
.kpi .v{font:600 18px var(--mono)}
h2{margin:0 0 8px;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:600}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th{color:var(--dim);font-weight:500;text-align:right;padding:6px;border-bottom:1px solid var(--line);white-space:nowrap}
td{text-align:right;padding:6px;font-family:var(--mono);border-bottom:1px solid rgba(255,255,255,.06);white-space:nowrap}
th:first-child,td:first-child{text-align:left;font-family:var(--ui)}
.banner{padding:12px 14px;border-radius:16px;border:1px solid rgba(255,196,107,.5);background:rgba(255,196,107,.10);font-size:13px}
.banner.red{border-color:rgba(255,122,150,.6);background:rgba(255,122,150,.12)}
.btn{display:inline-block;padding:10px 16px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.12);
color:#fff;font:600 13px var(--ui);cursor:pointer;text-decoration:none}
.btn.red{background:rgba(255,122,150,.25);border-color:rgba(255,122,150,.6)}
nav{position:fixed;left:12px;right:12px;bottom:12px;max-width:560px;margin:0 auto;padding:6px;border-radius:22px;
background:rgba(20,16,42,.78);border:1px solid var(--line);backdrop-filter:blur(16px);display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;z-index:5}
nav a{height:46px;border-radius:16px;display:flex;align-items:center;justify-content:center;text-decoration:none;color:var(--muted);font-size:12px;min-width:0}
.msg{max-width:88%;padding:10px 12px;border-radius:16px;font-size:13.5px;line-height:1.5;overflow-wrap:anywhere}
.msg.me{margin-left:auto;background:linear-gradient(90deg,rgba(255,122,195,.22),rgba(169,139,255,.22));border:1px solid rgba(169,139,255,.35)}
.msg.ag{background:var(--glass);border:1px solid rgba(110,231,255,.28)}
.msg .meta{margin-top:4px}
textarea{width:100%;min-height:84px;padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.06);color:#fff;font:14px var(--ui);resize:vertical}
.mdh{margin:10px 0 4px;font-size:14px}.mdp{margin:4px 0}.mdl{margin:4px 0 4px 18px;padding:0}
details summary{cursor:pointer;color:var(--muted);font-size:13px}
code{font-family:var(--mono);font-size:12px}
nav a.on{background:linear-gradient(90deg,rgba(255,122,195,.35),rgba(169,139,255,.35));color:#fff;font-weight:600}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--muted)}
.legend span{display:flex;align-items:center;gap:6px}.legend i{width:10px;height:3px;border-radius:2px;display:inline-block}
.empty{color:var(--dim);font-size:13px;padding:6px 2px}
input{width:100%;padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.06);color:#fff;font:15px var(--ui)}
.svgwrap{position:relative}
.tip{position:absolute;pointer-events:none;padding:6px 8px;border-radius:10px;background:rgba(20,16,42,.95);border:1px solid var(--line);font:12px var(--mono);display:none;white-space:nowrap}
@media(min-width:900px){
 .cols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;align-items:start}
 .kpis{grid-template-columns:repeat(4,minmax(0,1fr))}
}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" '
         'href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">')


def page(title, body, tab=None, refresh=None):
    nav = ""
    if tab is not None:
        nav = "<nav aria-label='Hoofdmenu'>" + "".join(
            f"<a href='{u}' class='{'on' if tab == k else ''}'>{k}</a>"
            for k, u in (("Nu", "/"), ("Resultaten", "/resultaten"), ("Controle", "/controle"), ("Agent", "/agent"),
                         ("Log", "/log"))) + "</nav>"
    meta = f"<meta http-equiv='refresh' content='{refresh}'>" if refresh else ""
    return (f"<!doctype html><html lang='nl'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>{e(title)}</title>{meta}{FONTS}<style>{CSS}</style>"
            f"</head><body><main>{body}</main>{nav}</body></html>")


def header(s: dict, csrf: str | None = None):
    ok = s.get("connected")
    acc = s.get("account") or {}
    kind = "demo" if acc.get("demo") else ("LIVE" if acc else "?")
    nxt = s.get("next_scan")
    left = ""
    if nxt and s.get("now"):
        sec = max(0, int((pd.Timestamp(nxt) - pd.Timestamp(s["now"])).total_seconds()))
        left = f" · volgende {sec // 60:02d}:{sec % 60:02d}"
    st = (f"<span style='white-space:nowrap'><span class='dot {'off' if not ok else ''}' style='display:inline-block;margin-right:6px'></span>"
          f"{'verbonden' if ok else 'NIET verbonden'}</span> · {kind} "
          f"#{e(str(acc.get('login', '—')))} · scan {be(s.get('last_scan_done'), '%H:%M')}{left}")
    return (f"<header><div style='display:grid;gap:4px;min-width:0'><span class='brand'>katsu live</span>"
            f"<span class='status'>{st}</span></div><a class='stop' href='/noodknop' aria-label='Noodknop: alles stoppen'>STOP</a></header>")


def banners(s, csrf):
    out = ""
    if s.get("mode") == "loggen":
        out += ("<div class='banner'>Stand <b>loggen</b>: KATSU zoekt setups en meldt ze, maar stuurt <b>geen orders</b> "
                "naar MT5 (eerste week, spec §7.5).</div>")
    if s.get("paused"):
        out += (f"<div class='banner red'><b>Gepauzeerd</b> (noodknop). Er worden geen nieuwe orders geplaatst."
                f"<form method='post' action='/hervat' style='margin-top:10px'><input type='hidden' name='csrf' value='{csrf}'>"
                f"<button class='btn'>Hervat de scanner</button></form></div>")
    for err in (s.get("errors") or [])[:3]:
        out += f"<div class='banner red'>{e(be(err['time']))} · {e(err['text'])}</div>"
    return out


def spark(points, w=320, h=54, color="url(#g)"):
    """Lijn van cumulatieve R. points = [(tijd, R), ...]."""
    if len(points) < 2:
        return "<div class='empty'>Nog te weinig gesloten trades voor een curve.</div>"
    ys = [0.0] + [p[1] for p in points]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1.0
    xs = [i * w / (len(ys) - 1) for i in range(len(ys))]
    pts = " ".join(f"{x:.1f},{h - 4 - (y - lo) / span * (h - 8):.1f}" for x, y in zip(xs, ys))
    zero = h - 4 - (0 - lo) / span * (h - 8)
    return (f"<svg viewBox='0 0 {w} {h}' width='100%' height='{h}' role='img' aria-label='Curve cumulatieve R'>"
            "<defs><linearGradient id='g' x1='0' x2='1'><stop offset='0' stop-color='#FF7AC3'/>"
            "<stop offset='1' stop-color='#6EE7FF'/></linearGradient></defs>"
            f"<line x1='0' x2='{w}' y1='{zero:.1f}' y2='{zero:.1f}' stroke='rgba(255,255,255,.18)' stroke-dasharray='3 4'/>"
            f"<polyline fill='none' stroke='{color}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' points='{pts}'/></svg>")


def curves(setups: dict):
    """Eén lijn per setup (cumulatieve R per gesloten trade), legende + label aan het einde, hover-tooltip."""
    series = {n: s["curve"] for n, s in setups.items() if s["curve"]}
    if not series:
        return "<div class='empty'>Nog geen gesloten trades.</div>"
    w, h, padl, padr = 480, 230, 40, 122
    allp = [(pd.Timestamp(t), r) for c in series.values() for t, r in c]
    t1 = max(t for t, _ in allp)
    t0 = min(t for t, _ in allp)
    t0 = t0 - max((t1 - t0) * 0.04, pd.Timedelta(hours=6))          # elke lijn start op 0R, net vóór de eerste trade
    ys = [0.0] + [r for _, r in allp]
    lo, hi = min(ys), max(ys)
    lo, hi = (lo - 0.5, hi + 0.5) if hi - lo < 1 else (lo, hi)
    tx = lambda t: padl + ((pd.Timestamp(t) - t0) / ((t1 - t0) or pd.Timedelta(1))) * (w - padl - padr)
    ty = lambda r: 12 + (hi - r) / (hi - lo) * (h - 30)
    grid = ""
    for v in sorted({int(round(lo)), 0, int(round(hi))}):
        grid += (f"<line x1='{padl}' x2='{w - padr}' y1='{ty(v):.1f}' y2='{ty(v):.1f}' stroke='rgba(255,255,255,{.22 if v == 0 else .08})'/>"
                 f"<text x='{padl - 6}' y='{ty(v) + 4:.1f}' text-anchor='end' font-size='12' fill='#9C93C2'>{v:+d}R</text>")
    lines, dots, labels = "", "", []
    for n, c in series.items():
        col = COLORS[n]
        pts = [(tx(t0), ty(0))] + [(tx(t), ty(r)) for t, r in c]
        lines += (f"<polyline fill='none' stroke='{col}' stroke-width='2' stroke-linejoin='round' "
                  f"points='{' '.join(f'{x:.1f},{y:.1f}' for x, y in pts)}'/>")
        labels.append([pts[-1][1], n, c[-1][1]])
        for (t, r), (x, y) in zip(c, pts[1:]):
            dots += (f"<circle cx='{x:.1f}' cy='{y:.1f}' r='10' fill='transparent' data-t='{e(NAMES[n])} · {be(t)} · {fR(r, 2)}'/>"
                     f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' fill='{col}' stroke='#14102A' stroke-width='2' pointer-events='none'/>")
    labels.sort()
    for i in range(1, len(labels)):                                   # labels niet over elkaar
        labels[i][0] = max(labels[i][0], labels[i - 1][0] + 16)
    for y, n, r in labels:
        lines += (f"<text x='{w - padr + 8}' y='{y + 4:.1f}' font-size='13' fill='#EEEAFB'>"
                  f"<tspan fill='{COLORS[n]}'>●</tspan> {NAMES[n]} {fR(r, 1)}</text>")
    legend = "<div class='legend'>" + "".join(f"<span><i style='background:{COLORS[n]}'></i>{NAMES[n]}</span>" for n in series) + "</div>"
    js = ("<script>document.querySelectorAll('.svgwrap').forEach(w=>{const tip=w.querySelector('.tip');"
          "w.querySelectorAll('circle[data-t]').forEach(c=>{c.addEventListener('mouseenter',ev=>{tip.textContent=c.dataset.t;"
          "tip.style.display='block';const b=w.getBoundingClientRect(),r=c.getBoundingClientRect();"
          "tip.style.left=Math.min(r.left-b.left+12,b.width-170)+'px';tip.style.top=(r.top-b.top-30)+'px'});"
          "c.addEventListener('mouseleave',()=>tip.style.display='none')})})</script>")
    return (f"{legend}<div class='svgwrap'><svg viewBox='0 0 {w} {h}' width='100%' role='img' aria-label='Cumulatieve R per setup'>"
            f"{grid}{lines}{dots}</svg><div class='tip'></div></div>{js}")


def order_item(o, cur, live=None):
    m = o["market"]
    col = COLORS[o["setup"]]
    dcol = "var(--up)" if o["direction"] == "LONG" else "var(--down)"
    if o["state"] == "gevuld":
        r = (live or {}).get(o["id"])
        tpR = (o["direction"] == "LONG" and 1 or -1) * (o["tp"] - o["fill_px"]) / o["risk_px"] if o.get("risk_px") else 2
        pos = 0 if r is None else max(0.0, min(1.0, (r + 1) / (1 + tpR)))
        red = 1 / (1 + tpR)
        return (f"<div class='item run'><div class='bar' style='background:{col}'></div><div class='grow'>"
                f"<div class='row'><span><b>{m}</b> · <span style='color:{dcol}'>{o['direction']}</span></span>"
                f"<span class='mono {tone(r)}' style='font-size:20px;font-weight:600'>{fR(r)}</span></div>"
                f"<div class='track'><b style='width:{red * 100:.0f}%'></b><i style='left:calc({pos * 100:.0f}% - 7px)'></i></div>"
                f"<div class='row meta'><span>SL {px(m, o['sl'])}</span><span>{NAMES[o['setup']]} · sinds {be(o['fill_time'], '%d-%m %H:%M')}</span>"
                f"<span>TP {px(m, o['tp'])}</span></div></div></div>")
    lab = {"geplaatst": "limiet bij MT5", "wacht": "wacht (andere trade loopt)", "log": "alleen gelogd"}.get(o["state"], o["state"])
    until = be(o["valid_until"]) if o.get("valid_until") else (f"{o['valid_bars']} candles" if o.get("valid_bars") else "—")
    entry = px(m, o["limit"]) if o.get("limit") is not None else "markt"
    return (f"<div class='item'><div class='bar' style='background:{dcol}'></div><div class='grow'>"
            f"<div class='row'><span><b>{m}</b> · <span style='color:{dcol}'>{o['direction']}</span></span>"
            f"<span class='tag'>{NAMES[o['setup']]}</span></div>"
            f"<div class='sub'>@ {entry} · SL {px(m, o.get('sl'))} · TP {px(m, o.get('tp'))}</div>"
            f"<div class='meta'>{e(lab)} · signaal {be(o['t_sig'])} · geldig tot {e(until)} · {o['lot']:.2f} lot</div></div></div>")


def summary_table(rows, cur):
    head = ["", "trades", "W/V", "winrate", "gem.", "totaal", "pips", "winst", "verlies", "netto"]
    body = ""
    for name, s in rows:
        body += (f"<tr><td>{e(name)}</td><td>{s['trades']}</td><td>{s['winst']}/{s['verlies']}</td><td>{fP(s['winrate'])}</td>"
                 f"<td class='{tone(s['gem_R'])}'>{fR(s['gem_R'])}</td><td class='{tone(s['totaal_R'])}'>{fR(s['totaal_R'], 1)}</td>"
                 f"<td class='{tone(s['pips'])}'>{s['pips']:+.1f}</td><td class='pos'>{fM(s['winst_geld'], cur)}</td>"
                 f"<td class='neg'>{fM(s['verlies_geld'], cur)}</td><td class='{tone(s['netto'])}'>{fM(s['netto'], cur)}</td></tr>")
    return "<div class='tw'><table><tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr>" + body + "</table></div>"


# ------------------------------------------------------------------ app

def make_app(snap: Snapshot, password: str, secret: str, logbook=None, agent: dict | None = None):
    app = Flask(__name__)
    app.secret_key = secret
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                      PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30)
    fails: dict = defaultdict(deque)
    all_fails: deque = deque()          # alle IP's samen: max. 20 foute pogingen per 24 u (kort wachtwoord)

    def logged_in():
        return session.get("ok") is True

    def csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(24)
        return session["csrf"]

    def check_csrf():
        if not hmac.compare_digest(request.form.get("csrf", ""), session.get("csrf", "-")):
            abort(400)

    @app.before_request
    def guard():
        if request.endpoint in ("login", "static"):
            return None
        if not logged_in():
            return redirect("/login")
        return None

    @app.after_request
    def headers(resp):
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/login", methods=["GET", "POST"])
    def login():
        ip = request.remote_addr or "?"
        q = fails[ip]
        while q and q[0] < time.time() - 900:
            q.popleft()
        while all_fails and all_fails[0] < time.time() - 86400:
            all_fails.popleft()
        msg = ""
        if request.method == "POST":
            if len(q) >= 5:
                return page("KATSU Live", "<div class='card'>Te veel foute pogingen. Probeer over 15 minuten opnieuw.</div>"), 429
            if len(all_fails) >= 20:
                return page("KATSU Live", "<div class='card'>Inloggen staat 24 uur dicht: te veel foute pogingen (van "
                                          "verschillende plaatsen). KATSU blijft gewoon draaien.</div>"), 429
            if hmac.compare_digest(request.form.get("pw", "").encode(), password.encode()):
                session.clear()
                session["ok"] = True
                session.permanent = True
                return redirect("/")
            q.append(time.time())
            all_fails.append(time.time())
            time.sleep(1.0)
            msg = "<div class='banner red'>Fout wachtwoord.</div>"
        body = (f"<div class='card' style='max-width:380px;margin:12vh auto 0;display:grid;gap:12px'>"
                f"<span class='brand'>katsu live</span>{msg}<form method='post' style='display:grid;gap:10px'>"
                f"<label class='k' for='pw'>Wachtwoord</label><input id='pw' name='pw' type='password' autocomplete='current-password' autofocus>"
                f"<button class='btn'>Inloggen</button></form></div>")
        return page("KATSU Live — inloggen", body)

    @app.route("/uitloggen")
    def logout():
        session.clear()
        return redirect("/login")

    @app.route("/")
    def nu():
        s = snap.get()
        cur = s.get("cur", "€")
        orders = s.get("orders", [])
        month = s.get("results_month") or {}
        a = month.get("algemeen") or {}
        live = s.get("live_r", {})
        running = [o for o in orders if o["state"] == "gevuld"]
        pending = [o for o in orders if o["state"] in ("geplaatst", "wacht")]
        recent_log = [o for o in orders if o["state"] == "log"][-5:][::-1]
        hero = (f"<section class='card hero'><div class='row'><div><div class='k'>netto deze maand</div>"
                f"<div class='big {tone(a.get('netto'))}'>{fM(a.get('netto'), cur)}</div></div>"
                f"<div class='mono k' style='text-align:right'>{fR(a.get('totaal_R'), 1)}<br>{a.get('trades', 0)} trades · {fP(a.get('winrate'))}</div></div>"
                f"{spark(_merge_curves(month.get('setups', {})))}</section>")
        chips = (f"<div class='chips'><span class='chip'>Orders {len(pending)}</span><span class='chip'>Lopend {len(running)}</span>"
                 f"<span class='chip'>Vandaag gesloten {s.get('closed_today', 0)}</span></div>")
        items = "".join(order_item(o, cur, live) for o in running) + "".join(order_item(o, cur) for o in pending)
        if recent_log:
            items += "<h2 style='margin-top:6px'>Laatste signalen (alleen gelogd)</h2>" + "".join(order_item(o, cur) for o in recent_log)
        if not items:
            items = "<div class='empty'>Geen open orders of trades. KATSU wacht op de volgende setup.</div>"
        minis = ""
        for name, st in (month.get("setups") or {}).items():
            minis += (f"<div class='mini'><span class='k'>{NAMES[name]}</span><span class='mono {tone(st['netto'])}' "
                      f"style='font-weight:600;font-size:15px'>{fM(st['netto'], cur)}</span>"
                      f"<span class='meta mono'>{st['trades']} tr · {fP(st['winrate'])}</span></div>")
        body = (header(s) + banners(s, csrf()) + hero + chips + f"<section class='list'>{items}</section>"
                + (f"<section class='grid3'>{minis}</section>" if minis else ""))
        return page("KATSU Live", body, "Nu", refresh=20)

    @app.route("/resultaten")
    def resultaten():
        s = snap.get()
        cur = s.get("cur", "€")
        per = request.args.get("p", "maand")
        r = (s.get("results_month") if per == "maand" else s.get("results_all")) or {}
        a = r.get("algemeen") or {}
        chips = ("<div class='chips'>" + "".join(f"<a class='chip {'on' if per == k else ''}' href='?p={k}'>{lab}</a>"
                                                 for k, lab in (("maand", "Deze maand"), ("alles", "Alles"))) + "</div>")
        kp = lambda v, k, c="": f"<div class='kpi'><span class='v {c}'>{v}</span><span class='k'>{k}</span></div>"
        kpis = ("<section class='kpis'>" + kp(a.get("trades", 0), "trades") + kp(fP(a.get("winrate")), "winrate")
                + kp(fR(a.get("gem_R")), "gem. per trade", tone(a.get("gem_R"))) + kp(fR(a.get("totaal_R"), 1), "totaal", tone(a.get("totaal_R")))
                + kp(fM(a.get("winst_geld"), cur), f"totale winst ({a.get('winst', 0)})", "pos")
                + kp(fM(a.get("verlies_geld"), cur), f"totaal verlies ({a.get('verlies', 0)})", "neg")
                + kp(fM(a.get("netto"), cur), "netto", tone(a.get("netto"))) + kp(r.get("lopend", 0), "lopen nog") + "</section>")
        setups = r.get("setups") or {}
        t1 = summary_table([(NAMES[n], st) for n, st in setups.items()], cur)
        t2 = summary_table([(f"{NAMES[n]} · {m}", ps) for n, st in setups.items() for m, ps in st["per_pair"].items()], cur)
        trades = r.get("trades") or []
        rows = "".join(
            f"<tr><td>{be(o['exit_time'])}</td><td>{NAMES[o['setup']]}</td><td>{o['market']}</td><td>{o['direction']}</td>"
            f"<td>{px(o['market'], o['fill_px'])}</td><td>{px(o['market'], o['exit_px'])}</td><td>{e(str(o.get('exit_reason')))}</td>"
            f"<td class='{tone(o['r_net'])}'>{fR(o['r_net'])}</td><td class='{tone(o['pips'])}'>{o['pips']:+.1f}</td>"
            f"<td class='{tone(o['net'])}'>{fM(o['net'], cur)}</td></tr>" for o in trades[:100])
        tl = ("<div class='tw'><table><tr><th>gesloten</th><th>setup</th><th>pair</th><th>richting</th><th>entry</th><th>uit</th>"
              f"<th>uitkomst</th><th>R</th><th>pips</th><th>netto</th></tr>{rows}</table></div>") if rows else "<div class='empty'>Nog geen gesloten trades.</div>"
        body = (header(s) + chips + kpis
                + f"<div class='cols'><section class='card'><h2>Curve per setup (R)</h2>{curves(setups)}</section>"
                + f"<section class='card'><h2>Per setup</h2>{t1}</section></div>"
                + f"<section class='card'><h2>Per setup en pair</h2>{t2}</section>"
                + f"<section class='card'><h2>Trades</h2>{tl}<p class='meta'>Bedragen = echte MT5-cijfers (winst + commissie + swap) "
                  f"in {e(cur)}. R = netto / bedrag dat op het spel stond bij de vulling. Tijden in Belgische tijd.</p></section>"
                + "<p class='meta'>Stopregels per setup: na 20 trades gemiddeld onder −0,3R → stoppen · na 40 trades onder 0 → stoppen.</p>")
        return page("KATSU Live — resultaten", body, "Resultaten")

    @app.route("/controle")
    def controle():
        s = snap.get()
        c = s.get("control") or {}
        sg = c.get("signalen") or {}
        pct = c.get("overeenkomst")
        n = c.get("n_trades", 0)
        verdict = ("Nog geen trades om te vergelijken." if pct is None else
                   ("✓ boven de 90 %-grens" if pct >= 0.9 else "✗ ONDER de 90 %-grens: niets verder bouwen (werkregel 5)"))
        head = (f"<section class='kpis'><div class='kpi'><span class='v {'' if pct is None else ('pos' if pct >= .9 else 'neg')}'>{fP(pct)}</span>"
                f"<span class='k'>overeenkomst trades ({c.get('n_gelijk', 0)}/{n})</span></div>"
                f"<div class='kpi'><span class='v'>{fP(sg.get('pct'))}</span><span class='k'>signalen gelijk ({sg.get('gelijk', 0)}: "
                f"backtest {sg.get('backtest', 0)}, live {sg.get('live', 0)})</span></div>"
                f"<div class='kpi'><span class='v'>{min(n, 20)}/20</span><span class='k'>eerste 20 trades vergeleken</span></div>"
                f"<div class='kpi'><span class='v' style='font-size:13px'>{e(verdict)}</span><span class='k'>oordeel</span></div></section>")
        rows = ""
        for t in c.get("trades", []):
            st = t["status"]
            cl = "pos" if st.startswith("gelijk") else "neg"
            m = t["markt"]
            slip = "—" if t["slippage_pips"] is None else f"{t['slippage_pips']:+.1f}"
            com = "—" if t["commissie"] is None else f"{t['commissie']:.2f}"
            swp = "—" if t["swap"] is None else f"{t['swap']:.2f}"
            rows += (f"<tr><td>{be(t['t_sig'])}</td><td>{e(t['setup'])}</td><td>{m}</td><td>{t['richting']}</td>"
                     f"<td>{px(m, t['bt_fill'])}</td><td>{px(m, t['live_fill'])}</td><td>{slip}</td>"
                     f"<td>{e(str(t['bt_uit'] or '—'))}</td><td>{e(str(t['live_uit'] or '—'))}</td>"
                     f"<td>{fR(t['bt_R'])}</td><td>{fR(t['live_R'])}</td><td>{com}</td><td>{swp}</td>"
                     f"<td class='{cl}'>{e(st)}</td></tr>")
        table = ("<div class='tw'><table><tr><th>signaal</th><th>setup</th><th>pair</th><th>richting</th><th>vulling backtest</th>"
                 "<th>vulling MT5</th><th>slippage (pips)</th><th>uit backtest</th><th>uit MT5</th><th>R backtest</th><th>R MT5</th>"
                 f"<th>commissie</th><th>swap</th><th>oordeel</th></tr>{rows}</table></div>") if rows else "<div class='empty'>Nog geen trades.</div>"
        only = ""
        if sg.get("alleen_backtest") or sg.get("alleen_live"):
            only = ("<section class='card'><h2>Signalen die niet overeenkomen</h2>"
                    + "".join(f"<div class='meta mono'>alleen backtest · {e(k)}</div>" for k in sg.get("alleen_backtest", [])[:30])
                    + "".join(f"<div class='meta mono'>alleen live · {e(k)}</div>" for k in sg.get("alleen_live", [])[:30]) + "</section>")
        body = (header(s) + head + f"<section class='card'><h2>Trade per trade: backtest ↔ MT5</h2>{table}"
                f"<p class='meta'>Backtest = dezelfde code als de vooruit-test op de MT5-candles sinds de start ({be(c.get('start'))}). "
                f"'Gelijk' = in beide, zelfde uitkomst (TP/SL/tijd) en minder dan 0,25R verschil. Slippage + = slechter dan de backtest. "
                f"Laatst berekend: {be(s.get('control_time'))}.</p></section>" + only)
        return page("KATSU Live — controle", body, "Controle")

    @app.route("/agent", methods=["GET", "POST"])
    def agent_page():
        from katsu.live import agentbox as AB
        s = snap.get()
        if agent is None:
            return page("KATSU Live — agent", header(s) + "<div class='empty'>Agent niet ingesteld.</div>", "Agent")
        if request.method == "POST":
            check_csrf()
            AB.add_question(agent["vragen"], request.form.get("vraag", ""))
            return redirect("/agent")
        msgs = AB.thread(agent["vragen"], os.path.join(agent["repo"], "antwoorden.json"))
        chat = "".join(
            f"<div class='msg {'me' if m['van'] == 'gitchi' else 'ag'}'>"
            + (e(m["tekst"]).replace(chr(10), "<br>") if m["van"] == "gitchi" else AB.md_to_html(m["tekst"]))
            + f"<div class='meta'>{'jij' if m['van'] == 'gitchi' else 'agent'} · {_utc_be(m.get('tijd'))}"
            + (" · wacht op antwoord" if m.get("open") else "") + "</div></div>" for m in msgs[-60:])
        if not chat:
            chat = ("<div class='empty'>Nog geen berichten. Stel hieronder een vraag aan de agent, bv. "
                    "\"Waarom was er gisteren geen trade op goud?\"</div>")
        books = AB.logbooks(agent["repo"])
        latest = books[0] if books else None
        lb = ""
        if latest:
            lb = (f"<section class='card'><h2>Laatste logboek · {e(latest['soort'])} · {e(latest['datum'])}</h2>"
                  f"{AB.md_to_html(latest['tekst'])}</section>")
            older = "".join(f"<details><summary>{e(b['soort'])} · {e(b['datum'])}</summary>{AB.md_to_html(b['tekst'])}</details>"
                            for b in books[1:])
            if older:
                lb += f"<section class='card' style='display:grid;gap:8px'><h2>Eerdere logboeken</h2>{older}</section>"
        else:
            lb = ("<section class='card'><div class='empty'>Nog geen logboek. De agent schrijft elke dag om 07:10 een korte "
                  "check en op zondag om 10:10 een volledige review.</div></section>")
        form = (f"<form method='post' class='card' style='display:grid;gap:10px'>"
                f"<input type='hidden' name='csrf' value='{csrf()}'>"
                f"<label class='k' for='vraag'>Vraag aan de agent</label>"
                f"<textarea id='vraag' name='vraag' maxlength='2000' placeholder='Typ je vraag…'></textarea>"
                f"<button class='btn'>Versturen</button>"
                f"<span class='meta'>De agent leest alles en antwoordt om 07:10 en 19:10; het antwoord staat hier binnen "
                f"±1 uur daarna. Hij kan niets aanpassen: voorstellen keur je goed in een chat met Claude.</span></form>")
        body = (header(s) + f"<section class='card' style='display:grid;gap:10px'><h2>Gesprek met de agent</h2>{chat}</section>"
                + form + lb)
        return page("KATSU Live — agent", body, "Agent")

    @app.route("/log")
    def log():
        s = snap.get()
        f = request.args.get("f", "alles")
        groups = {"alles": None, "orders": {"geplaatst", "gevuld", "gesloten", "geannuleerd", "wacht", "geblokkeerd", "geweigerd"},
                  "signalen": {"signaal", "gemist"}, "fouten": {"fout"}, "scans": {"scan"}}
        evs = logbook.tail(300) if logbook is not None else []
        if groups[f] is not None:
            evs = [x for x in evs if x.get("kind") in groups[f]]
        chips = "<div class='chips'>" + "".join(f"<a class='chip {'on' if f == k else ''}' href='?f={k}'>{k}</a>" for k in groups) + "</div>"
        rows = "".join(f"<div class='item' style='padding:9px 12px'><div class='grow'><div class='row'><span class='meta mono'>{be(x.get('time'), '%d-%m %H:%M:%S')}</span>"
                       f"<span class='tag'>{e(str(x.get('kind')))}</span></div><div class='sub' style='font-family:var(--ui)'>{e(str(x.get('text')))}</div></div></div>"
                       for x in evs[:200]) or "<div class='empty'>Nog niets gelogd.</div>"
        body = header(s) + chips + f"<section class='list'>{rows}</section>"
        return page("KATSU Live — log", body, "Log", refresh=30)

    @app.route("/noodknop", methods=["GET", "POST"])
    def noodknop():
        if request.method == "POST":
            check_csrf()
            snap.request("kill")
            return page("KATSU Live", "<div class='card' style='display:grid;gap:12px'><b>Noodknop verstuurd.</b>"
                                      "<span class='k'>Binnen 10 seconden worden alle KATSU-orders geannuleerd en alle KATSU-trades gesloten. "
                                      "De scanner staat daarna op pauze.</span><a class='btn' href='/'>Terug</a></div>")
        body = (f"<div class='card' style='display:grid;gap:12px;max-width:460px;margin:10vh auto 0'><b style='font-size:18px'>Alles stoppen?</b>"
                f"<span class='k'>Alle klaarstaande KATSU-orders worden geannuleerd, alle lopende KATSU-trades worden meteen gesloten "
                f"tegen de marktprijs, en de scanner pauzeert. Andere trades op je account worden niet aangeraakt.</span>"
                f"<form method='post'><input type='hidden' name='csrf' value='{csrf()}'><button class='btn red'>Ja, alles stoppen</button></form>"
                f"<a class='btn' href='/'>Annuleren</a></div>")
        return page("KATSU Live — noodknop", body)

    @app.route("/hervat", methods=["POST"])
    def hervat():
        check_csrf()
        snap.request("resume")
        return redirect("/")

    return app


def _utc_be(t):
    """ISO-tijd (UTC of met tijdzone) → Belgische tijd als tekst."""
    if not t:
        return "—"
    try:
        ts = pd.Timestamp(t)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts.tz_convert("Europe/Brussels").strftime("%d-%m %H:%M")
    except Exception:
        return str(t)[:16]


def _merge_curves(setups: dict):
    """Cumulatieve R van alle setups samen (voor de kleine curve bovenaan)."""
    deltas = []
    for s in setups.values():
        prev = 0.0
        for t, r in s.get("curve", []):
            deltas.append((t, r - prev))
            prev = r
    deltas.sort(key=lambda x: x[0])
    cum, out = 0.0, []
    for t, d in deltas:
        cum += d
        out.append((t, cum))
    return out


__all__ = ["Snapshot", "make_app", "SETUPS"]
