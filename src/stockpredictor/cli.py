"""Punto de entrada de terminal. Cada etapa del pipeline se añadirá como subcomando."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from stockpredictor import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stockpredictor",
        description="Predicción de retorno absoluto a N días (investigación cuantitativa).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
