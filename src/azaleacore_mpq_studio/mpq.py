"""Lector MPQ mínimo y estrictamente de solo lectura."""

from __future__ import annotations

import bz2
import math
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


MPQ_FILE_IMPLODE = 0x00000100
MPQ_FILE_COMPRESS = 0x00000200
MPQ_FILE_ENCRYPTED = 0x00010000
MPQ_FILE_FIX_KEY = 0x00020000
MPQ_FILE_PATCH_FILE = 0x00100000
MPQ_FILE_SINGLE_UNIT = 0x01000000
MPQ_FILE_DELETE_MARKER = 0x02000000
MPQ_FILE_SECTOR_CRC = 0x04000000
MPQ_FILE_EXISTS = 0x80000000
UINT32_MASK = 0xFFFFFFFF
EMPTY_HASH = 0xFFFFFFFF
DELETED_HASH = 0xFFFFFFFE


class MPQError(RuntimeError):
    """Error legible durante la apertura o lectura de un MPQ."""


@dataclass(frozen=True)
class MPQFile:
    path: str
    size: int
    packed_size: int
    flags: int


@dataclass(frozen=True)
class MPQInventory:
    files: tuple[MPQFile, ...]
    active_entries: int
    unknown_entries: int
    has_listfile: bool


def load_listfile_paths(path: Path | str) -> tuple[str, ...]:
    """Lee rutas de un listfile externo y las normaliza para su búsqueda MPQ."""
    source = Path(path)
    payload = source.read_bytes()
    if payload.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = payload.decode("utf-16")
    else:
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = payload.decode("cp1252")
            except UnicodeDecodeError:
                text = payload.decode("latin-1")

    paths: dict[str, str] = {}
    for line in text.splitlines():
        internal_path = line.strip().strip("\x00").replace("/", "\\")
        if internal_path:
            paths.setdefault(internal_path.casefold(), internal_path)
    return tuple(paths.values())


def _build_crypt_table() -> tuple[int, ...]:
    table = [0] * 0x500
    seed = 0x00100001
    for index1 in range(0x100):
        for index2 in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            high = (seed & 0xFFFF) << 16
            seed = (seed * 125 + 3) % 0x2AAAAB
            table[index1 + index2 * 0x100] = high | (seed & 0xFFFF)
    return tuple(table)


CRYPT_TABLE = _build_crypt_table()


def mpq_hash(name: str, hash_type: int) -> int:
    seed1 = 0x7FED7FED
    seed2 = 0xEEEEEEEE
    try:
        normalized = name.replace("/", "\\").upper().encode("latin-1")
    except UnicodeEncodeError as exc:
        raise MPQError(f"La ruta no es compatible con el nombre MPQ: {name}") from exc
    for value in normalized:
        seed1 = (CRYPT_TABLE[(hash_type << 8) + value] ^ (seed1 + seed2)) & UINT32_MASK
        seed2 = (
            value + seed1 + seed2 + ((seed2 << 5) & UINT32_MASK) + 3
        ) & UINT32_MASK
    return seed1


def _decrypt_table(data: bytes, key: int) -> bytes:
    if len(data) % 4:
        raise MPQError("La tabla MPQ cifrada no está alineada a cuatro bytes.")
    output = bytearray()
    seed1 = key & UINT32_MASK
    seed2 = 0xEEEEEEEE
    for offset in range(0, len(data), 4):
        value = struct.unpack_from("<I", data, offset)[0]
        seed2 = (seed2 + CRYPT_TABLE[0x400 + (seed1 & 0xFF)]) & UINT32_MASK
        decoded = (value ^ (seed1 + seed2)) & UINT32_MASK
        seed1 = (
            (((~seed1 & UINT32_MASK) << 21) + 0x11111111) & UINT32_MASK
        ) | (seed1 >> 11)
        seed2 = (
            decoded + seed2 + ((seed2 << 5) & UINT32_MASK) + 3
        ) & UINT32_MASK
        output.extend(struct.pack("<I", decoded))
    return bytes(output)


def _decompress_block(block: bytes, expected_size: int) -> bytes:
    if len(block) == expected_size:
        return block
    if not block:
        raise MPQError("Se encontró un sector MPQ comprimido vacío.")
    method, payload = block[0], block[1:]
    if method == 0:
        return payload
    if method == 0x02:
        return zlib.decompress(payload)
    if method == 0x10:
        return bz2.decompress(payload)
    raise MPQError(f"Compresión MPQ todavía no soportada: 0x{method:02X}.")


