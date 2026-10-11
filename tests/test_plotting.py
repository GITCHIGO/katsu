"""Rooktest: een controlegrafiek moet zonder fout een PDF opleveren."""
from tests.test_sweep_choch import BASE, always, make
from katsu.plotting import save_setups_pdf
from katsu.signals import detect_setups
from katsu.structure import UP


def test_pdf_wordt_gemaakt(tmp_path):
    bars = make(BASE)
    s = detect_setups(bars, "5min", always(UP), L=1)[0]
    trade = {"fill": 108.5, "sl": 96.8, "tp": 131.9, "entry_time": bars.index[-1], "exit_time": None}
    out = tmp_path / "x.pdf"
    save_setups_pdf([(s, bars, trade, "test")], str(out), "intro")
    assert out.stat().st_size > 1000


def test_bos_pdf_wordt_gemaakt(tmp_path):
    from tests.test_bos import BASE as BOS_BASE, make as bos_make
    from katsu.bos import detect_bos
    from katsu.plotting import save_bos_pdf
    bars = bos_make(BOS_BASE)
    s = detect_bos(bars, "5min", lambda t: UP, L=1)[0]
    trade = {"fill": 106, "sl": 99.8, "tp": 118.4, "entry_time": bars.index[-1], "exit_time": None}
    out = tmp_path / "bos.pdf"
    save_bos_pdf([(s, bars, trade, "test")], str(out), "intro")
    assert out.stat().st_size > 1000


def test_fvg_pdf_wordt_gemaakt(tmp_path):
    from tests.test_fvg import ALL_UP, BASE as F_BASE, make as f_make
    from katsu.fvg import detect_fvg
    from katsu.plotting import save_fvg_pdf
    bars = f_make(F_BASE)
    s = detect_fvg(bars, "5min", lambda t: ALL_UP, "T+")[0]
    trade = {"fill": 102, "sl": 98.8, "tp": 108.4, "entry_time": bars.index[3], "exit_time": None}
    out = tmp_path / "fvg.pdf"
    save_fvg_pdf([(s, bars, trade, "test")], str(out), "intro")
    assert out.stat().st_size > 1000


def test_voorbeeldtrade_wordt_getekend(tmp_path):
    import matplotlib.pyplot as plt
    from tests.test_bos import BASE as BB, make as bmake
    from katsu.plotting import plot_example_trade
    bars = bmake(BB)
    trade = {"entry_time": bars.index[10], "exit_time": bars.index[10], "fill": 107, "sl": 99.8, "tp": 117.8}
    fig, ax = plt.subplots()
    plot_example_trade(ax, bars, 10, trade, "test", {"level": (106, 6), "anchor": (100, 8), "gap": (101, 102, 2)})
    fig.savefig(tmp_path / "t.png"); plt.close(fig)
    assert (tmp_path / "t.png").stat().st_size > 1000


def test_positie_wordt_getekend(tmp_path):
    import matplotlib.pyplot as plt
    from tests.test_fvg import BASE as FB, make as fmake
    from katsu.plotting import plot_position
    bars = fmake(FB)
    fig, ax = plt.subplots()
    plot_position(ax, bars, 2, 1, 3, 104.5, 103.5, 106.0, 4, 103.5, "SL", "test", gap=(101, 102))
    fig.savefig(tmp_path / "p.png"); plt.close(fig)
    assert (tmp_path / "p.png").stat().st_size > 1000
