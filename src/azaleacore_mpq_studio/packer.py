"""Construcción y planificación conservadora de parches MPQ."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .mpq import (
    CRYPT_TABLE,
    MPQArchive,
    MPQ_FILE_EXISTS,
    MPQ_FILE_SINGLE_UNIT,
    UINT32_MASK,
    mpq_hash,
)


MPQ_HEADER_SIZE = 32
PATCH_PATTERN = re.compile(r"^patch-(?P<suffix>[1-9A-Z])\.mpq$", re.IGNORECASE)
LOCALIZED_PATTERN = re.compile(
    r"^patch-(?P<locale>[a-z]{2}[A-Z]{2})-(?P<suffix>[1-9A-Z])\.mpq$",
    re.IGNORECASE,
)
LOCALE_DIR_PATTERN = re.compile(r"^[a-z]{2}[A-Z]{2}$")


class PackagingError(RuntimeError):
    """Error seguro y explicable durante el empaquetado."""


def _suffix_rank(suffix: str) -> int:
    """Ordena ranuras numéricas 1-9 y después alfabéticas A-Z."""
    normalized = suffix.upper()
    if normalized.isdigit():
        return int(normalized)
    return 9 + ord(normalized) - ord("A") + 1


def _next_suffix(suffix: str) -> str:
    normalized = suffix.upper()
    if normalized.isdigit() and int(normalized) < 9:
        return str(int(normalized) + 1)
    if normalized == "9":
        return "A"
    if "A" <= normalized < "Z":
        return chr(ord(normalized) + 1)
    raise PackagingError(
        f"{suffix} ya usa el último sufijo compatible (Z). "
        "No se generará automáticamente un sufijo posterior."
    )


@dataclass(frozen=True)
class PatchPlan:
    destination_dir: Path
    patch_name: str
    target: Path
    previous_patch: str | None
    message: str


def _encrypt_table(data: bytes, key: int) -> bytes:
    if len(data) % 4:
        raise PackagingError("La tabla MPQ no está alineada a cuatro bytes.")
    output = bytearray()
    seed1 = key & UINT32_MASK
    seed2 = 0xEEEEEEEE
    for offset in range(0, len(data), 4):
        decoded = struct.unpack_from("<I", data, offset)[0]
        seed2 = (seed2 + CRYPT_TABLE[0x400 + (seed1 & 0xFF)]) & UINT32_MASK
        encoded = (decoded ^ (seed1 + seed2)) & UINT32_MASK
        seed1 = (
            (((~seed1 & UINT32_MASK) << 21) + 0x11111111) & UINT32_MASK
        ) | (seed1 >> 11)
        seed2 = (
            decoded + seed2 + ((seed2 << 5) & UINT32_MASK) + 3
        ) & UINT32_MASK
        output.extend(struct.pack("<I", encoded))
    return bytes(output)


def _next_power_of_two(value: int) -> int:
    return 1 << (value - 1).bit_length()


def plan_patch(destination_dir: Path | str) -> PatchPlan:
    directory = Path(destination_dir).resolve()
    if not directory.is_dir():
        raise PackagingError("El directorio de destino no existe.")

    locale = directory.name if LOCALE_DIR_PATTERN.fullmatch(directory.name) else None
    entries: list[tuple[str, str]] = []
    for path in directory.iterdir():
        if not path.is_file():
            continue
        match = LOCALIZED_PATTERN.fullmatch(path.name) if locale else PATCH_PATTERN.fullmatch(path.name)
        if match and (not locale or match.group("locale").casefold() == locale.casefold()):
            entries.append((match.group("suffix").upper(), path.name))

    if entries:
        highest, previous = max(entries, key=lambda item: _suffix_rank(item[0]))
        suffix = _next_suffix(highest)
        prefix = f"patch-{locale}-" if locale else "patch-"
        name = f"{prefix}{suffix}.MPQ"
        message = (
            f"En este directorio el parche prioritario más reciente es {previous}. "
            f"Se generará {name}."
        )
    else:
        prefix = f"patch-{locale}-" if locale else "patch-"
        name = f"{prefix}1.MPQ"
        previous = None
        message = (
            "En este directorio no hay parches prioritarios compatibles. "
            f"Se creará {name} como primer parche."
        )

    target = directory / name
    if target.exists():
        raise PackagingError(f"El destino ya existe y no se sobrescribirá: {target}")
    return PatchPlan(directory, name, target, previous, message)


def _listfile_payload(files: Iterable[tuple[str, bytes]]) -> bytes:
    paths = sorted((name for name, _payload in files), key=str.casefold)
    return ("\r\n".join(paths) + "\r\n").encode("utf-8")


def build_mpq(
    files: Iterable[tuple[str, bytes]],
    destination: Path,
    *,
    include_listfile: bool = False,
) -> None:
    normalized = [(name.replace("/", "\\"), payload) for name, payload in files]
    if not normalized:
        raise PackagingError("No hay archivos seleccionados para empaquetar.")
    if len({name.casefold() for name, _ in normalized}) != len(normalized):
        raise PackagingError("Hay rutas internas duplicadas.")
    if include_listfile:
        if any(name.casefold() == "(listfile)" for name, _payload in normalized):
            raise PackagingError("La ruta interna (listfile) está reservada.")
        normalized.append(("(listfile)", _listfile_payload(normalized)))

    hash_count = _next_power_of_two(max(8, len(normalized) * 2))
    empty = (0xFFFFFFFF, 0xFFFFFFFF, 0xFFFF, 0xFFFF, 0xFFFFFFFF)
    hash_entries = [empty for _ in range(hash_count)]
    blocks: list[tuple[int, int, int, int]] = []
    data_area = bytearray()
    for block_index, (name, payload) in enumerate(normalized):
        file_pos = MPQ_HEADER_SIZE + len(data_area)
        data_area.extend(payload)
        blocks.append(
            (file_pos, len(payload), len(payload), MPQ_FILE_EXISTS | MPQ_FILE_SINGLE_UNIT)
        )
        slot = mpq_hash(name, 0) % hash_count
        for _ in range(hash_count):
            if hash_entries[slot][4] == 0xFFFFFFFF:
                hash_entries[slot] = (
                    mpq_hash(name, 1),
                    mpq_hash(name, 2),
                    0,
                    0,
                    block_index,
                )
                break
            slot = (slot + 1) % hash_count
        else:
            raise PackagingError("La tabla hash MPQ se quedó sin espacio.")

    plain_hashes = b"".join(struct.pack("<IIHHI", *entry) for entry in hash_entries)
    plain_blocks = b"".join(struct.pack("<4I", *entry) for entry in blocks)
    encrypted_hashes = _encrypt_table(plain_hashes, mpq_hash("(hash table)", 3))
    encrypted_blocks = _encrypt_table(plain_blocks, mpq_hash("(block table)", 3))
    hash_pos = MPQ_HEADER_SIZE + len(data_area)
    block_pos = hash_pos + len(encrypted_hashes)
    archive_size = block_pos + len(encrypted_blocks)
    header = struct.pack(
        "<4s2I2H4I",
        b"MPQ\x1a",
        MPQ_HEADER_SIZE,
        archive_size,
        0,
        3,
        hash_pos,
        block_pos,
        hash_count,
        len(blocks),
    )
    destination.write_bytes(header + data_area + encrypted_hashes + encrypted_blocks)


def create_and_install_patch(
    files: Iterable[tuple[str, Path]],
    plan: PatchPlan,
    *,
    include_listfile: bool = False,
) -> tuple[str, int]:
    selected = [(name, Path(path).read_bytes()) for name, path in files]
    if plan.target.exists():
        raise PackagingError(f"El destino ya existe: {plan.target}")

    temporary_root = Path(tempfile.mkdtemp(prefix="azaleacore-mpq-studio-"))
    temporary_mpq = temporary_root / plan.patch_name
    try:
        build_mpq(selected, temporary_mpq, include_listfile=include_listfile)
        with MPQArchive(temporary_mpq) as archive:
            expected_entries = len(selected) + int(include_listfile)
            if archive.active_entry_count != expected_entries:
                raise PackagingError("El MPQ reabierto no conserva todas las entradas.")
            for internal_path, expected in selected:
                actual = archive.read_file(internal_path)
                if actual != expected:
                    raise PackagingError(
                        f"La validación byte a byte falló para {internal_path}."
                    )
            if include_listfile:
                expected_listfile = _listfile_payload(selected)
                if archive.read_file("(listfile)") != expected_listfile:
                    raise PackagingError("El `(listfile)` generado no pasó la validación.")

        try:
            with plan.target.open("xb") as output, temporary_mpq.open("rb") as source:
                shutil.copyfileobj(source, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
        except Exception:
            plan.target.unlink(missing_ok=True)
            raise
        digest = hashlib.sha256(plan.target.read_bytes()).hexdigest().upper()
        return digest, plan.target.stat().st_size
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)
