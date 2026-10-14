"""Cambio seguro del modelo animado de la pantalla de acceso de WoW 3.3.5a."""

from __future__ import annotations

import os
import re
import shutil
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .mpq import (
    DELETED_HASH,
    EMPTY_HASH,
    MPQ_FILE_EXISTS,
    MPQ_FILE_SINGLE_UNIT,
    MPQArchive,
    MPQError,
    mpq_hash,
)
from .packer import _encrypt_table


ACCOUNT_LOGIN_PATH = "Interface\\GlueXML\\AccountLogin.lua"
ACCOUNT_LOGIN_XML_PATH = "Interface\\GlueXML\\AccountLogin.xml"
ORIGINAL_WOW_LOGO_PATH = "Interface\\Glues\\Common\\Glues-WoW-WotLKLogo"
WOW_LOGO_TEXTURE_PATH = ORIGINAL_WOW_LOGO_PATH + ".blp"
LOGIN_MUSIC_PATH = "Sound\\Music\\GlueScreenMusic\\WotLK_main_title.mp3"
BACKUP_SUFFIX = ".before-login-background"
RESTORE_SAFETY_SUFFIX = ".before-login-restore"
LOGO_BACKUP_SUFFIX = ".before-login-logo"
LOGO_RESTORE_SAFETY_SUFFIX = ".before-login-logo-restore"
MUSIC_BACKUP_SUFFIX = ".before-login-music"
MUSIC_RESTORE_SAFETY_SUFFIX = ".before-login-music-restore"
SOUND_CONFIG_BACKUP_SUFFIX = ".before-login-audio"

LOGIN_MODELS = {
    "classic": "Interface\\Glues\\Models\\UI_MainMenu\\UI_MainMenu.m2",
    "burning_crusade": (
        "Interface\\Glues\\Models\\UI_MainMenu_BurningCrusade\\"
        "UI_MainMenu_BurningCrusade.m2"
    ),
    "northrend": (
        "Interface\\Glues\\Models\\UI_MainMenu_Northrend\\"
        "UI_MainMenu_Northrend.m2"
    ),
}

_SET_MODEL_RE = re.compile(
    r'AccountLogin:SetModel\(\s*["\'][^"\']+["\']\s*\)', re.IGNORECASE
)
_COLOR_BLOCK_RE = re.compile(
    r"-- AZALEACORE_LOGIN_COLORS_BEGIN.*?"
    r"-- AZALEACORE_LOGIN_COLORS_END(?:\r?\n){0,2}",
    re.DOTALL,
)
_COLOR_CALL_RE = re.compile(
    r"^[ \t]*AzaleaApplyLoginColors\(\);[ \t]*\r?\n?",
    re.MULTILINE,
)
_COLOR_VALUE_RE = re.compile(
    r"AZALEA_LOGIN_(BUTTON|TEXT)_COLOR\s*=\s*"
    r"\{\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\}"
)
_LEGACY_BUTTON_COLOR_RE = re.compile(
    r"texture:SetVertexColor\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)"
)
_LEGACY_TEXT_COLOR_RE = re.compile(
    r"(?:label|fontString):SetTextColor\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\)"
)


class LoginBackgroundError(RuntimeError):
    """Problema recuperable durante el cambio del fondo de acceso."""


@dataclass(frozen=True)
class LoginBackgroundResult:
    archive: Path
    backup: Path
    model_path: str
    hide_blizzard_logo: bool = False
    hide_rating_logo: bool = False
    center_wow_logo: bool = False


def _decode_lua(payload: bytes) -> tuple[str, str, bytes]:
    bom = b"\xef\xbb\xbf" if payload.startswith(b"\xef\xbb\xbf") else b""
    raw = payload[len(bom) :]
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding), encoding, bom
        except UnicodeDecodeError:
            continue
    raise LoginBackgroundError("No se pudo decodificar AccountLogin.lua.")


def rewrite_account_login(payload: bytes, background: str) -> bytes:
    """Fuerza todas las ramas del login a usar uno de los M2 nativos conocidos."""
    try:
        model_path = LOGIN_MODELS[background]
    except KeyError as exc:
        raise LoginBackgroundError(f"Fondo de login desconocido: {background}") from exc

    text, encoding, bom = _decode_lua(payload)
    lua_path = model_path.replace("\\", "\\\\")
    replacement = f'AccountLogin:SetModel("{lua_path}")'
    updated, replacements = _SET_MODEL_RE.subn(lambda _match: replacement, text)
    if replacements == 0:
        raise LoginBackgroundError(
            "AccountLogin.lua no contiene ninguna llamada AccountLogin:SetModel compatible."
        )
    return bom + updated.encode(encoding)


