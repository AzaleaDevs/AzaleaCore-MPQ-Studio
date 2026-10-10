"""Pruebas del flujo seguro de exportación y empaquetado."""

from __future__ import annotations

import tempfile
import struct
import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from azaleacore_mpq_studio.app import (
    calculate_mpq_sha256,
    describe_mpq_flags,
    filter_mpq_files,
    format_error_for_clipboard,
    _set_windows_app_user_model_id,
)
from azaleacore_mpq_studio.i18n import normalize_language, translate_text
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
    plan_patch,
)
from azaleacore_mpq_studio.settings import (
    load_language_setting,
    load_workspace_settings,
    save_language_setting,
    save_workspace_settings,
)
from azaleacore_mpq_studio.workspace import (
    ExportRequest,
    export_files,
    prepare_workspace,
)


PATCH9 = Path(r"D:\World of Warcraft 3.3.5a\Data\patch-9.MPQ")
HIGHLIGHT = "Interface\\WorldMap\\Azeroth\\AzerothHighlight.blp"
APP_ICON = Path(__file__).resolve().parents[1] / "assets" / "azaleacore-mpq-studio.ico"


class PatchPlanningTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "solo Windows tiene barra de tareas")
    def test_windows_app_user_model_id_can_be_set(self) -> None:
        self.assertTrue(_set_windows_app_user_model_id())

    def test_application_icon_contains_expected_windows_sizes(self) -> None:
        icon = APP_ICON.read_bytes()
        reserved, resource_type, count = struct.unpack_from("<HHH", icon)
        self.assertEqual((reserved, resource_type, count), (0, 1, 7))
        dimensions = tuple(icon[6 + index * 16] or 256 for index in range(count))
        self.assertEqual(dimensions, (16, 24, 32, 48, 64, 128, 256))

    def test_error_clipboard_report_includes_version_title_and_detail(self) -> None:
        report = format_error_for_clipboard("MPQ inválido", "Tabla incompleta")
        self.assertIn("AzaleaCore MPQ Studio", report)
        self.assertIn("MPQ inválido", report)
        self.assertIn("Tabla incompleta", report)

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

    def test_language_preference_persists_without_overwriting_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings = root / "settings.json"
            workspace = root / "workspace"
            workspace.mkdir()

            save_workspace_settings(settings, remember=True, workspace=workspace)
            save_language_setting(settings, "en")
            self.assertEqual(load_language_setting(settings), "en")
            self.assertEqual(load_workspace_settings(settings), (True, workspace))

            save_workspace_settings(settings, remember=False, workspace=workspace)
            self.assertEqual(load_language_setting(settings), "en")
            self.assertEqual(load_workspace_settings(settings), (False, None))

    def test_language_translation_switches_both_directions(self) -> None:
        spanish = "Pila de extracción"
        english = "Extraction queue"
        self.assertEqual(normalize_language("fr"), "es")
        self.assertEqual(translate_text(spanish, "en"), english)
        self.assertEqual(translate_text(english, "es"), spanish)
        self.assertEqual(
            translate_text(
                "En este directorio no hay parches prioritarios compatibles. "
                "Se creará patch-1.MPQ como primer parche.",
                "en",
            ),
            "There are no compatible priority patches in this folder. "
            "The new patch will be patch-1.MPQ as the first patch.",
        )
        self.assertEqual(
            translate_text("0x80000200 · EXISTE | COMPRIMIDO", "en"),
            "0x80000200 · EXISTS | COMPRESSED",
        )

    @unittest.skipUnless(sys.platform == "win32", "la prueba gráfica requiere Windows")
    def test_app_language_toggle_updates_widgets_menus_and_persists(self) -> None:
        from azaleacore_mpq_studio import app as app_module

        with tempfile.TemporaryDirectory() as temporary:
            root = tk.Tk()
            root.withdraw()
            settings = Path(temporary) / "settings.json"
            try:
                with (
                    patch.object(app_module, "default_settings_path", return_value=settings),
                    patch.object(app_module, "DEFAULT_DATA_DIR", Path(temporary)),
                ):
                    studio = app_module.MPQStudioApp(root)
                    root.update_idletasks()
                    self.assertEqual(studio.notebook.tab(studio.export_tab, "text"), "EXPORTAR")
                    self.assertEqual(studio.export_status.get(), "Selecciona un archivo MPQ.")

                    studio.toggle_language()
                    root.update_idletasks()
                    self.assertEqual(studio.language, "en")
                    self.assertEqual(studio.notebook.tab(studio.export_tab, "text"), "EXPORT")
                    self.assertEqual(studio.archive_tree.heading("#0", "text"), "Name")
                    self.assertEqual(
                        studio.archive_menu.entrycget(0, "label"),
                        "Add selection to extraction queue",
                    )
                    self.assertEqual(studio.language_button.cget("text"), "Español")
                    self.assertEqual(load_language_setting(settings), "en")

                    studio.toggle_language()
                    self.assertEqual(studio.notebook.tab(studio.export_tab, "text"), "EXPORTAR")
                    self.assertEqual(
                        studio.archive_menu.entrycget(0, "label"),
                        "Añadir selección a extracción",
                    )
                    self.assertEqual(load_language_setting(settings), "es")
            except tk.TclError as exc:
                self.skipTest(f"no se pudo inicializar Tk: {exc}")
            finally:
                root.destroy()

    def test_mpq_flags_are_shown_in_hex_and_plain_language(self) -> None:
        description = describe_mpq_flags(MPQ_FILE_EXISTS | MPQ_FILE_COMPRESS)
        self.assertEqual(description, "0x80000200 · EXISTE | COMPRIMIDO")

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

    def test_patch_a_follows_patch_nine(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "patch-9.MPQ").touch()
            plan = plan_patch(root)
            self.assertEqual(plan.patch_name, "patch-A.MPQ")
            self.assertEqual(plan.previous_patch, "patch-9.MPQ")

    def test_patch_letters_advance_and_ignore_patch_ten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "patch-9.MPQ").touch()
            (root / "patch-A.MPQ").touch()
            (root / "patch-10.MPQ").touch()
            plan = plan_patch(root)
            self.assertEqual(plan.patch_name, "patch-B.MPQ")
            self.assertEqual(plan.previous_patch, "patch-A.MPQ")

    def test_localized_patches_advance_from_nine_to_a_and_b(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            locale = Path(temporary) / "esES"
            locale.mkdir()
            (locale / "patch-esES-9.MPQ").touch()
            self.assertEqual(plan_patch(locale).patch_name, "patch-esES-A.MPQ")
            (locale / "patch-esES-A.MPQ").touch()
            self.assertEqual(plan_patch(locale).patch_name, "patch-esES-B.MPQ")

    def test_patch_z_is_reported_as_final_supported_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "patch-Z.MPQ").touch()
            with self.assertRaisesRegex(PackagingError, "último sufijo compatible"):
                plan_patch(root)

    def test_locale_directory_uses_localized_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            locale = Path(temporary) / "esES"
            locale.mkdir()
            self.assertEqual(plan_patch(locale).patch_name, "patch-esES-1.MPQ")


class PackagingRoundTripTest(unittest.TestCase):
    def test_optional_listfile_is_written_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = prepare_workspace(root / "workspace")
            internal_path = "Interface\\Demo\\sample.txt"
            source = workspace.package_dir / "Interface" / "Demo" / "sample.txt"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"demo payload")
            destination = root / "destination"
            destination.mkdir()
            plan = plan_patch(destination)

            create_and_install_patch(
                [(internal_path, source)], plan, include_listfile=True
            )

            with MPQArchive(plan.target) as archive:
                inventory = archive.inventory()
                self.assertEqual(archive.active_entry_count, 2)
                self.assertTrue(inventory.has_listfile)
                self.assertEqual(inventory.unknown_entries, 0)
                self.assertEqual(
                    archive.read_file("(listfile)"),
                    (internal_path + "\r\n").encode("utf-8"),
                )

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
                self.assertFalse(archive.inventory().has_listfile)
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
