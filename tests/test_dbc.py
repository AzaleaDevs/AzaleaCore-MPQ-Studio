import struct
import unittest

from azaleacore_mpq_studio.dbc import DBCError, parse_dbc


def build_dbc(records: list[tuple[int, ...]], strings: bytes = b"\0") -> bytes:
    field_count = len(records[0]) if records else 2
    record_data = b"".join(struct.pack(f"<{field_count}I", *row) for row in records)
    return (
        struct.pack(
            "<4s4I",
            b"WDBC",
            len(records),
            field_count,
            field_count * 4,
            len(strings),
        )
        + record_data
        + strings
    )


class DBCReaderTests(unittest.TestCase):
    def test_reads_header_records_and_strings(self) -> None:
        dbc = parse_dbc(build_dbc([(7, 1), (8, 6)], b"\0Hola\0Mundo\0"))

        self.assertEqual(dbc.header.record_count, 2)
        self.assertEqual(dbc.header.field_count, 2)
        self.assertEqual(dbc.record(1), (8, 6))
        self.assertEqual(dbc.string_at(1), "Hola")
        self.assertEqual(dbc.display_value(6), '6 · "Mundo"')

    def test_does_not_treat_the_middle_of_a_string_as_an_offset(self) -> None:
        dbc = parse_dbc(build_dbc([(2, 0)], b"\0Hola\0"))

        self.assertIsNone(dbc.string_at(2))
        self.assertEqual(dbc.display_value(2), "2")

    def test_rejects_wrong_magic_and_truncated_payloads(self) -> None:
        with self.assertRaisesRegex(DBCError, "WDBC"):
            parse_dbc(b"WDB2" + b"\0" * 16)
        with self.assertRaisesRegex(DBCError, "truncado"):
            parse_dbc(struct.pack("<4s4I", b"WDBC", 1, 2, 8, 1))

    def test_rejects_inconsistent_record_size(self) -> None:
        payload = struct.pack("<4s4I", b"WDBC", 0, 3, 8, 0)

        with self.assertRaisesRegex(DBCError, "tamaño de registro"):
            parse_dbc(payload)

    def test_replaces_numeric_value_and_serializes(self) -> None:
        original = parse_dbc(build_dbc([(7, 1)], b"\0Hola\0"))

        modified = original.replace_value(0, 0, 99)
        reopened = parse_dbc(modified.to_bytes())

        self.assertEqual(original.record(0), (7, 1))
        self.assertEqual(reopened.record(0), (99, 1))

    def test_replaces_field_with_new_string(self) -> None:
        original = parse_dbc(build_dbc([(7, 1)], b"\0Hola\0"))

        modified = original.replace_with_string(0, 1, "Azeroth")
        reopened = parse_dbc(modified.to_bytes())

        new_offset = reopened.record(0)[1]
        self.assertEqual(reopened.string_at(new_offset), "Azeroth")
        self.assertEqual(reopened.header.string_block_size, len(b"\0Hola\0Azeroth\0"))


if __name__ == "__main__":
    unittest.main()
