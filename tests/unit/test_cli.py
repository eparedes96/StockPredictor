import pytest

from stockpredictor import __version__
from stockpredictor.cli import main


def test_main_sin_argumentos_devuelve_cero():
    assert main([]) == 0


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_session_may_be_open():
    import datetime as dt

    from stockpredictor.cli import session_may_be_open

    utc = dt.UTC
    assert session_may_be_open(dt.datetime(2026, 11, 26, 10, 0, tzinfo=utc))  # jueves 11:00 CET
    assert not session_may_be_open(dt.datetime(2026, 11, 26, 17, 30, tzinfo=utc))  # 18:30 CET
    assert not session_may_be_open(dt.datetime(2026, 11, 28, 10, 0, tzinfo=utc))  # sábado
