"""Conversión conservadora de logotipos raster a BLP2 para WoW 3.3.5a."""

from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image, UnidentifiedImageError


class BLPConversionError(RuntimeError):
    """La imagen elegida no se puede usar como textura de login."""


def _is_power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def validate_blp(payload: bytes) -> tuple[int, int]:
    if len(payload) < 20 or payload[:4] not in (b"BLP1", b"BLP2"):
        raise BLPConversionError("El archivo no contiene una cabecera BLP1/BLP2 válida.")
    width, height = struct.unpack_from("<II", payload, 12)
    if not (_is_power_of_two(width) and _is_power_of_two(height)):
        raise BLPConversionError("El BLP debe tener dimensiones potencia de dos.")
    if width != height * 2:
        raise BLPConversionError("El logo BLP debe tener proporción 2:1, por ejemplo 512x256.")
    if width > 2048 or height > 1024:
        raise BLPConversionError("El logo BLP es demasiado grande para el cliente 3.3.5a.")
    return width, height


def _rgb565(red: int, green: int, blue: int) -> int:
    return ((red * 31 + 127) // 255 << 11) | ((green * 63 + 127) // 255 << 5) | (
        (blue * 31 + 127) // 255
    )


def _unpack_rgb565(value: int) -> tuple[int, int, int]:
    return (
        ((value >> 11) & 31) * 255 // 31,
        ((value >> 5) & 63) * 255 // 63,
        (value & 31) * 255 // 31,
    )


def _encode_dxt5_block(pixels: list[tuple[int, int, int, int]]) -> bytes:
    alphas = [pixel[3] for pixel in pixels]
    alpha0, alpha1 = max(alphas), min(alphas)
    if alpha0 == alpha1:
        alpha_palette = [alpha0] * 8
    else:
        alpha_palette = [alpha0, alpha1] + [
            ((6 - step) * alpha0 + (step + 1) * alpha1 + 3) // 7
            for step in range(6)
        ]
    alpha_bits = 0
    for index, alpha in enumerate(alphas):
        choice = min(range(8), key=lambda item: abs(alpha - alpha_palette[item]))
        alpha_bits |= choice << (index * 3)

    reds = [pixel[0] for pixel in pixels]
    greens = [pixel[1] for pixel in pixels]
    blues = [pixel[2] for pixel in pixels]
    color0 = _rgb565(max(reds), max(greens), max(blues))
    color1 = _rgb565(min(reds), min(greens), min(blues))
    if color0 < color1:
        color0, color1 = color1, color0
    first = _unpack_rgb565(color0)
    second = _unpack_rgb565(color1)
    colors = (
        first,
        second,
        tuple((2 * first[channel] + second[channel]) // 3 for channel in range(3)),
        tuple((first[channel] + 2 * second[channel]) // 3 for channel in range(3)),
    )
    color_bits = 0
    for index, (red, green, blue, _alpha) in enumerate(pixels):
        choice = min(
            range(4),
            key=lambda item: (
                (red - colors[item][0]) ** 2
                + (green - colors[item][1]) ** 2
                + (blue - colors[item][2]) ** 2
            ),
        )
        color_bits |= choice << (index * 2)
    return bytes((alpha0, alpha1)) + alpha_bits.to_bytes(6, "little") + struct.pack(
        "<HHI", color0, color1, color_bits
    )


def _encode_dxt5(image: Image.Image) -> bytes:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    output = bytearray()
    for top in range(0, rgba.height, 4):
        for left in range(0, rgba.width, 4):
            block = [
                pixels[min(left + x, rgba.width - 1), min(top + y, rgba.height - 1)]
                for y in range(4)
                for x in range(4)
            ]
            output.extend(_encode_dxt5_block(block))
    return bytes(output)


def rgba_to_blp2(image: Image.Image, width: int = 512, height: int = 256) -> bytes:
    """Encaja una imagen sin deformarla y genera BLP2 DXT5 con alfa y mipmaps."""
    source = image.convert("RGBA")
    source.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(source, ((width - source.width) // 2, (height - source.height) // 2))

    mip_payloads: list[bytes] = []
    mip_width, mip_height = width, height
    while True:
        mip = canvas.resize((mip_width, mip_height), Image.Resampling.LANCZOS)
        mip_payloads.append(_encode_dxt5(mip))
        if mip_width == 1 and mip_height == 1:
            break
        mip_width = max(1, mip_width // 2)
        mip_height = max(1, mip_height // 2)

    header_size = 148
    palette_padding = bytes(1024)
    data_offset = header_size + len(palette_padding)
    offsets = [0] * 16
    sizes = [0] * 16
    cursor = data_offset
    for index, payload in enumerate(mip_payloads[:16]):
        offsets[index] = cursor
        sizes[index] = len(payload)
        cursor += len(payload)
    header = bytearray()
    header.extend(b"BLP2")
    header.extend(struct.pack("<I", 1))
    header.extend(bytes((2, 8, 7, 1)))
    header.extend(struct.pack("<II", width, height))
    header.extend(struct.pack("<16I", *offsets))
    header.extend(struct.pack("<16I", *sizes))
    return bytes(header + palette_padding + b"".join(mip_payloads[:16]))


def prepare_login_logo(path: Path | str) -> bytes:
    source = Path(path)
    if source.suffix.casefold() == ".blp":
        payload = source.read_bytes()
        validate_blp(payload)
        return payload
    try:
        with Image.open(source) as image:
            payload = rgba_to_blp2(image)
    except (OSError, UnidentifiedImageError) as exc:
        raise BLPConversionError(f"No se pudo abrir la imagen: {exc}") from exc
    validate_blp(payload)
    return payload
