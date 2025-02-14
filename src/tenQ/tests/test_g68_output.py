# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0

from datetime import date
from enum import Enum
from typing import List
from unittest import TestCase

from tenQ.writer.g68 import (
    BetalingstekstLinje,
    DateField,
    EnumField,
    Field,
    FloatingFieldMixin,
    FlydendeEllerFast,
    Fortegnsmarkering,
    G68Transaction,
    G68TransactionWriter,
    Linjeløbenummer,
    Maskinnummer,
    NumericField,
    Organisationsenhed,
    Organisationstype,
    Posteringsdato,
    Posteringshenvisning,
    Registreringssted,
    Serializable,
    Snitfladetype,
    StringField,
    Transaktionstype,
    TransaktionstypeEnum,
    Udbetalingsbeløb,
    Udbetalingsberettiget,
    UdbetalingsberettigetIdentKode,
    UdbetalingsberettigetIdentKodeEnum,
    Udbetalingsdato,
    UdIdent,
    ZeroPaddedNumericField,
)


class TestSerializable(TestCase):
    def setUp(self):
        super().setUp()
        self.instance = Serializable()

    def test_serialized_value(self):
        with self.assertRaises(NotImplementedError):
            self.instance.serialized_value

    def test_repr(self):
        with self.assertRaises(NotImplementedError):
            repr(self.instance)


class TestField(TestCase):
    class FieldImpl(Field):
        datatype = list
        length = 3

    def test_length_is_checked(self):
        # Instantiating a `FieldImpl` with a list of length 4 should fail
        with self.assertRaises(ValueError):
            self.FieldImpl([1, 2, 3, 4])

    def test_from_str(self):
        instance = self.FieldImpl("abc")
        self.assertEqual(instance.val, ["a", "b", "c"])

    def test_parse(self):
        line = "000G68"
        reg, interface_type = Field.parse(line, Registreringssted, Snitfladetype)
        self.assertIsInstance(reg, Registreringssted)
        self.assertIsInstance(interface_type, Snitfladetype)


class TestNumericField(TestCase):
    class NumericFieldImpl(NumericField):
        length = 100

    def setUp(self):
        super().setUp()
        self.instance = self.NumericFieldImpl(42)

    def test_length_is_checked(self):
        with self.assertRaises(ValueError):
            self.NumericFieldImpl(int("1" * 200))

    def test_serializes_to_string(self):
        self.assertEqual(self.instance.serialized_value, "42")

    def test_repr(self):
        self.assertEqual(repr(self.instance), "<NumericFieldImpl: 42>")


class TestZeroPaddedNumericField(TestCase):
    class ZeroPaddedNumericFieldImpl(ZeroPaddedNumericField):
        length = 4

    def setUp(self):
        super().setUp()
        self.instance = self.ZeroPaddedNumericFieldImpl(42)

    def test_serializes_to_zero_padded_string(self):
        self.assertEqual(self.instance.serialized_value, "0042")

    def test_repr(self):
        self.assertEqual(
            repr(self.instance),
            "<ZeroPaddedNumericFieldImpl: 0042>",
        )


class TestStringField(TestCase):
    class StringFieldImpl(StringField):
        length = 100

    def setUp(self):
        super().setUp()
        self.instance = self.StringFieldImpl("abc")

    def test_illegal_characters_are_checked(self):
        for illegal in ("&", "!", "\\"):
            with self.subTest(f"illegal={illegal!r}"):
                with self.assertRaises(ValueError):
                    self.StringFieldImpl(illegal)

    def test_serializes_to_string(self):
        self.assertEqual(self.instance.serialized_value, "abc")

    def test_repr(self):
        self.assertEqual(
            repr(self.instance),
            "<StringFieldImpl: abc>",
        )


class TestDateField(TestCase):
    class DateFieldImpl(DateField):
        pass

    def setUp(self):
        super().setUp()
        self.instance = self.DateFieldImpl(date(2020, 2, 29))

    def test_val_arg_is_checked(self):
        with self.assertRaises(TypeError):
            self.DateFieldImpl(42)  # type: ignore[arg-type]

    def test_serializes_to_string(self):
        self.assertEqual(self.instance.serialized_value, "20200229")

    def test_repr(self):
        self.assertEqual(repr(self.instance), "<DateFieldImpl: 20200229>")

    def test_from_str(self):
        instance = self.DateFieldImpl.from_str("20200229")
        self.assertEqual(instance.val, date(2020, 2, 29))


class EnumA(Enum):
    Option1 = 1
    Option2 = 2


class TestEnumField(TestCase):
    class EnumFieldImpl(EnumField):
        datatype = EnumA
        length = 4

    def setUp(self):
        self.instance = self.EnumFieldImpl(EnumA.Option2)

    def test_instantiation_from_numeric_value(self):
        instance_2 = self.EnumFieldImpl(EnumA.Option2.value)
        self.assertEqual(self.instance.val, instance_2.val)

    def test_serializes_to_zero_padded_string(self):
        self.assertEqual(self.instance.serialized_value, "0002")

    def test_repr(self):
        self.assertEqual(repr(self.instance), "<EnumFieldImpl: 0002>")

    def test_from_str(self):
        instance = self.EnumFieldImpl.from_str("0002")
        self.assertEqual(instance.val, EnumA.Option2.value)


