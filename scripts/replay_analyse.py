"""
Analyse van de replay-trades. Leest een dump van de opslag (ArtifactData list met out_dir: <map>/trades/*.json en
<map>/beslissingen/*.json) en de episodes, en drukt per trade het resultaat en de MFE/MAE af.
Gebruik: python -m scripts.replay_analyse <dump-map> <episodes-map> [uit.csv]
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

from katsu.replay import decode
from katsu.replay_analyse import excursion, net_pips, sl_check


def load_docs(dump):
    rows = []
    for kind in ("trades", "beslissingen"):
        for f in glob.glob(os.path.join(dump, kind, "*.json")):
            d = json.load(open(f)); d = d.get("data", d)
            d["_bron"] = kind; rows.append(d)
    return rows


def main(dump, epdir, out=None):
    cache, rows = {}, []
    for d in load_docs(dump):
        if d.get("status") != "closed" or d.get("fill") is None:
            continue
        ep = d["ep"]
        if ep not in cache:
            cache[ep] = decode(open(os.path.join(epdir, ep + ".bin"), "rb").read())[1]
        m1 = cache[ep]
        mins = m1.index.values.astype("datetime64[m]").astype(np.int64)
        exit_idx = int(np.searchsorted(mins, d["exitT"]))
        x = excursion(m1, d["sym"], d["dir"], d["fill"], d["tp"], int(d["fillIdx"]), exit_idx)
        x.update(sl_check(m1, d["sym"], d["dir"], d["fill"], d.get("slAtFill", d["sl"]), d["tp"], int(d["fillIdx"])))
        soort = ("niet genomen" if d.get("kind") == "overgeslagen" else "twijfel, niet genomen") if d["_bron"] == "beslissingen" \
            else ("genomen, twijfel" if d.get("doubt") else "genomen, zeker")
        rows.append({"episode": ep, "soort": soort, "richting": "L" if d["dir"] > 0 else "S", "uitkomst": d["reason"],
                     "netto_pips": net_pips(d["sym"], d["dir"], d["fill"], d["exitPx"]), **x, "reden": d.get("why", "")})
    df = pd.DataFrame(rows).sort_values(["episode", "soort"])
    with pd.option_context("display.width", 200, "display.max_colwidth", 40):
        print(df.drop(columns=["reden"]).round(1).to_string(index=False))
        sl = df[df.uitkomst == "SL"]
        print("\nVerliezers die ≥ 80% van de TP-afstand haalden:", int((sl.tp_bereikt >= 0.8).sum()), "van", len(sl))
        red = sl[sl.extra_sl_pips.notna()]
        print("Verliezers waarbij de TP later tóch kwam:", len(red), "van", len(sl), "; nodige extra SL (pips):",
              red.extra_sl_pips.round(1).tolist())
        win = df[df.uitkomst == "TP"]
        print("Winnaars: kleinste marge tot de SL (pips):", win.sl_marge_pips.round(1).tolist())
        print(df.groupby("soort").agg(n=("netto_pips", "size"), win=("uitkomst", lambda u: (u == "TP").mean()),
                                      pips=("netto_pips", "sum"), gem_tp_bereikt=("tp_bereikt", "mean")).round(2))
    if out:
        df.to_csv(out, index=False, float_format="%.2f")


if __name__ == "__main__":
    main(*sys.argv[1:4])
