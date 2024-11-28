# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0
from datetime import date, datetime
from enum import Enum
from operator import attrgetter
from textwrap import wrap
from typing import Generator, List, Optional, Type, Union

_not_implemented = NotImplementedError("must be implemented by subclass")


class Serializable:
    """Implements a shared "serializable" interface used by `Field` and
    `G68Transaction`.
    """

    @property
    def serialized_value(self) -> str:
        raise _not_implemented

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.serialized_value}>"


class Field(Serializable):
    """Base class for all fields on a G68 transaction."""

    # These class attributes are expected to be overridden by subclasses
    datatype: Union[Type, NotImplementedError] = _not_implemented
    length: Union[int, NotImplementedError] = _not_implemented

    def __init__(self, val):
        assert isinstance(self.datatype, type)
        assert isinstance(self.length, int)
        if len(val) > self.length:
            raise ValueError(f"{val}: length must be {self.length} or shorter")
        self._val = self.datatype(val)

    @property
    def val(self):
        return self._val

    @classmethod
    def from_str(cls, val: str) -> "Field":
        assert isinstance(cls.datatype, type)
        return cls(cls.datatype(val))

    @classmethod
    def parse(cls, line: str, *expected_fields: Type["Field"]) -> Generator:
        start = 0
        end = 0
        for field in expected_fields:
            assert isinstance(field.length, int)
            end += field.length
            val = line[start:end]
            yield field.from_str(val)
            start += field.length


class NumericField(Field):
    """Represents a numeric field on a G68 transaction."""

    datatype: Type[int] = int

    def __init__(self, val: int):
        assert isinstance(self.length, int)
        if len(str(val)) > self.length:
            raise ValueError(f"{val}: must be {self.length} digits or shorter")
        self._val = self.datatype(val)

    @property
    def serialized_value(self) -> str:
        return str(self._val)


class ZeroPaddedNumericField(NumericField):
    """Represents a zero-padded numeric field on a G68 transaction."""

    @property
    def serialized_value(self) -> str:
        assert isinstance(self.length, int)
        return str(self._val).zfill(self.length)


class StringField(Field):
    """Represents a text field on a G68 transaction."""

    datatype = str

    _illegal = set("&!\\")

    def __init__(self, val: str):
        illegal: set = set(val) & (set(self._illegal))
        if illegal != set():
            raise ValueError(f"{val!r} contains illegal characters: {illegal}")
        super().__init__(val)

    @property
    def serialized_value(self) -> str:
        return self._val


class DateField(Field):
    """Represents a date field on a G68 transaction."""

    datatype = date
    length = 8  # length of serialized output

    _format = "%Y%m%d"

    def __init__(self, val: date):
        if not isinstance(val, date):
            raise TypeError(f"{val!r} is not a `date` instance")
        self._val = val
        self._formatted_val = val.strftime(self._format)
        assert len(self._formatted_val) == self.length

    @property
    def serialized_value(self) -> str:
        return self._formatted_val

    @classmethod
    def from_str(cls, val: str) -> "DateField":
        return cls(datetime.strptime(val, cls._format).date())


class EnumField(ZeroPaddedNumericField):
    """Represents an enum field on a G68 transaction.
    In subclasses, the class attribute `datatype` specifies the actual `Enum` to use.
    The enum value is serialized to a zero-padded numeric field.
    """

    datatype: Union[Type[Enum], NotImplementedError] = _not_implemented  # type: ignore[assignment]

    def __init__(self, val: Union[Enum, int]):
        # Allow instantiating an `EnumField` with either an `Enum` member or its
        # numeric equivalent.
        if isinstance(val, Enum):
            val = val.value
        super().__init__(val)  # type: ignore[arg-type]
        # Use the numeric value of the `Enum` member for the serialized output
        self._val = self._val.value

    @classmethod
    def from_str(cls, val: str) -> "EnumField":
        return cls(int(val))