class MPQArchive:
    """Abre un MPQ existente sin solicitar nunca permisos de escritura."""

    def __init__(self, path: Path | str):
        self.path = Path(path).resolve()
        self._handle = None
        try:
            self._handle = self.path.open("rb")
            if self._handle.read(4) != b"MPQ\x1a":
                raise MPQError("El archivo no comienza con una cabecera MPQ válida.")
            header_data = self._handle.read(28)
            if len(header_data) != 28:
                raise MPQError("La cabecera MPQ está incompleta.")
            header = struct.unpack("<2I2H4I", header_data)
            self.format_version = header[2]
            self.sector_size = 512 << header[3]
            hash_pos, block_pos = header[4], header[5]
            hash_count, block_count = header[6], header[7]
            if not hash_count or not block_count:
                raise MPQError("El MPQ no contiene tablas utilizables.")

            self._handle.seek(hash_pos)
            raw_hashes = self._handle.read(hash_count * 16)
            if len(raw_hashes) != hash_count * 16:
                raise MPQError("La tabla hash del MPQ está incompleta.")
            hashes = _decrypt_table(raw_hashes, mpq_hash("(hash table)", 3))
            self.hash_table = tuple(
                struct.unpack_from("<IIHHI", hashes, index * 16)
                for index in range(hash_count)
            )

            self._handle.seek(block_pos)
            raw_blocks = self._handle.read(block_count * 16)
            if len(raw_blocks) != block_count * 16:
                raise MPQError("La tabla de bloques del MPQ está incompleta.")
            blocks = _decrypt_table(raw_blocks, mpq_hash("(block table)", 3))
            self.block_table = tuple(
                struct.unpack_from("<4I", blocks, index * 16)
                for index in range(block_count)
            )
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "MPQArchive":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _find_block_index(self, internal_path: str) -> int | None:
        count = len(self.hash_table)
        start = mpq_hash(internal_path, 0) % count
        name_a = mpq_hash(internal_path, 1)
        name_b = mpq_hash(internal_path, 2)
        candidates: list[tuple[int, int]] = []
        for step in range(count):
            entry = self.hash_table[(start + step) % count]
            if entry[4] == EMPTY_HASH:
                break
            if (
                entry[0] == name_a
                and entry[1] == name_b
                and entry[4] < len(self.block_table)
            ):
                candidates.append((0 if entry[2] == 0 else 1, entry[4]))
        return min(candidates)[1] if candidates else None

    def _active_block_indices(self) -> set[int]:
        return {
            entry[4]
            for entry in self.hash_table
            if entry[4] not in (EMPTY_HASH, DELETED_HASH)
            and entry[4] < len(self.block_table)
            and self.block_table[entry[4]][3] & MPQ_FILE_EXISTS
        }

    @property
    def active_entry_count(self) -> int:
        """Número de bloques activos sin necesidad de conocer sus nombres."""
        return len(self._active_block_indices())

    def contains(self, internal_path: str) -> bool:
        return self._find_block_index(internal_path) is not None

    def file_info(self, internal_path: str) -> MPQFile | None:
        block_index = self._find_block_index(internal_path)
        if block_index is None:
            return None
        _, packed_size, size, flags = self.block_table[block_index]
        if not flags & MPQ_FILE_EXISTS:
            return None
        return MPQFile(internal_path.replace("/", "\\"), size, packed_size, flags)

    def read_file(self, internal_path: str) -> bytes | None:
        block_index = self._find_block_index(internal_path)
        if block_index is None:
            return None
        file_pos, packed_size, size, flags = self.block_table[block_index]
        if not flags & MPQ_FILE_EXISTS:
            return None
        if flags & MPQ_FILE_ENCRYPTED:
            raise MPQError(f"El archivo está cifrado: {internal_path}")
        if flags & MPQ_FILE_PATCH_FILE:
            raise MPQError(f"El archivo es un delta MPQ: {internal_path}")
        if self._handle is None:
            raise MPQError("El MPQ ya está cerrado.")

        self._handle.seek(file_pos)
        raw = self._handle.read(packed_size)
        if len(raw) != packed_size:
            raise MPQError(f"Lectura incompleta: {internal_path}")
        compressed = flags & (MPQ_FILE_COMPRESS | MPQ_FILE_IMPLODE)
        if flags & MPQ_FILE_SINGLE_UNIT:
            result = (
                _decompress_block(raw, size)
                if compressed and packed_size < size
                else raw
            )
            return result[:size]
        if not compressed and packed_size >= size:
            return raw[:size]

        sector_count = math.ceil(size / self.sector_size)
        table_size = (sector_count + 1) * 4
        if len(raw) < table_size:
            raise MPQError(f"Tabla de sectores inválida: {internal_path}")
        offsets = struct.unpack_from(f"<{sector_count + 1}I", raw)
        output = bytearray()
        for index in range(sector_count):
            start, end = offsets[index], offsets[index + 1]
            if start > end or end > len(raw):
                raise MPQError(f"Offsets de sector inválidos: {internal_path}")
            sector = raw[start:end]
            expected = min(self.sector_size, size - len(output))
            output.extend(
                _decompress_block(sector, expected)
                if len(sector) < expected
                else sector
            )
        return bytes(output[:size])

    def _listfile_paths(self) -> set[str]:
        payload = self.read_file("(listfile)")
        if payload is None:
            return set()
        text = ""
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = payload.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        return {
            line.strip().replace("/", "\\")
            for line in text.splitlines()
            if line.strip()
        }

    def inventory(self, known_paths: Iterable[str] = ()) -> MPQInventory:
        listfile_paths = self._listfile_paths()
        candidates = listfile_paths | {
            path.strip().replace("/", "\\")
            for path in known_paths
            if path.strip()
        }
        identified: dict[int, MPQFile] = {}
        for path in sorted(candidates, key=str.casefold):
            block_index = self._find_block_index(path)
            info = self.file_info(path)
            if block_index is not None and info is not None:
                identified.setdefault(block_index, info)
        active = self._active_block_indices()
        return MPQInventory(
            files=tuple(sorted(identified.values(), key=lambda item: item.path.casefold())),
            active_entries=len(active),
            unknown_entries=len(active - identified.keys()),
            has_listfile=bool(listfile_paths),
        )
