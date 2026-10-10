"""Catálogo incremental de rutas conocidas de WoW 3.3.5a.

MPQ almacena hashes de los nombres. Cuando un archivo no incluye ``(listfile)``,
un lector sólo puede identificar una entrada probando rutas conocidas.
"""

from __future__ import annotations


def known_paths() -> tuple[str, ...]:
    paths = {
        "Interface\\WorldMap\\Azeroth\\AzerothHighlight.blp",
        "DBFilesClient\\AreaTable.dbc",
        "DBFilesClient\\WorldMapArea.dbc",
        "DBFilesClient\\WorldMapContinent.dbc",
        "DBFilesClient\\WorldMapOverlay.dbc",
    }
    for index in range(1, 13):
        paths.add(f"Interface\\WorldMap\\World\\World{index}.blp")
        paths.add(f"Interface\\WorldMap\\Azeroth\\Azeroth{index}.blp")
        paths.add(f"Interface\\WorldMap\\Tirisfal\\Tirisfal{index}.blp")
        paths.add(
            f"Interface\\WorldMap\\MidnightCrucible\\MidnightCrucible{index}.blp"
        )
    return tuple(sorted(paths, key=str.casefold))
