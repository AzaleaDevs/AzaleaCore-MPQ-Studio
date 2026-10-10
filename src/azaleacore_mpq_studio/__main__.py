"""Punto de entrada de AzaleaCore MPQ Studio."""

from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import known_paths
from .mpq import MPQArchive


def inspect_archive(path: Path) -> int:
    """Lista las rutas identificables de un MPQ sin abrir la interfaz."""
    with MPQArchive(path) as archive:
        inventory = archive.inventory(known_paths())
    for item in inventory.files:
        print(item.path)
    if inventory.unknown_entries:
        print(
            f"Aviso: {inventory.unknown_entries} entrada(s) no tienen un nombre "
            "recuperable sin un (listfile) o catálogo adicional."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AzaleaCore MPQ Studio")
    parser.add_argument(
        "--inspect",
        metavar="MPQ",
        type=Path,
        help="lista las rutas identificables del MPQ en modo de solo lectura",
    )
    args = parser.parse_args()
    if args.inspect:
        return inspect_archive(args.inspect)

    from .app import run

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