class TestFloatingFieldMixin(TestCase):
    def test_serializes_to_string_with_id(self):
        class Field(FloatingFieldMixin, ZeroPaddedNumericField):
            id = 99
            length = 4

        instance = Field(42)

        # Field serializes to `&NNMMMM` where `NN` is the two-digit field ID,
        # and `MMMM` is the (zero padded) field value.
        self.assertEqual(instance.serialized_value, "&990042")

    def test_cannot_register_subclasses_without_id(self):
        with self.assertRaises(ValueError):

            class Field(FloatingFieldMixin):
                pass

    def test_cannot_register_subclasses_with_duplicated_id(self):
        class FieldA(FloatingFieldMixin):
            id = 42

        with self.assertRaises(KeyError):

            class FieldB(FloatingFieldMixin):
                id = 42

    def test_validate_required_fields(self):
        with self.assertRaises(ValueError):
            FloatingFieldMixin.validate_required_fields([Organisationsenhed(0)])

    def test_parse(self):
        line = "000G68&020001&1011&40Betalingstekstlinje"
        org, ident, text_line = FloatingFieldMixin.parse(line)
        self._assert_type_val(org, Organisationsenhed, 1)
        self._assert_type_val(
            ident,
            UdbetalingsberettigetIdentKode,
            UdbetalingsberettigetIdentKodeEnum.CVR.value,
        )
        self._assert_type_val(
            text_line,
            BetalingstekstLinje,
            "Betalingstekstlinje",
        )

    def _assert_type_val(self, obj, expected_type, expected_value):
        self.assertIsInstance(obj, expected_type)
        self.assertEqual(obj.val, expected_value)


class TestSnitfladetype(TestCase):
    def test_accepts_valid_value(self):
        instance = Snitfladetype("G68")
        self.assertEqual(instance.val, instance._constant)

    def test_raises_on_invalid_value(self):
        with self.assertRaises(AssertionError):
            Snitfladetype("")


class TestUdbetalingsbeløb(TestCase):
    def test_val_arg_is_assumed_kr(self):
        instance = Udbetalingsbeløb(42)
        self.assertEqual(instance.val, 4200)

    def test_val_arg_is_without_sign(self):
        instance = Udbetalingsbeløb(-42)
        self.assertEqual(instance.val, 4200)


class TestFortegnsmarkering(TestCase):
    def test_val_arg_is_checked(self):
        with self.assertRaises(ValueError):
            Fortegnsmarkering("")


class TestPosteringshenvisning(TestCase):
    def test_serialized_value(self):
        instance = Posteringshenvisning(
            Posteringsdato(date(2020, 1, 1)),
            Maskinnummer(42),
            Linjeløbenummer(100),
        )
        self.assertEqual(
            instance.serialized_value,
            "&16202001010004200100",
        )

    def test_from_str(self):
        val = "202002290005000100"
        instance = Posteringshenvisning.from_str(val)
        self.assertEqual(instance.val, val)


class TestBetalingstekstLinje(TestCase):
    def test_id_arg_is_checked(self):
        cls = BetalingstekstLinje
        for id in (cls._min_id - 1, cls._max_id + 1):
            with self.subTest(f"id={id!r}"):
                with self.assertRaises(ValueError):
                    cls("val", id)

    def test_list_from_text(self):
        cls = BetalingstekstLinje
        instances: List[BetalingstekstLinje] = cls.list_from_text(
            # 35 lines of 81 characters each, separated by line breaks
            "\n".join(["a" * 81] * 35)
        )
        # Assert that a maximum of 35 lines are produced
        self.assertEqual(len(instances), (cls._max_id - cls._min_id))
        # Assert that each line is no longer than 81 characters
        self.assertTrue(all(len(instance.val) <= cls.length for instance in instances))
        # Assert that each line has a sequential ID, beginning at 40
        self.assertEqual(
            [instance.id for instance in instances],
            list(range(cls._min_id, cls._max_id)),
        )


class TestG8TransactionWriter(TestCase):
    maxDiff = None

    def setUp(self):
        super().setUp()
        self.writer = G68TransactionWriter(0, 0)

    def test_serialize_transaction(self):
        transaction_serialized = self.writer.serialize_transaction(
            TransaktionstypeEnum.AndenDestinationTilladt,
            UdbetalingsberettigetIdentKodeEnum.CPR,
            "0101012222",
            1234,
            date(2020, 1, 27),
            date(2020, 2, 1),
            "012345678",  # fakturanummer
            "Denne måneds udbetaling af beskæftigelsestilskud\n"
            "sker ud fra en forventet samlet årsindkomst på 324.178 kr.\n"
            "og er baseret på din A- og B-indkomst i 2023.",
        )
        self.assertEqual(
            transaction_serialized,
            "000G6800001011&020000&0300&07000000000000000000&0800000123400&09+"
            "&1002&1100000101012222&1220200127&16202002010000000001"
            "&17012345678"  # serialized fakturanummer
            "&40Denne måneds udbetaling af beskæftigelsestilskud"
            "&41sker ud fra en forventet samlet årsindkomst på 324.178 kr."
            "&42og er baseret på din A- og B-indkomst i 2023.",
        )


class TestG68Transaction(TestCase):
    maxDiff = None

    def test_parse(self):
        line = (
            "000G6800001011&020000&0300&07000000000000000000&0800000123400&09+"
            "&1002&1100000101012222&1220200127&16202002010000000001"
            "&40Denne måneds udbetaling af beskæftigelsestilskud sker ud fra en forventet samlet "
            "&41årsindkomst på 324.178 kr. og er baseret på din A- og B-indkomst i 2023."
        )
        fields = list(G68Transaction.parse(line))
        self.assertEqual(
            [type(field) for field in fields],
            [
                Registreringssted,
                Snitfladetype,
                Linjeløbenummer,
                Transaktionstype,
                FlydendeEllerFast,
                Organisationsenhed,
                Organisationstype,
                UdIdent,
                Udbetalingsbeløb,
                Fortegnsmarkering,
                UdbetalingsberettigetIdentKode,
                Udbetalingsberettiget,
                Udbetalingsdato,
                Posteringshenvisning,
                BetalingstekstLinje,
                BetalingstekstLinje,
            ],
        )