class FloatingFieldMixin:
    """Represents a "floating field" on a G68 transaction.
    A "floating field" is a field containing a numeric field ID and a field value.
    It is serialized to `&NNMMMM` where `NN` is a two-digit numeric ID, and `MMMM`
    is the field value (which may be of different types and lengths.)
    """

    # These class attributes are expected to be overridden by subclasses
    id: Union[int, NotImplementedError] = _not_implemented
    required: bool = False

    # These class attributes are private and used for internal bookkeeping
    _id_cls_map: dict = dict()
    _required: set = set()
    _id_length = 2

    @property
    def serialized_value(self) -> str:
        # Use serialized value from field implementation class
        # (`NumericField`, `StringField`, etc.)
        val = super().serialized_value  # type: ignore[misc]
        # Field IDs are serialized as zero-padded two-digit numbers
        field_id: str = str(self.id).zfill(self._id_length)
        return f"&{field_id}{val}"

    def __init_subclass__(cls, **kwargs):
        cls_id = getattr(cls, "id")
        required = getattr(cls, "required")

        if cls_id is None or cls_id is _not_implemented:
            raise ValueError(f"{cls} is missing the `id` attribute")

        if cls_id in FloatingFieldMixin._id_cls_map:
            raise KeyError(
                f"{cls_id} is already in use ({FloatingFieldMixin._id_cls_map[cls_id]})"
            )
        else:
            FloatingFieldMixin._id_cls_map[cls_id] = cls

        if required is True:
            FloatingFieldMixin._required.add(cls)

    @classmethod
    def validate_required_fields(cls, fields: List["FloatingFieldMixin"]):
        required_ids: set = set(f.id for f in cls._required)
        field_ids: set = set(f.id for f in fields)
        missing: list = [
            subclass.__name__
            for subclass in cls._required
            if subclass.id in (required_ids - field_ids)
        ]
        if missing:
            raise ValueError(f"The following required fields are missing: {missing}")

    @classmethod
    def parse(cls, line: str, *expected_fields: Type[Field]) -> Generator:
        remainder = line[line.index("&") :]
        for val in remainder.split("&"):
            if val != "":
                field_id = int(val[0 : cls._id_length])
                if 1 <= field_id < 40:
                    field = cls._id_cls_map[field_id]
                    yield field.from_str(val[cls._id_length :])
                else:
                    yield BetalingstekstLinje(val[cls._id_length :], field_id)


# Domain models: enums


class TransaktionstypeEnum(Enum):
    AndenDestinationTilladt = 1
    TvungenDestination = 10


class UdbetalingsberettigetIdentKodeEnum(Enum):
    KreditorKontonummer = 1
    CPR = 2
    SE = 3
    CVR = 11


# Domain models: fixed fields


class Registreringssted(ZeroPaddedNumericField):
    length = 3


class Snitfladetype(StringField):
    length = 3

    _constant = "G68"

    def __init__(self, val: str):
        assert val == self._constant, f"{val!r} is not {self._constant!r}"
        super().__init__(val)


class Linjeløbenummer(ZeroPaddedNumericField):
    length = 5


class Transaktionstype(EnumField):
    datatype = TransaktionstypeEnum
    length = 2


class FlydendeEllerFast(NumericField):
    length = 1


# Domain models: subcomponents of floating field `Posteringshenvisning`


class Posteringsdato(DateField):
    pass


class Maskinnummer(ZeroPaddedNumericField):
    length = 5


# Domain models: floating fields


class Organisationsenhed(FloatingFieldMixin, ZeroPaddedNumericField):
    id = 2
    length = 4


class Organisationstype(FloatingFieldMixin, ZeroPaddedNumericField):
    id = 3
    length = 2


class UdIdent(FloatingFieldMixin, ZeroPaddedNumericField):
    id = 7
    length = 18
    required = True


class Udbetalingsbeløb(FloatingFieldMixin, ZeroPaddedNumericField):
    id = 8
    length = 11
    required = True

    def __init__(self, val: int):
        # Assumes that `val` is in kroner - we need to supply an amount in øre.
        # The sign is stored in `Fortegnsmarkering` so we use the absolute value
        # here.
        super().__init__(abs(val * 100))


class Fortegnsmarkering(FloatingFieldMixin, StringField):
    id = 9
    length = 1
    required = True

    def __init__(self, val: str):
        super().__init__(val)
        if self._val not in {"-", "+"}:
            raise ValueError(f"{val!r} must be either '-' or '+'")


class UdbetalingsberettigetIdentKode(FloatingFieldMixin, EnumField):
    datatype = UdbetalingsberettigetIdentKodeEnum
    id = 10
    length = 2
    required = True


class Udbetalingsberettiget(FloatingFieldMixin, ZeroPaddedNumericField):
    id = 11
    length = 14  # or 10, depending on value in field 10
    required = True


class Udbetalingsdato(FloatingFieldMixin, DateField):
    id = 12


class Posteringshenvisning(FloatingFieldMixin, StringField):
    id = 16
    length = 20
    required = True

    def __init__(
        self,
        posting_date: Posteringsdato,
        machine_id: Maskinnummer,
        line_no: Linjeløbenummer,
    ):
        super().__init__(
            "".join(
                map(
                    attrgetter("serialized_value"),
                    [posting_date, machine_id, line_no],
                )
            )
        )

    @classmethod
    def from_str(cls, val: str) -> "Posteringshenvisning":
        posting_date: Posteringsdato
        machine_id: Maskinnummer
        line_no: Linjeløbenummer
        posting_date, machine_id, line_no = Field.parse(
            val, Posteringsdato, Maskinnummer, Linjeløbenummer
        )
        return cls(posting_date, machine_id, line_no)


class Fakturanummer(FloatingFieldMixin, StringField):
    id = 17
    length = 20


