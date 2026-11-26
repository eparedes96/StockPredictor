"""StockPredictor: predicción del retorno absoluto de acciones a N días."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("stockpredictor")
except PackageNotFoundError:  # ejecutado desde el código fuente sin instalar
    __version__ = "0.0.0+unknown"
