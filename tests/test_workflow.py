"""Pruebas del flujo seguro de exportación y empaquetado."""

from __future__ import annotations

import tempfile
import struct
import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from azaleacore_mpq_studio.app import (
    calculate_mpq_sha256,
    describe_mpq_flags,
    filter_mpq_files,
    format_error_for_clipboard,
    _set_windows_app_user_model_id,
)
from azaleacore_mpq_studio.i18n import normalize_language, translate_text
from azaleacore_mpq_studio.blp import rgba_to_blp2, validate_blp
from azaleacore_mpq_studio.login_background import (
    ACCOUNT_LOGIN_PATH,
    ACCOUNT_LOGIN_XML_PATH,
    BACKUP_SUFFIX,
    LOGIN_MUSIC_PATH,
    WOW_LOGO_TEXTURE_PATH,
    LOGIN_MODELS,
    apply_custom_login_logo,
    apply_custom_login_music,
    apply_login_background,
    apply_login_customization,
    apply_login_sound_volumes,
    clone_mpq_replacing_file,
    custom_login_music_is_active,
    detect_login_background,
    detect_login_colors,
    detect_hidden_login_logos,
    detect_centered_wow_logo,
    custom_login_logo_is_active,
    find_global_logo_archive,
    find_login_archives,
    find_login_music_archive,
    read_login_sound_volumes,
    restore_custom_login_music,
    restore_login_background,
    restore_custom_login_logo,
    restore_login_sound_volumes,
    rewrite_account_login,
    rewrite_account_login_colors,
    rewrite_account_login_xml,
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
    def test_rewrite_account_login_supports_original_classic_and_wrath_branches(self) -> None:
        original = (
            b'AccountLogin:SetModel("Interface\\\\Glues\\\\Models\\\\UI_MainMenu\\\\UI_MainMenu.m2")\r\n'
            b'AccountLogin:SetModel("Interface\\\\Glues\\\\Models\\\\UI_MainMenu_Northrend\\\\UI_MainMenu_Northrend.m2")\r\n'
        )
        updated = rewrite_account_login(original, "burning_crusade")
        expected = LOGIN_MODELS["burning_crusade"].replace("\\", "\\\\").encode()
        self.assertEqual(updated.count(expected), 2)
        self.assertEqual(detect_login_background(updated), "burning_crusade")

    def test_clone_replaces_one_file_and_preserves_other_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.MPQ"
            destination = root / "destination.MPQ"
            build_mpq(
                [
                    (ACCOUNT_LOGIN_PATH, b'AccountLogin:SetModel("old.m2")'),
                    ("Interface\\Demo\\keep.bin", b"keep me"),
                ],
                source,
            )
            clone_mpq_replacing_file(
                source,
                destination,
                ACCOUNT_LOGIN_PATH,
                b'AccountLogin:SetModel("new.m2")',
            )
            with MPQArchive(destination) as archive:
                self.assertEqual(archive.active_entry_count, 2)
                self.assertEqual(
                    archive.read_file(ACCOUNT_LOGIN_PATH),
                    b'AccountLogin:SetModel("new.m2")',
                )
                self.assertEqual(
                    archive.read_file("Interface\\Demo\\keep.bin"), b"keep me"
                )

    def test_login_logos_can_be_hidden_and_shown_without_removing_objects(self) -> None:
        original = (
            b'<Texture file="Interface\\Glues\\Mainmenu\\Glues-BlizzardLogo">\r\n'
            b'<Texture name="WorldOfWarcraftRating" hidden="true">\r\n'
            b'<Texture name="AccountLoginLogo">\r\n'
            b'  <Anchors><Anchor point="TOPLEFT"><Offset>'
            b'<AbsDimension x="3" y="-7"/></Offset></Anchor></Anchors>\r\n'
            b'</Texture>\r\n'
        )
        hidden = rewrite_account_login_xml(
            original,
            hide_blizzard_logo=True,
            hide_rating_logo=True,
            center_wow_logo=True,
        )
        self.assertEqual(detect_hidden_login_logos(hidden), (True, True))
        self.assertTrue(detect_centered_wow_logo(hidden))
        self.assertIn(
            b'file="Interface\\Glues\\Common\\Glues-WoW-WotLKLogo"', hidden
        )
        self.assertIn(b"Glues-BlizzardLogo", hidden)
        self.assertIn(b"WorldOfWarcraftRating", hidden)
        self.assertIn(b'point="CENTER"', hidden)
        self.assertIn(b'x="0" y="90"', hidden)

        visible = rewrite_account_login_xml(
            hidden,
            hide_blizzard_logo=False,
            hide_rating_logo=False,
            center_wow_logo=False,
        )
        self.assertEqual(detect_hidden_login_logos(visible), (False, False))
        self.assertFalse(detect_centered_wow_logo(visible))
        self.assertIn(b'point="TOPLEFT"', visible)
        self.assertIn(b'x="3" y="-7"', visible)
        self.assertIn(b'hidden="true"', visible)

    def test_login_button_colors_can_be_applied_detected_and_removed(self) -> None:
        original = (
            b'AccountLogin:SetModel("old.m2")\r\n'
            b'function AccountLogin_OnShow(self)\r\n'
            b'end\r\n'
        )
        updated = rewrite_account_login_colors(
            original,
            (1.0, 0.08, 0.08),
            (1.0, 0.95, 0.90),
        )
        self.assertEqual(
            detect_login_colors(updated),
            ((1.0, 0.08, 0.08), (1.0, 0.95, 0.90)),
        )
        self.assertIn(b"texture:SetVertexColor", updated)
        self.assertIn(b"fontString:SetTextColor", updated)
        self.assertEqual(
            rewrite_account_login_colors(updated, None, None),
            original,
        )

    def test_login_button_colors_detect_legacy_live_test_block(self) -> None:
        payload = b"""-- AZALEACORE_LOGIN_COLORS_BEGIN
function AzaleaApplyLoginColors()
    texture:SetVertexColor(1.00, 0.08, 0.08);
    label:SetTextColor(1.00, 0.95, 0.90);
end
-- AZALEACORE_LOGIN_COLORS_END
"""
        self.assertEqual(
            detect_login_colors(payload),
            ((1.0, 0.08, 0.08), (1.0, 0.95, 0.90)),
        )

    def test_customization_updates_lua_and_xml_together(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "patch-esES-3.MPQ"
            lua = (
                b'AccountLogin:SetModel("Interface\\Glues\\Models\\UI_MainMenu\\UI_MainMenu.m2")\r\n'
                b'function AccountLogin_OnShow(self)\r\n'
                b'end\r\n'
            )
            xml = (
                b'<Texture file="Interface\\Glues\\Mainmenu\\Glues-BlizzardLogo">\n'
                b'<Texture name="WorldOfWarcraftRating" hidden="true">\n'
                b'<Texture name="AccountLoginLogo">\n'
                b' <Anchors><Anchor point="TOPLEFT"><Offset>'
                b'<AbsDimension x="3" y="-7"/></Offset></Anchor></Anchors>\n'
                b'</Texture>\n'
            )
            build_mpq(
                [(ACCOUNT_LOGIN_PATH, lua), (ACCOUNT_LOGIN_XML_PATH, xml)],
                archive_path,
            )
            result = apply_login_customization(
                archive_path,
                "northrend",
                hide_blizzard_logo=True,
                hide_rating_logo=True,
                center_wow_logo=True,
                button_color=(0.25, 0.50, 0.75),
                text_color=(1.0, 0.90, 0.80),
            )
            self.assertTrue(result.hide_blizzard_logo)
            self.assertTrue(result.hide_rating_logo)
            self.assertTrue(result.center_wow_logo)
            with MPQArchive(archive_path) as archive:
                self.assertEqual(
                    detect_login_background(archive.read_file(ACCOUNT_LOGIN_PATH)),
                    "northrend",
                )
                self.assertEqual(
                    detect_login_colors(archive.read_file(ACCOUNT_LOGIN_PATH)),
                    ((0.25, 0.50, 0.75), (1.0, 0.90, 0.80)),
                )
                self.assertEqual(
                    detect_hidden_login_logos(archive.read_file(ACCOUNT_LOGIN_XML_PATH)),
                    (True, True),
                )
                self.assertTrue(
                    detect_centered_wow_logo(archive.read_file(ACCOUNT_LOGIN_XML_PATH))
                )

    def test_custom_logo_uses_global_patch_and_restores_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "Data"
            data.mkdir()
            archive_path = data / "patch-9.MPQ"
            build_mpq([("Interface\\Demo\\keep.bin", b"keep")], archive_path)
            self.assertEqual(find_global_logo_archive(root), archive_path)
            backup = apply_custom_login_logo(archive_path, b"custom-blp-payload")
            self.assertTrue(backup.is_file())
            self.assertTrue(custom_login_logo_is_active(archive_path))
            with MPQArchive(archive_path) as archive:
                self.assertEqual(
                    archive.read_file(WOW_LOGO_TEXTURE_PATH),
                    b"custom-blp-payload",
                )
                self.assertEqual(
                    archive.read_file("Interface\\Demo\\keep.bin"), b"keep"
                )
            restore_custom_login_logo(archive_path)
            self.assertFalse(custom_login_logo_is_active(archive_path))
            with MPQArchive(archive_path) as archive:
                self.assertIsNone(archive.read_file(WOW_LOGO_TEXTURE_PATH))

    def test_png_logo_converts_to_wow_blp2_with_alpha_and_mipmaps(self) -> None:
        image = Image.new("RGBA", (300, 100), (200, 30, 80, 128))
        payload = rgba_to_blp2(image)
        self.assertEqual(validate_blp(payload), (512, 256))
        self.assertEqual(payload[:4], b"BLP2")
        self.assertEqual(payload[8:12], bytes((2, 8, 7, 1)))
        first_offset = struct.unpack_from("<I", payload, 20)[0]
        first_size = struct.unpack_from("<I", payload, 84)[0]
        self.assertEqual(first_offset, 1172)
        self.assertEqual(first_size, 512 * 256)

    def test_apply_detect_and_restore_login_background(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            locale = root / "Data" / "esES"
            locale.mkdir(parents=True)
            archive_path = locale / "patch-esES-3.MPQ"
            original_lua = (
                b'AccountLogin:SetModel("Interface\\\\Glues\\\\Models\\\\'
                b'UI_MainMenu_Northrend\\\\UI_MainMenu_Northrend.m2")'
            )
            build_mpq([(ACCOUNT_LOGIN_PATH, original_lua)], archive_path)

            self.assertEqual(find_login_archives(root), (archive_path,))
            result = apply_login_background(archive_path, "classic")
            self.assertTrue(result.backup.is_file())
            self.assertEqual(result.backup.name, archive_path.name + BACKUP_SUFFIX)
            with MPQArchive(archive_path) as archive:
                changed = archive.read_file(ACCOUNT_LOGIN_PATH)
            self.assertEqual(detect_login_background(changed), "classic")

            restore_login_background(archive_path)
            with MPQArchive(archive_path) as archive:
                self.assertEqual(archive.read_file(ACCOUNT_LOGIN_PATH), original_lua)

    @unittest.skipUnless(sys.platform == "win32", "solo Windows tiene barra de tareas")
    def test_windows_app_user_model_id_can_be_set(self) -> None:
        self.assertTrue(_set_windows_app_user_model_id())

    def test_application_icon_contains_expected_windows_sizes(self) -> None:
        icon = APP_ICON.read_bytes()
        reserved, resource_type, count = struct.unpack_from("<HHH", icon)
        self.assertEqual((reserved, resource_type, count), (0, 1, 7))
        dimensions = tuple(icon[6 + index * 16] or 256 for index in range(count))
        self.assertEqual(dimensions, (16, 24, 32, 48, 64, 128, 256))

    def test_custom_login_music_round_trip_and_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / "Data"
            data.mkdir()
            archive_path = data / "patch-9.MPQ"
            original = b"\xff\xfb\x90\x64" + b"original" * 100
            replacement = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x64" + b"custom" * 100
            build_mpq([(LOGIN_MUSIC_PATH, original)], archive_path)

            self.assertEqual(find_login_music_archive(root), archive_path)
            apply_custom_login_music(archive_path, replacement)
            self.assertTrue(custom_login_music_is_active(archive_path))
            with MPQArchive(archive_path) as archive:
                self.assertEqual(archive.read_file(LOGIN_MUSIC_PATH), replacement)

            restore_custom_login_music(archive_path)
            with MPQArchive(archive_path) as archive:
                self.assertEqual(archive.read_file(LOGIN_MUSIC_PATH), original)

    def test_login_sound_volumes_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_dir = root / "WTF"
            config_dir.mkdir()
            config = config_dir / "Config.wtf"
            original = (
                'SET Sound_MusicVolume "0.10"\\r\\n'
                'SET Sound_AmbienceVolume "0.20"\\r\\n'
            ).encode()
            config.write_bytes(original)

            backup = apply_login_sound_volumes(root, 0.65, 0.35)
            self.assertTrue(backup.is_file())
            self.assertEqual(read_login_sound_volumes(root), (0.65, 0.35))
            self.assertIn('SET Sound_EnableMusic "1"', config.read_text())

            restore_login_sound_volumes(root)
            self.assertEqual(config.read_bytes(), original)

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