class BetalingstekstLinje(FloatingFieldMixin, StringField):
    length = 81
    id = 40

    _min_id = 40
    _max_id = 75

    def __init__(self, val: str, field_id: int):
        if not (self._min_id <= field_id <= self._max_id):
            raise ValueError(
                f"id {field_id} must be between {self._min_id} and {self._max_id}"
            )
        super().__init__(val)
        self.id = field_id

    @classmethod
    def list_from_text(cls, text: str) -> List["BetalingstekstLinje"]:
        """Create zero or more `BetalingstekstLinje` instances from string `text`.
        Each `BetalingstekstLinje` has an ID between 40 and 75.
        """
        return [
            cls(line, field_id)
            for field_id, line in enumerate(
                wrap(
                    text,
                    width=cls.length,
                    max_lines=(cls._max_id - cls._min_id) + 1,
                    drop_whitespace=False,
                ),
                start=cls._min_id,
            )
        ]


class G68TransactionWriter:
    def __init__(
        self,
        registreringssted: int,
        organisationsenhed: int,
        maskinnummer: Optional[int] = None,
    ):
        self.reg = Registreringssted(registreringssted)
        self.org = Organisationsenhed(organisationsenhed)
        self.machine_id = Maskinnummer(0 if maskinnummer is None else maskinnummer)
        self._line_no = 1

    @property
    def line_no(self) -> int:
        return self._line_no

    def serialize_transaction(
        self,
        transaction_type: TransaktionstypeEnum,
        recipient_type: UdbetalingsberettigetIdentKodeEnum,
        recipient: str,
        amount: int,
        payment_date: date,
        posting_date: date,
        invoice_no: str,
        text: str,
    ) -> str:
        transaction = G68Transaction(
            self,
            Transaktionstype(transaction_type),
            UdbetalingsberettigetIdentKode(recipient_type),
            Udbetalingsberettiget(int(recipient)),
            Udbetalingsbeløb(amount),
            Udbetalingsdato(payment_date),
            Posteringsdato(posting_date),
            Fakturanummer(invoice_no),
            BetalingstekstLinje.list_from_text(text),
        )
        self._line_no += 1
        return transaction.serialized_value


class G68Transaction(Serializable):
    def __init__(
        self,
        writer: G68TransactionWriter,
        transaction_type: Transaktionstype,
        recipient_type: UdbetalingsberettigetIdentKode,
        recipient: Udbetalingsberettiget,
        amount: Udbetalingsbeløb,
        payment_date: Udbetalingsdato,
        posting_date: Posteringsdato,
        invoice_no: Fakturanummer,
        text: List[BetalingstekstLinje],
    ):
        self._writer = writer

        # Fixed fields whose value is always the same
        self.interface_type = Snitfladetype("G68")
        self.floating_marker = FlydendeEllerFast(1)

        # Fixed field passed via `writer` instance
        self.line_no = Linjeløbenummer(self._writer.line_no)

        # Fixed field passed via args to this method
        self.transaction_type = transaction_type

        # Floating fields whose value is always the same
        self.organisation_type = Organisationstype(0)
        self.out_ident = UdIdent(0)

        # Floating fields passed via args to this method
        self.recipient = recipient
        self.recipient_type = recipient_type
        self.amount = amount
        self.payment_date = payment_date
        self.posting_date = posting_date
        self.invoice_no = invoice_no
        self.text = text

    @property
    def serialized_value(self) -> str:
        all_fields = (
            self.fixed_fields
            + [self.floating_marker]
            + sorted(self.floating_fields, key=attrgetter("id"))
        )
        return "".join(map(attrgetter("serialized_value"), all_fields))

    @property
    def fixed_fields(self) -> List[Field]:
        return [
            self._writer.reg,
            self.interface_type,
            self.line_no,
            self.transaction_type,
        ]

    @property
    def floating_fields(self) -> List[FloatingFieldMixin]:
        fields: List[FloatingFieldMixin] = [
            self._writer.org,
            self.organisation_type,
            self.out_ident,
            self.amount,
            Fortegnsmarkering("+" if self.amount.val >= 0 else "-"),
            self.recipient_type,
            self.recipient,
            self.payment_date,
            self.posting_reference,
            self.invoice_no,
            *self.text,
        ]
        FloatingFieldMixin.validate_required_fields(fields)
        return fields

    @property
    def posting_reference(self) -> Posteringshenvisning:
        return Posteringshenvisning(
            self.posting_date,
            self._writer.machine_id,
            self.line_no,
        )

    @classmethod
    def parse(cls, line: str) -> Generator[Field, None, None]:
        # Read fixed fields
        yield from Field.parse(
            line,
            Registreringssted,
            Snitfladetype,
            Linjeløbenummer,
            Transaktionstype,
            FlydendeEllerFast,
        )
        # Read floating fields
        yield from FloatingFieldMixin.parse(line)
