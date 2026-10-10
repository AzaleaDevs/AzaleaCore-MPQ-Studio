"""Prueba opcional contra el parche de laboratorio instalado."""

from __future__ import annotations

import unittest
from pathlib import Path

from azaleacore_mpq_studio.catalog import known_paths
from azaleacore_mpq_studio.mpq import MPQArchive


PATCH9 = Path(r"D:\World of Warcraft 3.3.5a\Data\patch-9.MPQ")
EXPECTED = "Interface\\WorldMap\\Azeroth\\AzerothHighlight.blp"


@unittest.skipUnless(PATCH9.is_file(), "patch-9.MPQ no está instalado")
class Patch9IntegrationTest(unittest.TestCase):
    def test_inventory_identifies_its_only_file(self) -> None:
        with MPQArchive(PATCH9) as archive:
            inventory = archive.inventory(known_paths())

        self.assertEqual(inventory.active_entries, 1)
        self.assertEqual(inventory.unknown_entries, 0)
        self.assertEqual([item.path for item in inventory.files], [EXPECTED])


if __name__ == "__main__":
    unittest.main()