def _validated_color(
    color: tuple[float, float, float], label: str
) -> tuple[float, float, float]:
    if len(color) != 3 or any(not 0.0 <= channel <= 1.0 for channel in color):
        raise LoginBackgroundError(
            f"El color de {label} debe contener tres valores entre 0 y 1."
        )
    return tuple(float(channel) for channel in color)


def rewrite_account_login_colors(
    payload: bytes,
    button_color: tuple[float, float, float] | None,
    text_color: tuple[float, float, float] | None,
) -> bytes:
    """Añade o retira el tinte RGB de los botones visibles del login."""
    if (button_color is None) != (text_color is None):
        raise LoginBackgroundError(
            "El color del botón y del texto deben configurarse juntos."
        )
    text, encoding, bom = _decode_lua(payload)
    newline = "\r\n" if "\r\n" in text else "\n"
    text = _COLOR_CALL_RE.sub("", text)
    text = _COLOR_BLOCK_RE.sub("", text)
    if button_color is None:
        return bom + text.encode(encoding)

    button = _validated_color(button_color, "botón")
    label = _validated_color(text_color, "texto")
    marker = "function AccountLogin_OnShow(self)"
    if marker not in text:
        raise LoginBackgroundError(
            "AccountLogin.lua no contiene AccountLogin_OnShow para aplicar colores."
        )
    button_values = ", ".join(f"{channel:.3f}" for channel in button)
    text_values = ", ".join(f"{channel:.3f}" for channel in label)
    block = f"""-- AZALEACORE_LOGIN_COLORS_BEGIN
AZALEA_LOGIN_BUTTON_COLOR = {{{button_values}}};
AZALEA_LOGIN_TEXT_COLOR = {{{text_values}}};

function AzaleaApplyLoginColors()
    local buttons = {{
        AccountLoginLoginButton,
        AccountLoginExitButton,
        AccountLoginTOSButton,
        AccountLoginCreditsButton,
        AccountLoginCinematicsButton,
        OptionsButton,
        AccountLoginCommunityButton,
        AccountLoginManageAccountButton
    }};
    for _, button in ipairs(buttons) do
        if ( button ) then
            local textures = {{
                button:GetNormalTexture(),
                button:GetPushedTexture(),
                button:GetDisabledTexture(),
                button:GetHighlightTexture()
            }};
            for _, texture in ipairs(textures) do
                if ( texture ) then
                    texture:SetVertexColor(
                        AZALEA_LOGIN_BUTTON_COLOR[1],
                        AZALEA_LOGIN_BUTTON_COLOR[2],
                        AZALEA_LOGIN_BUTTON_COLOR[3]
                    );
                end
            end
            local fontString = button:GetFontString();
            if ( fontString ) then
                fontString:SetTextColor(
                    AZALEA_LOGIN_TEXT_COLOR[1],
                    AZALEA_LOGIN_TEXT_COLOR[2],
                    AZALEA_LOGIN_TEXT_COLOR[3]
                );
            end
        end
    end
end
-- AZALEACORE_LOGIN_COLORS_END

"""
    block = block.replace("\n", newline)
    text = text.replace(
        marker,
        block + marker + newline + "\tAzaleaApplyLoginColors();",
        1,
    )
    return bom + text.encode(encoding)


