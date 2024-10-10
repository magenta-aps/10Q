# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0

from datetime import date, datetime, timezone

from tenQ.dates import get_last_payment_date_from_due_date


# Temporary class for serializing transaction data in a writer
# Uses KMD GE550010Q v 15
# Eller se online dokumentation https://aka.nanoq.gl/etaxOIO/FileFormats/Prisme/10Q.aspx
class TenQTransaction(dict):
    fieldspec = (
        ("leverandoer_ident", 4, None),
        ("trans_type", 2, None),
        (
            "time_stamp",
            13,
            None,
        ),  # Timestamp is normally 12 chars, but here we have a prefixed 0
        ("bruger_nummer", 4, "0900"),
        ("omraade_nummer", 3, None),
        ("betal_art", 3, 209),
        ("paalign_aar", 4, None),
        ("debitor_nummer", 10, None),
        ("sag_nummer", 2, "00"),
    )
    trans_type = None

    def __init__(self, **kwargs):
        super(TenQTransaction, self).__init__()
        for field_name, _, default in self.fieldspec:
            self[field_name] = kwargs.get(field_name, default)
        self["trans_type"] = self.trans_type

    def parse(self, line):
        data = {}
        pos = 0
        for name, length, default in self.fieldspec:
            data[name] = line[pos : pos + length]
            pos += length
        return data

    @property
    def serialize_fields(self):
        return self.fieldspec

    def serialize_transaction(self, **kwargs):
        data = {**self}
        data.update(kwargs)

        data["debitor_nummer"] = str(data["cpr_nummer"]).zfill(10)
        data["person_nummer"] = str(data["cpr_nummer"]).zfill(10)

        fields = []

        for field_name, width, _ in self.serialize_fields:
            value = data[field_name]

            if value is None:
                raise ValueError("Value for %s cannot be None" % (field_name))

            value = str(value)

            if len(value) > width:
                raise ValueError(
                    "Value '%s' for field %s is wider than %d characters"
                    % (value, field_name, width)
                )

            fields.append(value.rjust(width))

        return "".join(fields)

    @staticmethod
    def format_timestamp(dt: datetime):
        return "{:0%Y%m%d%H%M}".format(dt)

    @staticmethod
    def format_date(d: date):
        return "{:%Y%m%d}".format(d)

    @staticmethod
    def format_omraade_nummer(nummer):
        return str(nummer)[-3:].zfill(3)

    @staticmethod
    def format_amount(amount):
        # amount angives i ører og fortegn angives som sidste karakter
        sign = "-" if amount < 0 else "+"
        return str(abs(amount)).rjust(10, "0") + sign

    @staticmethod
    def format_nummer(nummer, width):
        # Efter aftale anvendes skatteaaret som omraadenummer
        return str(nummer).rjust(width, "0")

    def __str__(self):
        return str(self.get_data())


class TenQFixWidthFieldLineTransactionType10(TenQTransaction):
    fieldspec = TenQTransaction.fieldspec + (("person_nummer", 10, None),)
    trans_type = 10


class TenQFixWidthFieldLineTransactionType24(TenQTransaction):
    fieldspec = TenQTransaction.fieldspec + (
        ("individ_type", 2, "20"),  # Hardcoded to 20 according to spec
        ("rate_nummer", 3, "999"),  # Hardcoded to 999 according to spec
        ("rate_beloeb", 11, None),
        ("belob_type", 1, "1"),  # Hardcoded to 1 according to spec
        (
            "rentefri_beloeb",
            11,
            "0000000000+",
        ),  # Hardcoded since the amount is in 'rate_beloeb'
        ("opkraev_kode", 1, "1"),  # Hardcoded to nettoopkraevning
        ("opkraev_dato", 8, None),
        ("forfald_dato", 8, None),
        ("betal_dato", 8, None),
        ("rentefri_dato", 8, None),
        ("tekst_nummer", 3, "000"),  # Hardcoded to 000 according to spec
        ("rate_spec", 3, ""),  # Hardcoded to <empty> according to spec
        ("slet_mark", 1, ""),  # Hardcoded to <empty> according to spec
        ("faktura_no", 35, ""),  # Hardcoded to <empty> according to spec
        ("stiftelse_dato", 8, None),
        ("fra_periode", 8, None),
        ("til_periode", 8, None),
        ("aedring_aarsag_kode", 4, ""),  # Hardcoded to <empty> according to spec
        ("aedring_aarsag_tekst", 100, ""),  # Hardcoded to <empty> according to spec
        ("afstem_noegle", 35, None),
    )
    trans_type = 24  # Hardcoded to 24 according to spec


class TenQFixWidthFieldLineTransactionType26(TenQTransaction):
    fieldspec = TenQTransaction.fieldspec + (
        ("individ_type", 2, "20"),  # Hardcoded to 20 according to spec
        ("rate_nummer", 3, "999"),  # Hardcoded to 999 according to spec
        ("line_number", 3, None),
        ("rate_text", 60, ""),
    )
    trans_type = 26

    @property
    def serialize_fields(self):
        return self.fieldspec[0:-1]

    # Special case for field 'rate_text': This field should be appended at the end and not
    # right justified with max. 60 characters.
    def serialize_transaction(self, **kwargs):
        line = super(
            TenQFixWidthFieldLineTransactionType26, self
        ).serialize_transaction(**kwargs)
        line += kwargs["rate_text"][:60]
        return line


class TenQFixWidthFieldLineTransactionType52(TenQTransaction):
    fieldspec = TenQTransaction.fieldspec + (("ean_lokationsnummer", 13, None),)
    trans_type = 52


