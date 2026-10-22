"""KATSU Agent (docs/agent_spec.md): waakhond en verzamelaar, met tijdelijke mappen en een lokale git-'GitHub'."""
import json
import os
import subprocess

import pandas as pd
import pytest

from katsu.agent.collect import collect, diagnose, gather, watchdog
from katsu.live.config import Config, paths


class FakeDiscord:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)
        return True


def cfg_in(tmp_path, repo=None):
    c = Config(data_dir=str(tmp_path / "data"), dash_password="1234", dash_secret="x" * 40,
               agent_repo=str(repo or tmp_path / "katsu-data"))
    return c, paths(c)


def status(p, mtime, **kw):
    st = {"tijd_server": "2026-10-22 10:00:00", "verbonden": True, "niet_verbonden_sinds": None,
          "open_trades": ["T1-EUR-1"]}
    st.update(kw)
    with open(p["status"], "w") as fh:
        json.dump(st, fh)
    os.utime(p["status"], (mtime, mtime))


NOW = 1_800_000_000.0


def test_watchdog_alerts_once_and_on_recovery(tmp_path):
    c, p = cfg_in(tmp_path)
    d = FakeDiscord()
    status(p, NOW - 60)                                           # hartslag 1 min oud: in orde
    assert watchdog(c, NOW, d) is None and d.sent == []
    status(p, NOW - 11 * 60)                                      # 11 min oud: stil
    assert watchdog(c, NOW, d) == "stil"
    assert watchdog(c, NOW + 900, d) == "stil"                    # tweede controle: geen tweede melding
    assert len(d.sent) == 1 and "staat stil" in d.sent[0]
    status(p, NOW + 1800 - 30)
    assert watchdog(c, NOW + 1800, d) is None
    assert len(d.sent) == 2 and "terug in orde" in d.sent[1]


def test_watchdog_missing_status_and_mt5_disconnected(tmp_path):
    c, p = cfg_in(tmp_path)
    assert diagnose(p, NOW)[0] == "stil"                          # status.json ontbreekt
    # vers, maar al 12 min niet verbonden (servertijd 10:00 vs sinds 09:48)
    status(p, NOW - 20, verbonden=False, niet_verbonden_sinds="2026-10-22 09:48:00")
    prob, text = diagnose(p, NOW)
    assert prob == "mt5" and "12 min" in text
    status(p, NOW - 20, verbonden=False, niet_verbonden_sinds="2026-10-22 09:55:00")   # pas 5 min
    assert diagnose(p, NOW)[0] is None


def git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def remote_and_clone(tmp_path):
    remote = tmp_path / "remote.git"
    git("init", "--bare", "-q", "-b", "main", str(remote))
    clone = tmp_path / "katsu-data"
    git("clone", "-q", str(remote), str(clone))
    git("-C", str(clone), "config", "user.name", "test")
    git("-C", str(clone), "config", "user.email", "t@t")
    return remote, clone


def test_collect_pushes_files_without_secrets(tmp_path, remote_and_clone):
    remote, clone = remote_and_clone
    c, p = cfg_in(tmp_path, clone)
    status(p, NOW)
    for k in ("state", "control", "deals"):
        with open(p[k], "w") as fh:
            json.dump({"k": k}, fh)
    with open(os.path.join(p["data"], "config.toml"), "w") as fh:      # mag NOOIT mee
        fh.write('password = "geheim"')
    today = pd.Timestamp.fromtimestamp(NOW, tz="UTC").strftime("%Y-%m-%d")
    for day in (today, "2020-01-01"):                                 # oude log blijft weg
        with open(os.path.join(p["log"], f"{day}.jsonl"), "w") as fh:
            fh.write('{"kind":"scan"}\n')
    assert collect(c, NOW) == "doorgestuurd"
    files = git("--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main").split()
    assert {"status.json", "orders.json", "controle.json", "deals.json", "vps.json", "README.md",
            f"log/{today}.jsonl"} <= set(files)
    assert "config.toml" not in files and "log/2020-01-01.jsonl" not in files
    assert not any("geheim" in open(os.path.join(clone, f)).read() for f in files if os.path.isfile(os.path.join(clone, f)))
    n = len(git("--git-dir", str(remote), "log", "--oneline", "main").splitlines())
    os.utime(p["status"], (NOW, NOW))
    # vps.json verandert wel (tijdstip), dus een nieuwe commit; zonder enige wijziging: geen commit
    collect(c, NOW)
    m = len(git("--git-dir", str(remote), "log", "--oneline", "main").splitlines())
    assert collect(c, NOW) == "niets nieuws"
    assert len(git("--git-dir", str(remote), "log", "--oneline", "main").splitlines()) == m >= n


def test_collect_keeps_agent_logbook_from_remote(tmp_path, remote_and_clone):
    """De agent schrijft logboek/… in de repo; de verzamelaar haalt dat op en overschrijft het niet."""
    remote, clone = remote_and_clone
    c, p = cfg_in(tmp_path, clone)
    status(p, NOW)
    collect(c, NOW)
    other = tmp_path / "agent"
    git("clone", "-q", str(remote), str(other))
    os.makedirs(other / "logboek")
    (other / "logboek" / "2026-10-22-dag.md").write_text("# dag\n")
    git("-C", str(other), "add", "-A")
    git("-C", str(other), "-c", "user.name=a", "-c", "user.email=a@a", "commit", "-qm", "logboek")
    git("-C", str(other), "push", "-q")
    status(p, NOW + 3600)
    assert collect(c, NOW + 3600) == "doorgestuurd"
    files = git("--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main").split()
    assert "logboek/2026-10-22-dag.md" in files


def test_collect_reports_error_and_watchdog_flags_after_3h(tmp_path):
    c, p = cfg_in(tmp_path, tmp_path / "bestaat-niet")
    status(p, NOW)
    assert collect(c, NOW).startswith("FOUT")
    assert diagnose(p, NOW + 60)[0] is None                       # nog geen 3 u
    status(p, NOW + 4 * 3600)
    assert collect(c, NOW + 4 * 3600).startswith("FOUT")
    prob, text = diagnose(p, NOW + 4 * 3600)
    assert prob == "verzamelaar" and "geen git-kloon" in text


def test_runner_writes_status_deals_and_forward(tmp_path):
    from katsu.live.fake import FakeBroker
    from katsu.live.runner import Runner
    from tests.test_live_app import flat_bars
    c, p = cfg_in(tmp_path)
    fb = FakeBroker()
    for m, px in (("EURUSD", 1.10), ("GBPUSD", 1.30), ("XAUUSD", 2400.0)):
        fb.bars[m] = flat_bars("2026-10-12", 900, px)
        fb.set_price(m, px, px + 0.00002, "2026-10-21 10:15:05")
    now = pd.Timestamp("2026-10-21 10:15:10")
    r = Runner(c, broker=fb, now_fn=lambda: now)
    r.start()
    r.next_scan = now
    r.once(now)
    st = json.load(open(p["status"]))
    assert st["verbonden"] is True and st["stand"] == "loggen" and st["laatste_scan"] == str(now)
    assert os.path.exists(p["deals"]) and os.path.exists(p["forward"])
    assert json.load(open(p["forward"]))["start"] == "2026-10-10"
    fb.is_connected = False
    r.once(now + pd.Timedelta(minutes=1))
    st = json.load(open(p["status"]))
    assert st["verbonden"] is False and st["niet_verbonden_sinds"] == str(now + pd.Timedelta(minutes=1))
