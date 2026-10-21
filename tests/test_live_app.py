"""KATSU Live: instellingen, resultaten, controle backtest ↔ broker, dashboard (login/noodknop), runner-ronde."""
import os

import numpy as np
import pandas as pd
import pytest

from katsu.live.config import check, load_config, Config
from katsu.live.fake import FakeBroker
from katsu.live.notify import Discord, Logbook
from katsu.live.report import control, results, summarize
from katsu.live.web import Snapshot, make_app

GOOD = """
[mt5]
login = 123
server = "ICMarketsSC-Demo"
[katsu]
mode = "loggen"
data_dir = '{d}'
lots = {{ EURUSD = 0.10, GBPUSD = 0.10, XAUUSD = 0.02 }}
[discord]
webhook = ""
[dashboard]
password = "een-lang-wachtwoord"
secret = "{s}"
port = 8080
"""


def write_cfg(tmp_path, **kw):
    text = GOOD.format(d=str(tmp_path / "data"), s="x" * 40)
    for k, v in kw.items():
        text = text.replace(k, v)
    f = tmp_path / "config.toml"
    f.write_text(text)
    return str(f)


def test_config_loads_and_validates(tmp_path):
    c = load_config(write_cfg(tmp_path))
    assert c.mode == "loggen" and c.lots["XAUUSD"] == 0.02 and c.login == 123 and not c.allow_live
    with pytest.raises(ValueError, match="4 tekens"):
        load_config(write_cfg(tmp_path, **{"een-lang-wachtwoord": "abc"}))
    with pytest.raises(ValueError, match="groter dan 1,0"):
        load_config(write_cfg(tmp_path, **{"XAUUSD = 0.02": "XAUUSD = 5.0"}))
    with pytest.raises(ValueError, match="loggen"):
        load_config(write_cfg(tmp_path, **{'mode = "loggen"': 'mode = "alles"'}))


def test_discord_without_webhook_does_nothing():
    assert Discord("").send("test") is False


def test_logbook_newest_first(tmp_path):
    lb = Logbook(str(tmp_path))
    lb.write({"time": "2026-10-20 10:00:00", "kind": "scan", "text": "a"})
    lb.write({"time": "2026-10-21 10:00:00", "kind": "scan", "text": "b"})
    lb.write({"time": "2026-10-21 10:15:00", "kind": "fout", "text": "c"})
    assert [x["text"] for x in lb.tail(10)] == ["c", "b", "a"]


# ------------------------------------------------------------------ resultaten

def closed(setup, market, net, r, pips, t):
    return {"setup": setup, "market": market, "state": "gesloten", "net": net, "r_net": r, "pips": pips,
            "exit_time": t, "key": f"{setup}|{market}|{t}|LONG|1", "t_sig": t}


def test_results_hand():
    o = [closed("Test #1 (FVG)", "EURUSD", 21.5, 1.94, 22.2, "2026-10-21 12:00"),
         closed("Test #1 (FVG)", "GBPUSD", -11.8, -1.06, -11.1, "2026-10-22 12:00"),
         closed("Zone GBPUSD", "GBPUSD", 10.0, 0.9, 9.0, "2026-10-23 12:00"),
         {"setup": "AMD-extra (#386)", "market": "EURUSD", "state": "gevuld"}]
    r = results(o)
    a = r["algemeen"]
    # 3 gesloten: 2 winst, 1 verlies; netto 21,5 − 11,8 + 10 = 19,7; winst 31,5; verlies −11,8; R 1,94−1,06+0,9 = 1,78
    assert (a["trades"], a["winst"], a["verlies"]) == (3, 2, 1)
    assert a["netto"] == pytest.approx(19.7) and a["winst_geld"] == pytest.approx(31.5)
    assert a["verlies_geld"] == pytest.approx(-11.8) and a["totaal_R"] == pytest.approx(1.78)
    assert r["lopend"] == 1
    t1 = r["setups"]["Test #1 (FVG)"]
    assert t1["per_pair"]["EURUSD"]["trades"] == 1 and t1["per_pair"]["XAUUSD"]["trades"] == 0
    assert [round(x[1], 2) for x in t1["curve"]] == [1.94, 0.88]
    assert results(o, since=pd.Timestamp("2026-10-22"))["algemeen"]["trades"] == 2
    assert summarize([])["winrate"] is None


