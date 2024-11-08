# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0
import re
import unittest
from datetime import date
from decimal import Decimal

from tenQ.writer import G69TransactionWriter


class OutputTest(unittest.TestCase):

    minimum_required = {
        "post_type": "NOR",
        "kaldenavn": "test",
        "maskinnr": 123,
        "eks_løbenr": 1,
        "post_dato": date(2022, 3, 11),
        "kontonr": 1234005678,
        "beløb": Decimal(123.45),
        "deb_kred": "D",
    }

    def setUp(self):
        self.transaction_writer = G69TransactionWriter(12, 34)

    def test_writer_successful(self):
        prismeG69_content_1 = self.transaction_writer.serialize_transaction(
            post_type="NOR",
            kaldenavn="test",
            maskinnr=123,
            eks_løbenr=1,
            post_dato=date(2022, 3, 11),
            kontonr=123456789012345,
            beløb=Decimal(123.45),
            deb_kred="D",
            is_cvr=True,
            ydelse_modtager=12345678,
        )
        prismeG69_content_2 = self.transaction_writer.serialize_transaction(
            post_type="NOR",
            kaldenavn="test",
            maskinnr=123,
            eks_løbenr=1,
            post_dato=date(2022, 3, 11),
            kontonr=123456789012345,
            beløb=Decimal(123.45),
            deb_kred="K",
            is_cvr=True,
            ydelse_modtager=12345678,
        )
        self.assertEqual(
            prismeG69_content_1,
            "012G6900001003401NORFLYD"
            "&101test"
            "&10300123"
            "&1040000001"
            "&11020220311"
            "&111123456789012345"
            "&112000000012345 "
            "&113D"
            "&13203"
            "&13312345678",
        )
        self.assertEqual(
            prismeG69_content_2,
            "012G6900002003401NORFLYD"
            "&101test"
            "&10300123"
            "&1040000001"
            "&11020220311"
            "&111123456789012345"
            "&112000000012345 "
            "&113K"
            "&13203"
            "&13312345678",
        )

    def test_writer_invalid_input(self):
        defaults = {
            "kaldenavn": "test",
        }
        invalid = ["test", 123, date(2022, 3, 11), Decimal("100.25")]
        for key, value in defaults.items():
            for invalid_value in invalid:
                if type(invalid_value) != type(value):  # noqa: E721
                    with self.assertRaises(ValueError):
                        self.transaction_writer.serialize_transaction(
                            **{
                                "post_type": "NOR",
                                **defaults,
                                key: invalid_value,
                            }
                        )

    def test_writer_required_together(self):
        data = (
            {"ydelse_modtager_nrkode": 3, "ydelse_modtager": 3},
            {"rekvisitionsnr": 3, "delleverance": "N"},
            {"projekt_nr": "3", "projekt_art": "test", "antal": 10},
        )
        for d in data:
            for key, value in d.items():
                with self.assertRaises(ValueError):
                    self.transaction_writer.serialize_transaction(
                        **{**self.minimum_required, key: value}
                    )
            self.transaction_writer.serialize_transaction(
                **{
                    **self.minimum_required,
                    **d,
                }
            )

    def test_writer_mutex(self):
        data = (
            (
                {"emne": "test", "notat_long": "test"},
                {"bilag_arkiv_nr": "test", "kontering_fakturapulje": "test"},
            ),
        )
        for subject, mutex in data:
            for key, value in mutex.items():
                with self.assertRaises(ValueError):
                    self.transaction_writer.serialize_transaction(
                        **{**self.minimum_required, **subject, key: value}
                    )
            self.transaction_writer.serialize_transaction(
                **{**self.minimum_required, **subject}
            )

    def test_field_111_allows_values_longer_than_15_digits(self):
        # Act: pass a 40-digit value as `kontonr` (= field 111)
        transaction = self.transaction_writer.serialize_transaction(
            **{**self.minimum_required, **{"kontonr": int("1" * 50)}}
        )
        # Assert: field 111 is not padded
        self.assertEqual(
            self._get_floating_field_value(transaction, 111),
            "1" * 50,
        )

    def test_field_111_pads_shorter_values_to_15_characters(self):
        # Act: pass a 10-digit value as `kontonr` (= field 111)
        transaction = self.transaction_writer.serialize_transaction(
            **{**self.minimum_required, **{"kontonr": int("1" * 10)}}
        )
        # Assert: field 111 is padded out to 15 characters
        self.assertEqual(
            self._get_floating_field_value(transaction, 111),
            "000001111111111",
        )

    def _get_floating_field_value(self, transaction: str, field: int) -> str:
        match = re.match(rf".*&{field}(?P<val>\d+)&.*", transaction)
        self.assertIsNotNone(match)
        return match.groupdict()["val"]
