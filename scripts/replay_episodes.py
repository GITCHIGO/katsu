"""
Bouwt de episodes voor de KATSU Replay (docs/replay_spec.md).
Gebruik: python -m scripts.replay_episodes <uitmap-episodes> <sleutelbestand.csv>
De sleutel (episode -> echte datum) blijft buiten de repo, zodat de replay blind blijft.
"""
import os
import sys

import numpy as np
import pandas as pd

from katsu.replay import encode, episode_frame, pick_mondays

SRC = {"EURUSD": "/home/claude/katsu_research/eur_m1_full.pkl", "XAUUSD": "/home/claude/katsu_research/xau_m1_full.pkl"}
N = 20


def main(outdir, keyfile):
    os.makedirs(outdir, exist_ok=True)
    rng = np.random.default_rng(20261012)
    rows = []
    for sym, f in SRC.items():
        m1 = pd.read_pickle(f)
        m1 = m1[m1.index < "2025-01-01"]
        mondays = pick_mondays(m1.index, N, rng)
        order = rng.permutation(len(mondays))           # nummering niet chronologisch
        for nr, j in enumerate(order, 1):
            mon = mondays[j]
            eid = f"{'eur' if sym == 'EURUSD' else 'xau'}{nr:02d}"
            blob = encode(episode_frame(m1, mon), sym, eid, mon)
            with open(os.path.join(outdir, eid + ".bin"), "wb") as fh:
                fh.write(blob)
            rows.append({"episode": eid, "markt": sym, "start_server": mon, "kb": round(len(blob) / 1024)})
    key = pd.DataFrame(rows).sort_values("episode")
    key.to_csv(keyfile, index=False)
    print(key.to_string(index=False)); print("totaal MB:", round(key.kb.sum() / 1024, 1))


if __name__ == "__main__":
    main(*sys.argv[1:3])