# ------------------------------------------------------------------ controle

def bt_row(setup_kind, t, fill, uit, r, limit=1.101):
    return {"markt": "EURUSD", "soort": setup_kind, "t_sig": pd.Timestamp(t), "plan_kind": "limit",
            "plan_richting": "LONG", "plan_anchor": 1.1, "plan_atr": 0.001, "plan_limit": limit,
            "plan_valid_until": pd.Timestamp(t), "plan_valid_bars": 480, "plan_tp": 1.105, "plan_cancel": 1.103,
            "plan_max_rr": 2.0, "plan_close_eod": np.nan, "fill_px": fill, "uitkomst": uit, "r_net": r,
            "status": "gesloten", "vulling": "gevuld"}


def test_control_compares_line_by_line():
    rows = pd.DataFrame([bt_row("FVG", "2026-10-21 10:15", 1.101, "TP", 1.9),
                         bt_row("FVG", "2026-10-21 14:15", 1.1012, "SL", -1.05, limit=1.1012),
                         bt_row("FVG", "2026-10-22 09:00", 1.1015, "SL", -1.05, limit=1.1015)])
    fake_rows_for = lambda bars, mask, rng: rows
    fake_trades = lambda df, name: df if name == "Test #1 (FVG)" else df.iloc[0:0]
    import katsu.live.report as R
    old = R.preset_mask
    R.preset_mask = lambda df, name: np.full(len(df), name == "Test #1 (FVG)")
    try:
        from katsu.live.scan import signal_from_row
        k = [signal_from_row(r, "Test #1 (FVG)").key for _, r in rows.iterrows()]
        live = [  # trade 1 gelijk; trade 2: live TP i.p.v. SL; trade 3 ontbreekt live
            {"key": k[0], "t_sig": "2026-10-21 10:15", "state": "gesloten", "fill_px": 1.10102, "exit_reason": "TP",
             "r_net": 1.80, "commission": -0.7, "swap": 0.0},
            {"key": k[1], "t_sig": "2026-10-21 14:15", "state": "gesloten", "fill_px": 1.1012, "exit_reason": "TP",
             "r_net": 1.9, "commission": -0.7, "swap": 0.0}]
        c = control(live, {}, pd.Timestamp("2026-10-21"), fake_rows_for, fake_trades)
    finally:
        R.preset_mask = old
    st = [t["status"] for t in c["trades"]]
    assert st == ["gelijk", "verschil: uitkomst SL vs TP", "alleen backtest"]
    assert c["trades"][0]["slippage_pips"] == pytest.approx(0.2)         # 1.10102 − 1.10100 = 0,2 pip slechter
    assert c["overeenkomst"] == pytest.approx(1 / 3)
    assert c["signalen"]["gelijk"] == 2 and c["signalen"]["backtest"] == 3


# ------------------------------------------------------------------ dashboard

@pytest.fixture
def client(tmp_path):
    snap = Snapshot()
    snap.set({"now": "2026-10-21 10:00:00", "connected": True, "mode": "orders", "paused": False,
              "account": {"login": 123, "demo": True}, "orders": [], "results_month": results([]),
              "results_all": results([]), "control": {}, "errors": [], "cur": "€"})
    app = make_app(snap, "een-lang-wachtwoord", "x" * 40, Logbook(str(tmp_path)))
    app.config["TESTING"] = True
    return app.test_client(), snap


def test_dashboard_requires_login_and_limits_attempts(client):
    c, _ = client
    assert c.get("/").status_code == 302
    r = c.post("/login", data={"pw": "fout"})
    assert "Fout wachtwoord" in r.get_data(as_text=True)
    for _ in range(4):
        c.post("/login", data={"pw": "fout"})
    assert c.post("/login", data={"pw": "een-lang-wachtwoord"}).status_code == 429     # ook juist wachtwoord: geblokkeerd


