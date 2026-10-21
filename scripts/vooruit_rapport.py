"""
Maakt van een vooruit-test-JSON (scripts/vooruittest.py) een leesbare pagina (ook op gsm).
Gebruik: python -m scripts.vooruit_rapport <rapport.json> <uit.html>
"""
import html
import json
import sys

import pandas as pd

BE = pd.Timedelta(hours=1)               # Belgische tijd = server − 1 u


def fR(x, d=2):
    return "—" if x is None else ("+" if x >= 0 else "−") + f"{abs(x):.{d}f}R"


def fUSD(x):
    return "—" if x is None else ("+" if x >= 0 else "−") + f"${abs(x):,.2f}".replace(",", " ")


def fPct(x):
    return "—" if x is None else f"{round(100 * x)}%"


def cls(x):
    return "" if x is None else ("pos" if x >= 0 else "neg")


def row(cells):
    return "<tr>" + "".join(f'<td class="{c}">{html.escape(str(v))}</td>' for v, c in cells) + "</tr>"


def summary_cells(name, s, extra=None):
    cells = [(name, ""), (s["trades"], ""), (f'{s["winst"]}/{s["verlies"]}', ""), (fPct(s["winrate"]), ""),
             (fR(s["gem_R"]), cls(s["gem_R"])), (fR(s["gem_win_R"]), "pos" if s["gem_win_R"] else ""),
             (fR(s["gem_verlies_R"]), "neg" if s["gem_verlies_R"] else ""), (fR(s["totaal_R"], 1), cls(s["totaal_R"])),
             (f'{s["pips"]:+.1f}', cls(s["pips"])), (fUSD(s.get("winst_usd")), "pos"), (fUSD(s.get("verlies_usd")), "neg"),
             (fUSD(s["usd"]), cls(s["usd"])), (s["lopend"], "")]
    if extra is not None:
        cells.append((extra, "note"))
    return cells


HEAD = ["", "trades", "W/V", "winrate", "gem.", "gem. winnaar", "gem. verliezer", "totaal", "pips", "winst $", "verlies $", "netto $", "lopend"]


def table(head, rows):
    return ('<div class="tw"><table><tr>' + "".join(f"<th>{html.escape(h)}</th>" for h in head) + "</tr>"
            + "".join(rows) + "</table></div>")


