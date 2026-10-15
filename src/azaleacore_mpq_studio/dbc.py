"""Lector de solo lectura para tablas DBC de World of Warcraft 3.3.5a."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass


DBC_MAGIC = b"WDBC"
DBC_HEADER_SIZE = 20


class DBCError(ValueError):
    """Describe un DBC inválido o no compatible."""


@dataclass(frozen=True)
class DBCHeader:
    record_count: int
    field_count: int
    record_size: int
    string_block_size: int


@dataclass(frozen=True)
class DBCFile:
    """Tabla DBC validada cuyos registros se decodifican bajo demanda."""

    header: DBCHeader
    records: bytes
    strings: bytes

    def record(self, index: int) -> tuple[int, ...]:
        if not 0 <= index < self.header.record_count:
            raise IndexError(index)
        offset = index * self.header.record_size
        return struct.unpack_from(
            f"<{self.header.field_count}I", self.records, offset
        )

    def string_at(self, offset: int) -> str | None:
        """Devuelve una cadena solo si el valor señala su byte inicial."""
        if offset <= 0 or offset >= len(self.strings):
            return None
        if offset > 0 and self.strings[offset - 1] != 0:
            return None
        end = self.strings.find(b"\0", offset)
        if end < 0 or end == offset:
            return None
        payload = self.strings[offset:end]
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            text = payload.decode("cp1252", errors="replace")
        if not text.isprintable():
            return None
        return text

    def display_value(self, value: int) -> str:
        text = self.string_at(value)
        if text is not None:
            escaped = text.replace("\n", "\\n").replace("\r", "\\r")
            if len(escaped) > 80:
                escaped = escaped[:77] + "…"
            return f'{value} · "{escaped}"'
        return str(value)

    def replace_value(self, record_index: int, field_index: int, value: int) -> "DBCFile":
        """Devuelve una copia con un uint32 sustituido."""
        if not 0 <= record_index < self.header.record_count:
            raise IndexError(record_index)
        if not 0 <= field_index < self.header.field_count:
            raise IndexError(field_index)
        if not 0 <= value <= 0xFFFFFFFF:
            raise ValueError("El valor debe estar entre 0 y 4294967295.")
        records = bytearray(self.records)
        offset = record_index * self.header.record_size + field_index * 4
        struct.pack_into("<I", records, offset, value)
        return DBCFile(self.header, bytes(records), self.strings)

    def replace_with_string(
        self, record_index: int, field_index: int, text: str
    ) -> "DBCFile":
        """Añade texto al bloque de cadenas y actualiza el offset del campo."""
        if not text:
            return self.replace_value(record_index, field_index, 0)
        encoded = text.encode("utf-8")
        if b"\0" in encoded:
            raise ValueError("El texto no puede contener caracteres nulos.")
        offset = len(self.strings)
        strings = self.strings + encoded + b"\0"
        updated = self.replace_value(record_index, field_index, offset)
        header = DBCHeader(
            updated.header.record_count,
            updated.header.field_count,
            updated.header.record_size,
            len(strings),
        )
        return DBCFile(header, updated.records, strings)

    def to_bytes(self) -> bytes:
        """Serializa la tabla conservando el formato WDBC clásico."""
        return struct.pack(
            "<4s4I",
            DBC_MAGIC,
            self.header.record_count,
            self.header.field_count,
            self.header.record_size,
            len(self.strings),
        ) + self.records + self.strings

    @property
    def page_count(self) -> int:
        return max(1, math.ceil(self.header.record_count / 250))


def parse_dbc(payload: bytes) -> DBCFile:
    """Valida y abre en memoria un DBC WDBC clásico."""
    if len(payload) < DBC_HEADER_SIZE:
        raise DBCError("La cabecera DBC está incompleta.")
    magic, record_count, field_count, record_size, string_block_size = (
        struct.unpack_from("<4s4I", payload)
    )
    if magic != DBC_MAGIC:
        raise DBCError("El archivo no comienza con la firma WDBC.")
    if field_count == 0:
        raise DBCError("El DBC no contiene campos.")
    if record_size != field_count * 4:
        raise DBCError(
            "El tamaño de registro DBC no coincide con el número de campos."
        )
    records_size = record_count * record_size
    expected_size = DBC_HEADER_SIZE + records_size + string_block_size
    if len(payload) < expected_size:
        raise DBCError(
            f"El DBC está truncado: esperaba {expected_size} bytes y contiene "
            f"{len(payload)}."
        )
    records_end = DBC_HEADER_SIZE + records_size
    return DBCFile(
        header=DBCHeader(record_count, field_count, record_size, string_block_size),
        records=payload[DBC_HEADER_SIZE:records_end],
        strings=payload[records_end:expected_size],
    )