class TenQTransactionWriter(object):
    transaction_10 = None
    transaction_24 = None
    transaction_26 = None
    transaction_52 = None
    transaction_list = ""

    def __init__(
        self,
        due_date: date,
        year: int,
        leverandoer_ident: str,
        timestamp: datetime = None,
        periode_fra: date = None,
        periode_til: date = None,
        creation_date: date = None,
        faktura_no: str = None,
        bruger_nummer: str = None,
        betal_art: str = None,
        last_payment_date: date = None,
        opkraev_date: date = None,
        interest_date: date = None,
        omraade_nummer: int = None,
        ean_lokationsnummer: str = None,
    ):
        if timestamp is None:
            timestamp = datetime.utcnow().replace(tzinfo=timezone.utc)
        if creation_date is None:
            creation_date = due_date
        if periode_fra is None:
            periode_fra = date(year=year, month=1, day=1)
        if periode_til is None:
            periode_til = date(year=year, month=12, day=31)
        if bruger_nummer is None:
            bruger_nummer = "0900"
        if betal_art is None:
            betal_art = 209
        if faktura_no is None:
            faktura_no = ""
        if omraade_nummer is None:
            omraade_nummer = year
        if last_payment_date is None:
            last_payment_date = get_last_payment_date_from_due_date(due_date)
        if opkraev_date is None:
            opkraev_date = last_payment_date
        if interest_date is None:
            interest_date = last_payment_date

        init_data = {
            "time_stamp": TenQTransaction.format_timestamp(timestamp),
            "leverandoer_ident": leverandoer_ident,
            "omraade_nummer": TenQTransaction.format_omraade_nummer(omraade_nummer),
            "paalign_aar": year,
            # Note that the names of the following two datefields have different
            # meanings in Prisme and in the 10Q format. The way there are used
            # here results in the correct data in Prisme.
            "opkraev_dato": TenQTransaction.format_date(opkraev_date),
            "forfald_dato": TenQTransaction.format_date(due_date),
            "betal_dato": TenQTransaction.format_date(last_payment_date),
            "rentefri_dato": TenQTransaction.format_date(interest_date),
            "stiftelse_dato": TenQTransaction.format_date(creation_date),
            "fra_periode": TenQTransaction.format_date(periode_fra),
            "til_periode": TenQTransaction.format_date(periode_til),
            "faktura_no": faktura_no,
            "bruger_nummer": bruger_nummer,
            "betal_art": betal_art,
            "ean_lokationsnummer": ean_lokationsnummer,
        }

        self.transaction_10 = TenQFixWidthFieldLineTransactionType10(**init_data)
        self.transaction_24 = TenQFixWidthFieldLineTransactionType24(**init_data)
        self.transaction_26 = TenQFixWidthFieldLineTransactionType26(**init_data)
        self.transaction_52 = TenQFixWidthFieldLineTransactionType52(**init_data)

        self.transaction_map = {
            "10": self.transaction_10,
            "24": self.transaction_24,
            "26": self.transaction_26,
            "52": self.transaction_52,
        }

    def parse(self, text):
        data = []
        for line in text.split("\r\n"):
            transaction_object = self.transaction_map.get(line[4:6])
            if transaction_object:
                data.append(transaction_object.parse(line))
        return data

    def serialize_transaction(
        self,
        cpr_nummer: str,
        amount_in_dkk: int,
        afstem_noegle: str,
        rate_text: str,
        sag_nummer: int = 0,
        individ_type: int = 20,
        rate_nummer: int = 999,
        belob_type: int = 1,
        rentefri_beloeb: int = 0,
        opkraev_kode: int = 1,
        ean_lokationsnummer: str = "",
    ):
        data = {
            "cpr_nummer": cpr_nummer,
            "rate_beloeb": TenQTransaction.format_amount(
                amount_in_dkk * 100
            ),  # Amount is in øre, so multiply by 100
            "afstem_noegle": afstem_noegle,
            "sag_nummer": TenQTransaction.format_nummer(sag_nummer, 2),
            "individ_type": TenQTransaction.format_nummer(individ_type, 2),
            "rate_nummer": TenQTransaction.format_nummer(rate_nummer, 3),
            "belob_type": belob_type,
            "rentefri_beloeb": TenQTransaction.format_amount(rentefri_beloeb),
            "opkraev_kode": opkraev_kode,
            "ean_lokationsnummer": ean_lokationsnummer,
        }
        # Initial two lines
        result_lines = [
            self.transaction_10.serialize_transaction(**data),
            self.transaction_24.serialize_transaction(**data),
        ]
        # One type 26 line for each line in the rate text.
        for line_nr, line in enumerate(rate_text.splitlines(), 1):
            result_lines.append(
                self.transaction_26.serialize_transaction(
                    line_number=str(line_nr).rjust(3, "0"), rate_text=line, **data
                ),
            )
        if ean_lokationsnummer:
            result_lines.append(self.transaction_52.serialize_transaction(**data))
        return "\r\n".join(result_lines)


# afstem_noegle = '44edf2b0-9e2d-40fa-8087-cb37cfbdb66'  # SET PROPERTY HERE Skal vaere unik pr. dataleverandoer identifikation og pr. G19-transaktiontype og pr. kommune (hordcoded based on random uuid)
# cpr_nummer = '2507919858'  # TEST-CPR-NUMMER som brugt i eksempel fra dokumentation
# tilbagebetaling = 200

# # Construct the writer
# transaction_creator = TenQTransactionWriter(due_date=datetime.now(), year=2020)
# print(transaction_creator.serialize_transaction(cpr_nummer=cpr_nummer, rate_beloeb=tilbagebetaling, afstem_noegle=afstem_noegle))
