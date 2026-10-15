"""Vista previa fiel del tinte multiplicativo de los botones del login."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, UnidentifiedImageError

from .mpq import MPQArchive, MPQError


BUTTON_TEXTURE_PATHS = (
    r"Interface\Glues\Common\Glue-Panel-Button-Up-Blue.blp",
    r"Interface\Glues\Common\Glue-Panel-Button-Up.blp",
)


def fallback_button_texture(width: int = 256, height: int = 64) -> Image.Image:
    """Crea una base azul similar al botón original cuando no hay MPQ detectado."""
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    for inset in range(4):
        shade = 48 + inset * 12
        draw.rounded_rectangle(
            (inset, inset, width - inset - 1, height - inset - 1),
            radius=max(2, 7 - inset),
            outline=(shade, shade + 14, shade + 42, 255),
        )
    for y in range(4, height - 4):
        distance = abs((height - 1) / 2 - y) / ((height - 8) / 2)
        light = round(74 - 28 * distance)
        blue = round(142 - 54 * distance)
        draw.line((4, y, width - 5, y), fill=(18, light, blue, 255))
    draw.line((9, 5, width - 10, 5), fill=(110, 153, 214, 180))
    draw.line(
        (9, height - 6, width - 10, height - 6),
        fill=(7, 16, 42, 230),
    )
    return image


def decode_button_texture(payload: bytes) -> Image.Image:
    """Decodifica la textura BLP que Pillow obtiene del MPQ del cliente."""
    with Image.open(BytesIO(payload)) as source:
        return source.convert("RGBA")


def tint_button_texture(
    texture: Image.Image, color: tuple[float, float, float]
) -> Image.Image:
    """Reproduce SetVertexColor multiplicando el RGB de la textura."""
    source = texture.convert("RGBA")
    red, green, blue, alpha = source.split()
    factors = tuple(
        round(min(1.0, max(0.0, channel)) * 255) for channel in color
    )
    tinted = ImageChops.multiply(
        Image.merge("RGB", (red, green, blue)),
        Image.new("RGB", source.size, factors),
    )
    tinted.putalpha(alpha)
    return tinted


def _candidate_archives(game_root: Path) -> tuple[Path, ...]:
    data = game_root if game_root.name.casefold() == "data" else game_root / "Data"
    candidates: list[Path] = []
    if not data.is_dir():
        return ()
    for locale_dir in sorted(
        (path for path in data.iterdir() if path.is_dir()), key=lambda path: path.name
    ):
        candidates.extend(sorted(locale_dir.glob("patch-*.MPQ"), reverse=True))
        candidates.extend(sorted(locale_dir.glob("locale-*.MPQ"), reverse=True))
        candidates.extend(sorted(locale_dir.glob("*-locale-*.MPQ"), reverse=True))
        candidates.extend(sorted(locale_dir.glob("base-*.MPQ"), reverse=True))
    candidates.extend(sorted(data.glob("patch-*.MPQ"), reverse=True))
    candidates.extend(sorted(data.glob("patch.MPQ"), reverse=True))
    candidates.extend(sorted(data.glob("common*.MPQ"), reverse=True))
    return tuple(dict.fromkeys(candidates))


def load_button_texture_from_client(game_root: Path | str) -> Image.Image | None:
    """Busca la textura efectiva sin extraer ni modificar ningún MPQ."""
    for archive_path in _candidate_archives(Path(game_root)):
        try:
            with MPQArchive(archive_path) as archive:
                for internal_path in BUTTON_TEXTURE_PATHS:
                    payload = archive.read_file(internal_path)
                    if payload is not None:
                        return decode_button_texture(payload)
        except (OSError, MPQError, UnidentifiedImageError):
            continue
    return None
