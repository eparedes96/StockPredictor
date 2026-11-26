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
