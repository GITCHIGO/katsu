"""Vervangen van een bestand dat even door een ander programma open is (Windows 'Access is denied')."""
import pytest

from katsu.live.fsutil import replace_retry


def flaky(fail_times):
    calls = {"n": 0}

    def _replace(tmp, path):
        calls["n"] += 1
        if calls["n"] <= fail_times:
            raise PermissionError(13, "Access is denied")
    return _replace, calls


def test_lukt_na_een_paar_keer_access_denied():
    rep, calls = flaky(3)
    slept = []
    assert replace_retry("a.tmp", "a", _replace=rep, _sleep=slept.append) == 4
    assert calls["n"] == 4 and slept == [0.1, 0.1, 0.1]


def test_geeft_op_na_alle_pogingen():
    rep, calls = flaky(99)
    with pytest.raises(PermissionError):
        replace_retry("a.tmp", "a", tries=5, _replace=rep, _sleep=lambda s: None)
    assert calls["n"] == 5


def test_andere_fouten_niet_opnieuw():
    def rep(tmp, path):
        raise FileNotFoundError("weg")
    with pytest.raises(FileNotFoundError):
        replace_retry("a.tmp", "a", _replace=rep, _sleep=lambda s: None)


def test_echt_bestand(tmp_path):
    tmp, path = tmp_path / "s.json.tmp", tmp_path / "s.json"
    tmp.write_text("nieuw"); path.write_text("oud")
    assert replace_retry(str(tmp), str(path)) == 1
    assert path.read_text() == "nieuw" and not tmp.exists()
