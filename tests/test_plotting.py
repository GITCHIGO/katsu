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