def render(rep):
    a = rep["algemeen"]
    proef = "proef" in rep["label"].lower()
    start = rep["start"]; end = str(rep["einde"])[:16].replace("T", " ")
    kpi = lambda v, k, c="": f'<div class="kpi"><span class="v {c}">{html.escape(str(v))}</span><span class="k">{k}</span></div>'
    kpis = "".join([kpi(a["trades"], "trades (gesloten)"), kpi(fPct(a["winrate"]), "winrate"),
                    kpi(fR(a["gem_R"]), "gem. per trade", cls(a["gem_R"])), kpi(fR(a["totaal_R"], 1), "totaal", cls(a["totaal_R"])),
                    kpi(fUSD(a.get("winst_usd")), f'totale winst ({a["winst"]} trades)', "pos"),
                    kpi(fUSD(a.get("verlies_usd")), f'totaal verlies ({a["verlies"]} trades)', "neg"),
                    kpi(fUSD(a["usd"]), "netto $ bij jouw lots", cls(a["usd"])), kpi(a["lopend"], "lopen nog")])
    setups = [row(summary_cells(n, s, s["stopregel"])) for n, s in rep["setups"].items()]
    pairs = []
    for n, s in rep["setups"].items():
        for m, ps in s["per_pair"].items():
            pairs.append(row(summary_cells(f"{n} · {m}", ps)))
    info = [row(summary_cells(f"Test #1 · {m} (info)", s)) for m, s in rep["info_test1_extra_markten"].items()]
    tr = []
    for t in rep["trades"]:
        ft = pd.Timestamp(t["fill_time"]) - BE
        et = (pd.Timestamp(t["exit_time"]) - BE) if t["exit_time"] else None
        dg = 5 if t["markt"] in ("EURUSD", "GBPUSD") else (3 if t["markt"] == "XAGUSD" else 2)
        px = lambda v: "—" if v is None else f"{v:.{dg}f}"
        uit = "loopt nog" if t["loopt"] else t["uitkomst"]
        tr.append(row([(ft.strftime("%d-%m %H:%M"), ""), (t["setup"], ""), (t["markt"], ""), (t["richting"], ""),
                       (px(t["fill_px"]), "num"), (px(t["sl_px"]), "num"), (px(t["tp_px"]), "num"),
                       (et.strftime("%d-%m %H:%M") if et is not None else "—", ""), (px(t["exit_px"]), "num"),
                       (uit, ""), (fR(t["r_net"]), cls(t["r_net"])), (f'{t["pips"]:+.1f}' if t["pips"] is not None else "—", "num"),
                       (fUSD(t["usd"]) if t["usd"] is not None else "—", cls(t["usd"]))]))
    lots = " · ".join(f"{m} {v:.2f}" for m, v in rep["lots"].items())
    banner = ('<div class="banner">PROEFRUN — dit is oude data, alleen om te tonen hoe het rapport eruitziet. '
              'Dit telt niet als vooruit-test.</div>' if proef else "")
    return f"""<title>KATSU Vooruittest</title>
<style>
:root {{ color-scheme: dark; --bg:#0f141b; --panel:#151c25; --line:#263243; --fg:#d5dce5; --muted:#8392a5; --accent:#e3a33b; --up:#2bb39a; --down:#e0565b;
  --ui:"IBM Plex Sans Condensed","Arial Narrow",system-ui,sans-serif; --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace; }}
body {{ background:var(--bg); color:var(--fg); font:14px/1.45 var(--ui); margin:0; }}
main {{ max-width:1100px; margin:0 auto; padding:16px; display:grid; gap:16px; }}
h1 {{ font-size:13px; letter-spacing:.14em; color:var(--accent); margin:0; }}
h2 {{ font-size:12px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); margin:0 0 6px; }}
.note {{ color:var(--muted); font-size:12px; }}
.banner {{ border:1px solid var(--accent); background:color-mix(in srgb, var(--accent) 15%, transparent); border-radius:6px; padding:10px 12px; font-weight:600; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(140px,1fr)); gap:8px; }}
.kpi {{ background:var(--panel); border:1px solid var(--line); border-radius:6px; padding:10px 12px; display:grid; }}
.kpi .v {{ font-family:var(--mono); font-size:20px; }} .kpi .k {{ font-size:12px; color:var(--muted); }}
section {{ background:var(--panel); border:1px solid var(--line); border-radius:6px; padding:12px; min-width:0; }}
.tw {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-size:13px; }}
th {{ color:var(--muted); font-weight:500; font-size:12px; text-align:right; padding:4px 6px; border-bottom:1px solid var(--line); white-space:nowrap; }}
td {{ text-align:right; padding:5px 6px; font-family:var(--mono); border-bottom:1px solid color-mix(in srgb, var(--line) 55%, transparent); white-space:nowrap; }}
th:first-child, td:first-child {{ text-align:left; font-family:var(--ui); }}
td.note {{ font-family:var(--ui); text-align:left; white-space:normal; min-width:160px; }}
.pos {{ color:var(--up); }} .neg {{ color:var(--down); }}
@media (max-width:600px) {{ main {{ padding:12px; gap:12px; }} .kpis {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .kpi .v {{ font-size:18px; }} }}
</style>
<main>
  <h1>KATSU VOORUITTEST</h1>
  {banner}
  <div class="note">{html.escape(rep["label"])} · van {html.escape(start)} t/m {html.escape(end)} (servertijd) · tijden in de lijst: Belgische tijd · één trade tegelijk per setup per markt · lots: {html.escape(lots)}</div>
  <div class="kpis">{kpis}</div>
  <section><h2>Per setup</h2>{table(HEAD + ["stopregel"], setups)}</section>
  <section><h2>Per setup en pair</h2>{table(HEAD, pairs)}</section>
  {f'<section><h2>Ter info: test #1 op andere markten</h2><p class="note">Telt niet mee in het totaal.</p>{table(HEAD, info)}</section>' if info else ''}
  <section><h2>Alle trades</h2><p class="note">Vergelijk lijn per lijn met je demo-trades (werkregel 5). "loopt nog" = nog niet gesloten op het einde van de data; telt nog niet mee.</p>
  {table(["vulling", "setup", "pair", "richting", "entry", "SL", "TP", "uit", "uitprijs", "uitkomst", "R", "pips", "$"], tr)}</section>
  <p class="note">Stopregels per setup: na 20 trades gemiddeld onder −0,3R → stoppen · na 40 trades onder 0 → stoppen · pas na ±150 trades boven +0,10R echt geld overwegen. Eén maand zegt weinig: kijk vooral naar grote afwijkingen.</p>
</main>
"""


if __name__ == "__main__":
    rep = json.load(open(sys.argv[1]))
    open(sys.argv[2], "w").write(render(rep))
    print("geschreven:", sys.argv[2])
