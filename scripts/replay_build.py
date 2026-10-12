"""
Bouwt de KATSU Replay-pagina: sim.js en de lijst episodes (alleen id + markt, géén datums) worden ingevoegd.
Gebruik: python -m scripts.replay_build <episodes-map> <uitmap>
"""
import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "replay"


def build(epdir, outdir):
    os.makedirs(os.path.join(outdir, "episodes"), exist_ok=True)
    eps = []
    for f in sorted(os.listdir(epdir)):
        if f.endswith(".bin"):
            eid = f[:-4]
            eps.append({"id": eid, "sym": "EURUSD" if eid.startswith("eur") else "XAUUSD"})
            with open(os.path.join(epdir, f), "rb") as fh:          # base64-tekst: artifacts serveren geen binaire bestanden
                txt = base64.b64encode(fh.read()).decode()
            with open(os.path.join(outdir, "episodes", eid + ".txt"), "w") as fh:
                fh.write(txt)
    page = (ROOT / "page.html").read_text()
    page = page.replace("/*SIM_JS*/", (ROOT / "sim.js").read_text())
    page = page.replace("/*EPISODES*/[]", json.dumps(eps))
    (Path(outdir) / "replay.html").write_text(page)
    return eps


if __name__ == "__main__":
    print(len(build(*sys.argv[1:3])), "episodes")