def detect_login_colors(
    payload: bytes,
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    text, _encoding, _bom = _decode_lua(payload)
    values: dict[str, tuple[float, float, float]] = {}
    for match in _COLOR_VALUE_RE.finditer(text):
        values[match.group(1)] = tuple(
            float(match.group(index)) for index in (2, 3, 4)
        )
    if "BUTTON" in values and "TEXT" in values:
        return values["BUTTON"], values["TEXT"]
    if "-- AZALEACORE_LOGIN_COLORS_BEGIN" in text:
        button = _LEGACY_BUTTON_COLOR_RE.search(text)
        label = _LEGACY_TEXT_COLOR_RE.search(text)
        if button is not None and label is not None:
            return (
                tuple(float(button.group(index)) for index in (1, 2, 3)),
                tuple(float(label.group(index)) for index in (1, 2, 3)),
            )
    return None


def detect_login_background(payload: bytes) -> str | None:
    text, _encoding, _bom = _decode_lua(payload)
    normalized = text.replace("\\\\", "\\").casefold()
    matches = [
        key for key, model in LOGIN_MODELS.items() if model.casefold() in normalized
    ]
    return matches[0] if len(matches) == 1 else None


def _set_tag_attribute(tag: str, name: str, value: str | None) -> str:
    pattern = re.compile(rf"\s+{re.escape(name)}\s*=\s*([\"']).*?\1", re.IGNORECASE)
    cleaned = pattern.sub("", tag)
    if value is None:
        return cleaned
    return cleaned[:-1] + f' {name}="{value}">'


def rewrite_account_login_xml(
    payload: bytes,
    *,
    hide_blizzard_logo: bool,
    hide_rating_logo: bool,
    center_wow_logo: bool = False,
) -> bytes:
    """Ajusta los logotipos sin eliminar objetos esperados por el cliente."""
    text, encoding, bom = _decode_lua(payload)
    blizzard_re = re.compile(
        r'<Texture\b[^>]*\bfile\s*=\s*(["\'])'
        r'Interface\\Glues\\Mainmenu\\Glues-BlizzardLogo\1[^>]*>',
        re.IGNORECASE,
    )
    rating_re = re.compile(
        r'<Texture\b[^>]*\bname\s*=\s*(["\'])WorldOfWarcraftRating\1[^>]*>',
        re.IGNORECASE,
    )

    def update_blizzard(match: re.Match[str]) -> str:
        tag = _set_tag_attribute(match.group(0), "alpha", "0" if hide_blizzard_logo else None)
        return _set_tag_attribute(tag, "hidden", "true" if hide_blizzard_logo else None)

    def update_rating(match: re.Match[str]) -> str:
        return _set_tag_attribute(
            match.group(0), "alpha", "0" if hide_rating_logo else None
        )

    updated, blizzard_count = blizzard_re.subn(update_blizzard, text, count=1)
    updated, rating_count = rating_re.subn(update_rating, updated, count=1)
    if blizzard_count != 1 or rating_count != 1:
        raise LoginBackgroundError(
            "AccountLogin.xml no contiene los elementos esperados de Blizzard y clasificación."
        )

    wow_logo_re = re.compile(
        r'<Texture\b(?=[^>]*\bname\s*=\s*(["\'])AccountLoginLogo\1)[^>]*>'
        r'.*?</Texture>',
        re.IGNORECASE | re.DOTALL,
    )
    wow_logo_match = wow_logo_re.search(updated)
    if wow_logo_match is None:
        raise LoginBackgroundError(
            "AccountLogin.xml no contiene el elemento AccountLoginLogo."
        )
    logo_block = wow_logo_match.group(0)
    opening_end = logo_block.find(">") + 1
    opening_tag = logo_block[:opening_end]
    opening_tag = _set_tag_attribute(
        opening_tag,
        "file",
        ORIGINAL_WOW_LOGO_PATH,
    )
    logo_block = opening_tag + logo_block[opening_end:]
    anchor_re = re.compile(
        r'(?P<indent>[ \t]*)<Anchor\b[^>]*>.*?</Anchor>',
        re.IGNORECASE | re.DOTALL,
    )
    anchor_match = anchor_re.search(logo_block)
    if anchor_match is None:
        raise LoginBackgroundError("AccountLoginLogo no contiene un anclaje compatible.")
    indent = anchor_match.group("indent")
    newline = "\r\n" if "\r\n" in logo_block else "\n"
    point, x, y = ("CENTER", 0, 90) if center_wow_logo else ("TOPLEFT", 3, -7)
    anchor = (
        f'{indent}<Anchor point="{point}">{newline}'
        f'{indent}\t<Offset>{newline}'
        f'{indent}\t\t<AbsDimension x="{x}" y="{y}"/>{newline}'
        f'{indent}\t</Offset>{newline}'
        f'{indent}</Anchor>'
    )
    logo_block = anchor_re.sub(anchor, logo_block, count=1)
    updated = (
        updated[: wow_logo_match.start()]
        + logo_block
        + updated[wow_logo_match.end() :]
    )
    return bom + updated.encode(encoding)


def detect_hidden_login_logos(payload: bytes) -> tuple[bool, bool]:
    text, _encoding, _bom = _decode_lua(payload)
    blizzard = re.search(
        r'<Texture\b(?=[^>]*Glues-BlizzardLogo)[^>]*\balpha\s*=\s*["\']0["\'][^>]*>',
        text,
        re.IGNORECASE,
    )
    rating = re.search(
        r'<Texture\b(?=[^>]*WorldOfWarcraftRating)[^>]*\balpha\s*=\s*["\']0["\'][^>]*>',
        text,
        re.IGNORECASE,
    )
    return blizzard is not None, rating is not None


def detect_centered_wow_logo(payload: bytes) -> bool:
    """Indica si el logo principal está anclado al centro sobre el formulario."""
    text, _encoding, _bom = _decode_lua(payload)
    block = re.search(
        r'<Texture\b(?=[^>]*\bname\s*=\s*(["\'])AccountLoginLogo\1)[^>]*>'
        r'.*?</Texture>',
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if block is None:
        return False
    return re.search(
        r'<Anchor\b[^>]*\bpoint\s*=\s*["\']CENTER["\'][^>]*>',
        block.group(0),
        re.IGNORECASE,
    ) is not None


def find_login_archives(game_root: Path | str) -> tuple[Path, ...]:
    """Localiza los patch-<locale>-3.MPQ que realmente contienen AccountLogin.lua."""
    root = Path(game_root).resolve()
    data = root / "Data"
    if not data.is_dir():
        return ()
    candidates: list[Path] = []
    for archive_path in sorted(data.glob("*/patch-*-3.MPQ"), key=lambda p: str(p).casefold()):
        try:
            with MPQArchive(archive_path) as archive:
                if archive.contains(ACCOUNT_LOGIN_PATH):
                    candidates.append(archive_path)
        except (OSError, MPQError):
            continue
    return tuple(candidates)


def find_global_logo_archive(game_root: Path | str) -> Path | None:
    """Devuelve el parche global de laboratorio usado para sobrescribir texturas."""
    candidate = Path(game_root).resolve() / "Data" / "patch-9.MPQ"
    return candidate if candidate.is_file() else None


def validate_login_music(payload: bytes) -> None:
    """Comprueba que el contenido incluye al menos una trama MP3 Layer III válida."""
    if len(payload) < 4:
        raise LoginBackgroundError("El archivo MP3 está vacío o truncado.")
    offset = 0
    if payload.startswith(b"ID3"):
        if len(payload) < 10 or any(byte & 0x80 for byte in payload[6:10]):
            raise LoginBackgroundError("La cabecera ID3 del MP3 no es válida.")
        offset = 10 + sum(
            byte << shift for byte, shift in zip(payload[6:10], (21, 14, 7, 0))
        )
        if payload[5] & 0x10:
            offset += 10
    limit = min(len(payload) - 3, offset + 1024 * 1024)
    for position in range(offset, max(offset, limit)):
        header = int.from_bytes(payload[position : position + 4], "big")
        version = (header >> 19) & 0x3
        layer = (header >> 17) & 0x3
        bitrate = (header >> 12) & 0xF
        sample_rate = (header >> 10) & 0x3
        if (
            header & 0xFFE00000 == 0xFFE00000
            and version != 1
            and layer == 1
            and bitrate not in (0, 15)
            and sample_rate != 3
        ):
            return
    raise LoginBackgroundError("No se encontró ninguna trama MP3 Layer III válida.")


def find_login_music_archive(game_root: Path | str) -> Path | None:
    """Localiza el parche global de mayor prioridad que define la música del login."""
    data = Path(game_root).resolve() / "Data"
    def priority(path: Path) -> int:
        match = re.fullmatch(r"patch-([1-9A-Z])\.mpq", path.name, re.IGNORECASE)
        if match is None:
            return 0
        suffix = match.group(1).upper()
        return int(suffix) if suffix.isdigit() else 10 + ord(suffix) - ord("A")

    candidates = sorted(
        (
            path
            for path in data.iterdir()
            if path.is_file()
            and path.suffix.casefold() == ".mpq"
            and ".before-" not in path.name.casefold()
        ),
        key=priority,
        reverse=True,
    )
    for archive_path in candidates:
        try:
            with MPQArchive(archive_path) as archive:
                if archive.contains(LOGIN_MUSIC_PATH):
                    return archive_path
        except (OSError, MPQError):
            continue
    return find_global_logo_archive(game_root)


def clone_mpq_replacing_files(
    source: Path | str,
    destination: Path | str,
    replacements: dict[str, bytes],
    *,
    allow_new: bool = False,
) -> None:
    """Clona un MPQ y sustituye entradas sin reconstruir ni perder bloques desconocidos."""
    source_path = Path(source).resolve()
    destination_path = Path(destination).resolve()
    if destination_path.exists():
        raise LoginBackgroundError(f"El destino ya existe: {destination_path}")
    if not replacements:
        raise LoginBackgroundError("No hay archivos internos para sustituir.")

    original = source_path.read_bytes()
    with MPQArchive(source_path) as archive:
        block_indices: dict[str, int] = {}
        hashes = list(archive.hash_table)
        blocks = list(archive.block_table)
        added = 0
        for internal_path in replacements:
            block_index = archive._find_block_index(internal_path)
            if block_index is None:
                if not allow_new:
                    raise LoginBackgroundError(
                        f"No se encontró {internal_path} en {source_path.name}."
                    )
                block_index = len(blocks)
                blocks.append((0, 0, 0, 0))
                slot = mpq_hash(internal_path, 0) % len(hashes)
                for _step in range(len(hashes)):
                    if hashes[slot][4] in (EMPTY_HASH, DELETED_HASH):
                        hashes[slot] = (
                            mpq_hash(internal_path, 1),
                            mpq_hash(internal_path, 2),
                            0,
                            0,
                            block_index,
                        )
                        added += 1
                        break
                    slot = (slot + 1) % len(hashes)
                else:
                    raise LoginBackgroundError(
                        "La tabla hash del MPQ no tiene espacio para el logo personalizado."
                    )
            block_indices[internal_path] = block_index
        active_entries = archive.active_entry_count

    data = bytearray()
    for internal_path, payload in replacements.items():
        file_pos = len(original) + len(data)
        data.extend(payload)
        blocks[block_indices[internal_path]] = (
            file_pos,
            len(payload),
            len(payload),
            MPQ_FILE_EXISTS | MPQ_FILE_SINGLE_UNIT,
        )
    plain_hashes = b"".join(struct.pack("<IIHHI", *entry) for entry in hashes)
    plain_blocks = b"".join(struct.pack("<4I", *entry) for entry in blocks)
    encrypted_hashes = _encrypt_table(plain_hashes, mpq_hash("(hash table)", 3))
    encrypted_blocks = _encrypt_table(plain_blocks, mpq_hash("(block table)", 3))
    hash_pos = len(original) + len(data)
    block_pos = hash_pos + len(encrypted_hashes)
    archive_size = block_pos + len(encrypted_blocks)
    if archive_size > 0xFFFFFFFF:
        raise LoginBackgroundError("El MPQ resultante supera el límite de formato de 4 GiB.")

    output = bytearray(original)
    output.extend(data)
    output.extend(encrypted_hashes)
    output.extend(encrypted_blocks)
    struct.pack_into("<I", output, 8, archive_size)
    struct.pack_into("<I", output, 16, hash_pos)
    struct.pack_into("<I", output, 20, block_pos)
    struct.pack_into("<I", output, 28, len(blocks))

    try:
        with destination_path.open("xb") as handle:
            handle.write(output)
            handle.flush()
            os.fsync(handle.fileno())
        with MPQArchive(destination_path) as check:
            if check.active_entry_count != active_entries + added:
                raise LoginBackgroundError(
                    "La validación cambió el número de entradas activas del MPQ."
                )
            for internal_path, payload in replacements.items():
                if check.read_file(internal_path) != payload:
                    raise LoginBackgroundError(
                        f"La validación byte a byte ha fallado para {internal_path}."
                    )
    except Exception:
        destination_path.unlink(missing_ok=True)
        raise


def clone_mpq_replacing_file(
    source: Path | str,
    destination: Path | str,
    internal_path: str,
    payload: bytes,
) -> None:
    clone_mpq_replacing_files(
        source, destination, {internal_path: payload}
    )


def apply_login_background(archive: Path | str, background: str) -> LoginBackgroundResult:
    """Crea el respaldo inicial y reemplaza atómicamente AccountLogin.lua."""
    archive_path = Path(archive).resolve()
    backup = archive_path.with_name(archive_path.name + BACKUP_SUFFIX)
    if not archive_path.is_file():
        raise LoginBackgroundError(f"No existe el MPQ: {archive_path}")

    with MPQArchive(archive_path) as source:
        current_lua = source.read_file(ACCOUNT_LOGIN_PATH)
    if current_lua is None:
        raise LoginBackgroundError(f"El MPQ no contiene {ACCOUNT_LOGIN_PATH}.")
    updated_lua = rewrite_account_login(current_lua, background)

    if not backup.exists():
        shutil.copy2(archive_path, backup)

    temporary_dir = Path(tempfile.mkdtemp(prefix="azaleacore-login-", dir=archive_path.parent))
    temporary_mpq = temporary_dir / archive_path.name
    try:
        clone_mpq_replacing_file(
            archive_path, temporary_mpq, ACCOUNT_LOGIN_PATH, updated_lua
        )
        os.replace(temporary_mpq, archive_path)
    except Exception as exc:
        raise LoginBackgroundError(
            "No se pudo reemplazar el MPQ. Cierra Wow.exe y vuelve a intentarlo. "
            f"Detalle: {exc}"
        ) from exc
    finally:
        shutil.rmtree(temporary_dir, ignore_errors=True)

    return LoginBackgroundResult(archive_path, backup, LOGIN_MODELS[background])


def apply_login_customization(
    archive: Path | str,
    background: str | None,
    *,
    hide_blizzard_logo: bool,
    hide_rating_logo: bool,
    center_wow_logo: bool = False,
    button_color: tuple[float, float, float] | None = None,
    text_color: tuple[float, float, float] | None = None,
) -> LoginBackgroundResult:
    """Aplica fondo y visibilidad de logotipos en una sola sustitución atómica."""
    archive_path = Path(archive).resolve()
    backup = archive_path.with_name(archive_path.name + BACKUP_SUFFIX)
    if not archive_path.is_file():
        raise LoginBackgroundError(f"No existe el MPQ: {archive_path}")

    with MPQArchive(archive_path) as source:
        current_lua = source.read_file(ACCOUNT_LOGIN_PATH)
        current_xml = source.read_file(ACCOUNT_LOGIN_XML_PATH)
    if current_lua is None or current_xml is None:
        raise LoginBackgroundError(
            "El MPQ no contiene AccountLogin.lua y AccountLogin.xml."
        )
    updated_lua = (
        current_lua
        if background is None
        else rewrite_account_login(current_lua, background)
    )
    updated_lua = rewrite_account_login_colors(
        updated_lua,
        button_color,
        text_color,
    )
    updated_xml = rewrite_account_login_xml(
        current_xml,
        hide_blizzard_logo=hide_blizzard_logo,
        hide_rating_logo=hide_rating_logo,
        center_wow_logo=center_wow_logo,
    )
    if not backup.exists():
        shutil.copy2(archive_path, backup)

    temporary_dir = Path(tempfile.mkdtemp(prefix="azaleacore-login-", dir=archive_path.parent))
    temporary_mpq = temporary_dir / archive_path.name
    try:
        clone_mpq_replacing_files(
            archive_path,
            temporary_mpq,
            {
                ACCOUNT_LOGIN_PATH: updated_lua,
                ACCOUNT_LOGIN_XML_PATH: updated_xml,
            },
        )
        os.replace(temporary_mpq, archive_path)
    except Exception as exc:
        raise LoginBackgroundError(
            "No se pudo reemplazar el MPQ. Cierra Wow.exe y vuelve a intentarlo. "
            f"Detalle: {exc}"
        ) from exc
    finally:
        shutil.rmtree(temporary_dir, ignore_errors=True)

    return LoginBackgroundResult(
        archive_path,
        backup,
        (
            LOGIN_MODELS[background]
            if background is not None
            else "Sin cambios (se conserva el M2 actual)"
        ),
        hide_blizzard_logo,
        hide_rating_logo,
        center_wow_logo,
    )


def custom_login_logo_is_active(archive: Path | str) -> bool:
    archive_path = Path(archive).resolve()
    backup = archive_path.with_name(archive_path.name + LOGO_BACKUP_SUFFIX)
    if not archive_path.is_file() or not backup.is_file():
        return False
    with MPQArchive(archive_path) as current, MPQArchive(backup) as original:
        current_logo = current.read_file(WOW_LOGO_TEXTURE_PATH)
        original_logo = original.read_file(WOW_LOGO_TEXTURE_PATH)
    return current_logo is not None and current_logo != original_logo


def apply_custom_login_logo(archive: Path | str, payload: bytes) -> Path:
    """Instala el BLP sobre la ruta global conocida y conserva el MPQ inicial."""
    archive_path = Path(archive).resolve()
    backup = archive_path.with_name(archive_path.name + LOGO_BACKUP_SUFFIX)
    if not archive_path.is_file():
        raise LoginBackgroundError(f"No existe el MPQ global: {archive_path}")
    if not payload:
        raise LoginBackgroundError("El logo personalizado está vacío.")
    if not backup.exists():
        shutil.copy2(archive_path, backup)

    temporary_dir = Path(tempfile.mkdtemp(prefix="azaleacore-logo-", dir=archive_path.parent))
    temporary_mpq = temporary_dir / archive_path.name
    try:
        clone_mpq_replacing_files(
            archive_path,
            temporary_mpq,
            {WOW_LOGO_TEXTURE_PATH: payload},
            allow_new=True,
        )
        os.replace(temporary_mpq, archive_path)
    except Exception as exc:
        raise LoginBackgroundError(
            "No se pudo instalar el logo en el MPQ global. Cierra Wow.exe y "
            f"vuelve a intentarlo. Detalle: {exc}"
        ) from exc
    finally:
        shutil.rmtree(temporary_dir, ignore_errors=True)
    return backup


def restore_custom_login_logo(archive: Path | str) -> Path:
    archive_path = Path(archive).resolve()
    backup = archive_path.with_name(archive_path.name + LOGO_BACKUP_SUFFIX)
    if not backup.is_file():
        raise LoginBackgroundError(f"No existe la copia del logo: {backup}")
    safety = archive_path.with_name(archive_path.name + LOGO_RESTORE_SAFETY_SUFFIX)
    if archive_path.exists() and not safety.exists():
        shutil.copy2(archive_path, safety)
    temporary = archive_path.with_name(archive_path.name + ".logo-restore.tmp")
    try:
        shutil.copy2(backup, temporary)
        os.replace(temporary, archive_path)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise LoginBackgroundError(
            "No se pudo restaurar el MPQ global. Cierra Wow.exe y vuelve a "
            f"intentarlo. Detalle: {exc}"
        ) from exc
    return backup


def custom_login_music_is_active(archive: Path | str) -> bool:
    archive_path = Path(archive).resolve()
    backup = archive_path.with_name(archive_path.name + MUSIC_BACKUP_SUFFIX)
    if not archive_path.is_file() or not backup.is_file():
        return False
    with MPQArchive(archive_path) as current, MPQArchive(backup) as original:
        current_music = current.read_file(LOGIN_MUSIC_PATH)
        original_music = original.read_file(LOGIN_MUSIC_PATH)
    return current_music is not None and current_music != original_music


def apply_custom_login_music(archive: Path | str, payload: bytes) -> Path:
    """Instala un MP3 de login y conserva el MPQ original."""
    archive_path = Path(archive).resolve()
    backup = archive_path.with_name(archive_path.name + MUSIC_BACKUP_SUFFIX)
    if not archive_path.is_file():
        raise LoginBackgroundError(f"No existe el MPQ de música: {archive_path}")
    validate_login_music(payload)
    if not backup.exists():
        shutil.copy2(archive_path, backup)

    temporary_dir = Path(
        tempfile.mkdtemp(prefix="azaleacore-music-", dir=archive_path.parent)
    )
    temporary_mpq = temporary_dir / archive_path.name
    try:
        clone_mpq_replacing_files(
            archive_path,
            temporary_mpq,
            {LOGIN_MUSIC_PATH: payload},
            allow_new=True,
        )
        os.replace(temporary_mpq, archive_path)
    except Exception as exc:
        raise LoginBackgroundError(
            "No se pudo instalar la música en el MPQ. Cierra Wow.exe y "
            f"vuelve a intentarlo. Detalle: {exc}"
        ) from exc
    finally:
        shutil.rmtree(temporary_dir, ignore_errors=True)
    return backup


def restore_custom_login_music(archive: Path | str) -> Path:
    archive_path = Path(archive).resolve()
    backup = archive_path.with_name(archive_path.name + MUSIC_BACKUP_SUFFIX)
    if not backup.is_file():
        raise LoginBackgroundError(f"No existe la copia de la música: {backup}")
    safety = archive_path.with_name(archive_path.name + MUSIC_RESTORE_SAFETY_SUFFIX)
    if archive_path.exists() and not safety.exists():
        shutil.copy2(archive_path, safety)
    temporary = archive_path.with_name(archive_path.name + ".music-restore.tmp")
    try:
        shutil.copy2(backup, temporary)
        os.replace(temporary, archive_path)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise LoginBackgroundError(
            "No se pudo restaurar la música. Cierra Wow.exe y vuelve a intentarlo. "
            f"Detalle: {exc}"
        ) from exc
    return backup


def _read_text_file(path: Path) -> tuple[str, str, bytes]:
    payload = path.read_bytes()
    bom = b"\xef\xbb\xbf" if payload.startswith(b"\xef\xbb\xbf") else b""
    raw = payload[len(bom) :]
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding), encoding, bom
        except UnicodeDecodeError:
            continue
    raise LoginBackgroundError(f"No se pudo leer {path}.")


def read_login_sound_volumes(game_root: Path | str) -> tuple[float, float]:
    config = Path(game_root).resolve() / "WTF" / "Config.wtf"
    if not config.is_file():
        return 0.5, 0.5
    text, _encoding, _bom = _read_text_file(config)

    def read_value(name: str, default: float) -> float:
        match = re.search(
            rf'^SET\s+{re.escape(name)}\s+"([^"]+)"',
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if match is None:
            return default
        try:
            return min(1.0, max(0.0, float(match.group(1))))
        except ValueError:
            return default

    return (
        read_value("Sound_MusicVolume", 0.5),
        read_value("Sound_AmbienceVolume", 0.5),
    )


def apply_login_sound_volumes(
    game_root: Path | str, music_volume: float, ambience_volume: float
) -> Path:
    """Guarda ambos volúmenes en Config.wtf para el próximo inicio del cliente."""
    for name, value in (
        ("música", music_volume),
        ("ambiente", ambience_volume),
    ):
        if not 0.0 <= value <= 1.0:
            raise LoginBackgroundError(f"El volumen de {name} debe estar entre 0 y 1.")

    root = Path(game_root).resolve()
    config = root / "WTF" / "Config.wtf"
    if not config.is_file():
        raise LoginBackgroundError(f"No existe la configuración del cliente: {config}")
    backup = config.with_name(config.name + SOUND_CONFIG_BACKUP_SUFFIX)
    if not backup.exists():
        shutil.copy2(config, backup)
    text, encoding, bom = _read_text_file(config)
    newline = "\r\n" if "\r\n" in text else "\n"

    def set_value(source: str, name: str, value: str) -> str:
        pattern = re.compile(
            rf'^SET\s+{re.escape(name)}\s+"[^"]*"',
            flags=re.IGNORECASE | re.MULTILINE,
        )
        line = f'SET {name} "{value}"'
        if pattern.search(source):
            return pattern.sub(line, source, count=1)
        return source.rstrip("\r\n") + newline + line + newline

    text = set_value(text, "Sound_MusicVolume", f"{music_volume:.2f}")
    text = set_value(text, "Sound_AmbienceVolume", f"{ambience_volume:.2f}")
    text = set_value(text, "Sound_EnableMusic", "1")
    temporary = config.with_name(config.name + ".login-audio.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(bom + text.encode(encoding))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, config)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise LoginBackgroundError(
            f"No se pudo actualizar el volumen del cliente. Detalle: {exc}"
        ) from exc
    return backup


def restore_login_sound_volumes(game_root: Path | str) -> Path:
    config = Path(game_root).resolve() / "WTF" / "Config.wtf"
    backup = config.with_name(config.name + SOUND_CONFIG_BACKUP_SUFFIX)
    if not backup.is_file():
        raise LoginBackgroundError(f"No existe la copia de audio: {backup}")
    temporary = config.with_name(config.name + ".audio-restore.tmp")
    try:
        shutil.copy2(backup, temporary)
        os.replace(temporary, config)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise LoginBackgroundError(
            f"No se pudo restaurar la configuración de audio. Detalle: {exc}"
        ) from exc
    return backup


def restore_login_background(archive: Path | str) -> Path:
    """Restaura el respaldo creado por Studio y conserva una copia del estado reemplazado."""
    archive_path = Path(archive).resolve()
    backup = archive_path.with_name(archive_path.name + BACKUP_SUFFIX)
    if not backup.is_file():
        raise LoginBackgroundError(f"No existe la copia de seguridad: {backup}")
    with MPQArchive(backup) as check:
        if check.read_file(ACCOUNT_LOGIN_PATH) is None:
            raise LoginBackgroundError("La copia de seguridad no contiene AccountLogin.lua.")

    safety = archive_path.with_name(archive_path.name + RESTORE_SAFETY_SUFFIX)
    if archive_path.exists() and not safety.exists():
        shutil.copy2(archive_path, safety)
    temporary = archive_path.with_name(archive_path.name + ".restore.tmp")
    try:
        shutil.copy2(backup, temporary)
        os.replace(temporary, archive_path)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise LoginBackgroundError(
            "No se pudo restaurar el MPQ. Cierra Wow.exe y vuelve a intentarlo. "
            f"Detalle: {exc}"
        ) from exc
    return backup
