"""Pruebas del flujo seguro de exportación y empaquetado."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from azaleacore_mpq_studio.app import (
    calculate_mpq_sha256,
    describe_mpq_flags,
    filter_mpq_files,
)
from azaleacore_mpq_studio.mpq import (
    MPQ_FILE_COMPRESS,
    MPQ_FILE_EXISTS,
    MPQArchive,
    MPQFile,
    load_listfile_paths,
)
from azaleacore_mpq_studio.packer import (
    PackagingError,
    build_mpq,
    create_and_install_patch,
    is_protected_gluexml,
    plan_patch,
)
from azaleacore_mpq_studio.settings import load_workspace_settings, save_workspace_settings
from azaleacore_mpq_studio.workspace import (
    ExportRequest,
    export_files,
    prepare_workspace,
)


PATCH9 = Path(r"D:\World of Warcraft 3.3.5a\Data\patch-9.MPQ")
HIGHLIGHT = "Interface\\WorldMap\\Azeroth\\AzerothHighlight.blp"


class PatchPlanningTest(unittest.TestCase):
    def test_external_listfile_paths_are_normalized_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            listfile = Path(temporary) / "listfile.txt"
            listfile.write_bytes(
                b"Interface/Demo/Hidden.bin\r\ninterface\\demo\\hidden.bin\n\n"
            )
            self.assertEqual(
                load_listfile_paths(listfile), ("Interface\\Demo\\Hidden.bin",)
            )

    def test_workspace_preference_can_be_saved_and_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "settings.json"
            workspace = root / "workspace"
            workspace.mkdir()

            save_workspace_settings(settings, remember=True, workspace=workspace)
            self.assertEqual(load_workspace_settings(settings), (True, workspace))

            save_workspace_settings(settings, remember=False, workspace=workspace)
            self.assertEqual(load_workspace_settings(settings), (False, None))

    def test_mpq_flags_are_shown_in_hex_and_plain_language(self) -> None:
        description = describe_mpq_flags(MPQ_FILE_EXISTS | MPQ_FILE_COMPRESS)
        self.assertEqual(description, "0x80000200 · EXISTE | COMPRIMIDO")

    def test_gluexml_paths_are_detected_case_insensitively(self) -> None:
        self.assertTrue(
            is_protected_gluexml("Interface\\GlueXML\\GlueStrings.lua")
        )
        self.assertTrue(is_protected_gluexml("interface/gluexml/Test.xml"))
        self.assertFalse(
            is_protected_gluexml("Interface\\WorldMap\\Azeroth\\Map.blp")
        )

    def test_path_filter_is_instant_style_and_case_insensitive(self) -> None:
        files = (
            MPQFile("Interface\\GlueXML\\GlueStrings.lua", 10, 10, 0),
            MPQFile("Interface\\WorldMap\\Azeroth\\Map.blp", 20, 20, 0),
        )
        self.assertEqual(filter_mpq_files(files, "gluestrings"), files[:1])
        self.assertEqual(filter_mpq_files(files, "WORLDMAP"), files[1:])
        self.assertEqual(filter_mpq_files(files, "   "), files)
        self.assertEqual(filter_mpq_files(files, "missing"), ())

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
    def test_external_listfile_discovers_unlisted_mpq_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "unlisted.MPQ"
            internal_path = "Interface\\Demo\\Hidden.bin"
            build_mpq([(internal_path, b"hidden resource")], archive_path)
            listfile = root / "listfile.txt"
            listfile.write_text(internal_path + "\n", encoding="utf-8")

            with MPQArchive(archive_path) as archive:
                inventory = archive.inventory(load_listfile_paths(listfile))

            self.assertEqual([item.path for item in inventory.files], [internal_path])
            self.assertEqual(inventory.unknown_entries, 0)

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
            self.assertEqual(
                calculate_mpq_sha256(plan.target, "Interface\\Demo\\sample.txt"),
                "e2ceabaa40908dc9ccddc62e734ef3c524c1466d8575afed7643ddb235e4e2a1",
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
