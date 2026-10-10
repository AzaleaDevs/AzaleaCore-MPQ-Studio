"""Pruebas del flujo seguro de exportación y empaquetado."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from azaleacore_mpq_studio.mpq import MPQArchive
from azaleacore_mpq_studio.packer import (
    PackagingError,
    create_and_install_patch,
    plan_patch,
)
from azaleacore_mpq_studio.workspace import (
    ExportRequest,
    export_files,
    prepare_workspace,
)


PATCH9 = Path(r"D:\World of Warcraft 3.3.5a\Data\patch-9.MPQ")
HIGHLIGHT = "Interface\\WorldMap\\Azeroth\\AzerothHighlight.blp"


class PatchPlanningTest(unittest.TestCase):
    def test_empty_directory_starts_at_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            plan = plan_patch(temporary)
            self.assertEqual(plan.patch_name, "patch-1.MPQ")

    def test_next_number_uses_highest_existing_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "patch-6.MPQ").touch()
            (root / "patch-8.MPQ").touch()
            plan = plan_patch(root)
            self.assertEqual(plan.patch_name, "patch-9.MPQ")
            self.assertEqual(plan.previous_patch, "patch-8.MPQ")

    def test_patch_ten_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "patch-9.MPQ").touch()
            with self.assertRaises(PackagingError):
                plan_patch(root)

    def test_locale_directory_uses_localized_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            locale = Path(temporary) / "esES"
            locale.mkdir()
            self.assertEqual(plan_patch(locale).patch_name, "patch-esES-1.MPQ")


class PackagingRoundTripTest(unittest.TestCase):
    def test_new_mpq_reopens_and_preserves_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = prepare_workspace(root / "workspace")
            source = workspace.package_dir / "Interface" / "Demo" / "sample.txt"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"AzaleaCore MPQ Studio\n")
            destination = root / "destination"
            destination.mkdir()
            plan = plan_patch(destination)

            digest, size = create_and_install_patch(
                [("Interface\\Demo\\sample.txt", source)], plan
            )

            self.assertTrue(digest)
            self.assertEqual(size, plan.target.stat().st_size)
            with MPQArchive(plan.target) as archive:
                self.assertEqual(
                    archive.read_file("Interface\\Demo\\sample.txt"),
                    b"AzaleaCore MPQ Studio\n",
                )


@unittest.skipUnless(PATCH9.is_file(), "patch-9.MPQ no está instalado")
class ExportIntegrationTest(unittest.TestCase):
    def test_patch9_exports_with_original_internal_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = prepare_workspace(temporary)
            results = export_files(
                [ExportRequest(PATCH9, HIGHLIGHT)], workspace
            )
            output = workspace.export_dir.joinpath(*HIGHLIGHT.split("\\"))
            self.assertTrue(output.is_file())
            self.assertEqual(results[0].size, output.stat().st_size)
            self.assertTrue((workspace.root / "azaleacore-export-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
