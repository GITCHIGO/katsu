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