def test_dashboard_pages_and_kill_switch_with_csrf(client):
    c, snap = client
    assert c.post("/login", data={"pw": "een-lang-wachtwoord"}).status_code == 302
    for url in ("/", "/resultaten", "/resultaten?p=alles", "/controle", "/log", "/noodknop"):
        r = c.get(url)
        assert r.status_code == 200, url
        assert "katsu live" in r.get_data(as_text=True).lower()
    assert c.post("/noodknop", data={"csrf": "verkeerd"}).status_code == 400
    page = c.get("/noodknop").get_data(as_text=True)
    token = page.split("name='csrf' value='")[1].split("'")[0]
    assert c.post("/noodknop", data={"csrf": token}).status_code == 200
    assert snap.take_requests() == ["kill"]


# ------------------------------------------------------------------ runner

def flat_bars(start, n, px):
    idx = pd.date_range(start, periods=n, freq="15min")
    idx = idx[idx.dayofweek < 5]
    return pd.DataFrame({"open": px, "high": px + 0.0002, "low": px - 0.0002, "close": px, "tickvol": 100,
                         "spread": 2}, index=idx)


def test_runner_refuses_live_account_and_runs_a_round(tmp_path):
    from katsu.live.runner import Runner, next_scan_time
    cfg = load_config(write_cfg(tmp_path))
    with pytest.raises(SystemExit, match="GEEN demo"):
        Runner(cfg, broker=FakeBroker(demo=False), now_fn=lambda: pd.Timestamp("2026-10-21 10:15:10")).start()
    fb = FakeBroker()
    for m, p in (("EURUSD", 1.10), ("GBPUSD", 1.30), ("XAUUSD", 2400.0)):
        fb.bars[m] = flat_bars("2026-10-12", 900, p)
        fb.set_price(m, p, p + 0.00002, "2026-10-21 10:15:05")
    now = pd.Timestamp("2026-10-21 10:15:10")
    r = Runner(cfg, broker=fb, now_fn=lambda: now)
    r.start()
    r.next_scan = now                                      # meteen scannen
    r.once(now)
    assert r.last_scan_done == now and r.mgr.last_scan == "2026-10-21 10:15:00"
    assert os.path.exists(os.path.join(cfg.data_dir, "bars", "EURUSD_M15_live.pkl"))
    assert r.next_scan == pd.Timestamp("2026-10-21 10:30:10")
    assert next_scan_time(pd.Timestamp("2026-10-21 10:30:05")) == pd.Timestamp("2026-10-21 10:30:10")
    snap = r.snap.get()
    assert snap["mode"] == "loggen" and snap["connected"]
    r.snap.request("kill")
    r.once(now + pd.Timedelta(seconds=10))
    assert r.mgr.paused
    kinds = [x["kind"] for x in r.log.tail(50)]
    assert "scan" in kinds and "fout" in kinds                # noodknop wordt als 'fout' (rood) gelogd


def test_dashboard_global_limit_over_many_ips(tmp_path):
    """Kort wachtwoord: ook vanaf veel verschillende IP's samen max. 20 foute pogingen per 24 u."""
    snap = Snapshot()
    snap.set({"orders": [], "results_month": results([]), "results_all": results([])})
    app = make_app(snap, "1234", "x" * 40, Logbook(str(tmp_path)))
    c = app.test_client()
    import katsu.live.web as W
    old = W.time.sleep
    W.time.sleep = lambda s: None
    try:
        for i in range(20):
            c.post("/login", data={"pw": "fout"}, environ_base={"REMOTE_ADDR": f"10.0.0.{i}"})
        r = c.post("/login", data={"pw": "1234"}, environ_base={"REMOTE_ADDR": "10.0.1.1"})
    finally:
        W.time.sleep = old
    assert r.status_code == 429 and "24 uur" in r.get_data(as_text=True)
