from datetime import date, datetime, timezone

from tenQ.dates import get_last_payment_date


# Temporary class for serializing transaction data in a writer
# Uses KMD GE550010Q v 15
class TenQTransaction(dict):

    fieldspec = (
        ('leverandoer_ident', 4, None),
        ('trans_type', 2, None),
        ('time_stamp', 13, None),  # Timestamp is normally 12 chars, but here we have a prefixed 0
        ('bruger_nummer', 4, '0900'),
        ('omraad_nummer', 3, None),
        ('betal_art', 3, 209),
        ('paalign_aar', 4, None),
        ('debitor_nummer', 10, None),
        ('sag_nummer', 2, '00'),
    )
    trans_type = None

    def __init__(self, **kwargs):
        super(TenQTransaction, self).__init__()
        for field_name, _, default in self.fieldspec:
            self[field_name] = kwargs.get(field_name, default)
        self['trans_type'] = self.trans_type

    def serialize_transaction(self, **kwargs):

        data = {**self}
        data.update(kwargs)

        data['debitor_nummer'] = data['cpr_nummer']
        data['person_nummer'] = data['cpr_nummer']

        fields = []

        for field_name, width, _ in self.fieldspec:
            value = data[field_name]

            if value is None:
                raise ValueError("Value for %s cannot be None" % (field_name))

            value = str(value)

            if len(value) > width:
                raise ValueError(
                    "Value '%s' for field %s is wider than %d characters" % (
                        value,
                        field_name,
                        width
                    )
                )

            fields.append(value.rjust(width))

        return ''.join(fields)

    @staticmethod
    def format_timestamp(datetime):
        return '{:0%Y%m%d%H%M}'.format(datetime)

    @staticmethod
    def format_date(date):
        return '{:%Y%m%d}'.format(date)

    @staticmethod
    def format_omraade_nummer(year):
        return str(year)[1:]

    @staticmethod
    def format_amount(amount):
        sign = '-' if amount < 0 else '+'
        return str(abs(amount)).rjust(10, '0') + sign

    def __str__(self):
        return str(self.get_data())


class TenQFixWidthFieldLineTransactionType10(TenQTransaction):
    fieldspec = TenQTransaction.fieldspec + tuple([
        ('person_nummer', 10, None)
    ])
    trans_type = 10


class TenQFixWidthFieldLineTransactionType24(TenQTransaction):
    fieldspec = TenQTransaction.fieldspec + (
        ('individ_type', 2, '20'),  # Hardcoded to 20 according to spec
        ('rate_nummer', 3, '999'),  # Hardcoded to 999 according to spec
        ('rate_beloeb', 11, None),
        ('belob_type', 1, '1'),  # Hardcoded to 1 according to spec
        ('rentefri_beloeb', 11, '0000000000+'),  # Hardcoded since the amount is in 'rate_beloeb'
        ('opkraev_kode', 1, '1'),  # Hardcoded to nettoopkraevning
        ('opkraev_dato', 8, None),
        ('forfald_dato', 8, None),
        ('betal_dato', 8, None),
        ('rentefri_dato', 8, None),
        ('tekst_nummer', 3, '000'),  # Hardcoded to 000 according to spec
        ('rate_spec', 3, ''),  # Hardcoded to <empty> according to spec
        ('slet_mark', 1, ''),  # Hardcoded to <empty> according to spec
        ('faktura_no', 35, ''),  # Hardcoded to <empty> according to spec
        ('stiftelse_dato', 8, None),
        ('fra_periode', 8, None),
        ('til_periode', 8, None),
        ('aedring_aarsag_kode', 4, ''),  # Hardcoded to <empty> according to spec
        ('aedring_aarsag_tekst', 100, ''),  # Hardcoded to <empty> according to spec
        ('afstem_noegle', 35, None)
    )
    trans_type = 24  # Hardcoded to 24 according to spec


class TenQFixWidthFieldLineTransactionType26(TenQTransaction):
    fieldspec = TenQTransaction.fieldspec + (
        ('individ_type', 2, '20'),  # Hardcoded to 20 according to spec
        ('rate_nummer', 3, '999'),  # Hardcoded to 999 according to spec
        ('line_number', 3, None),
    )
    trans_type = 26

    # Special case for field 'rate_text': This field should be appended at the end and not
    # right justified with max. 60 characters.

    def serialize_transaction(self, **kwargs):
        line = super(
            TenQFixWidthFieldLineTransactionType26, self
        ).serialize_transaction(**kwargs)
        line += kwargs['rate_text'][:60]

        return line


class TenQTransactionWriter(object):

    transaction_10 = None
    transaction_24 = None
    transaction_26 = None
    transaction_list = ''
    tax_year = None

    def __init__(self, due_date, year, timestamp=None):
        # Make sure due_date is on local time
        if timestamp is None:
            timestamp = datetime.utcnow().replace(tzinfo=timezone.utc)
        omraad_nummer = TenQTransaction.format_omraade_nummer(year)
        last_payment_date = get_last_payment_date(due_date)

        init_data = {
            'time_stamp': TenQTransaction.format_timestamp(timestamp),
            'omraad_nummer': omraad_nummer,
            'paalign_aar': year,
            # Note that the names of the following two datefields have different
            # meanings in Prisme and in the 10Q format. The way there are used
            # here results in the correct data in Prisme.
            'opkraev_dato': TenQTransaction.format_date(last_payment_date),
            'forfald_dato': TenQTransaction.format_date(due_date),
            'betal_dato': TenQTransaction.format_date(last_payment_date),
            'rentefri_dato': TenQTransaction.format_date(last_payment_date),
            'stiftelse_dato': TenQTransaction.format_date(due_date),
            'fra_periode': TenQTransaction.format_date(date(year=year, month=1, day=1)),
            'til_periode': TenQTransaction.format_date(date(year=year, month=12, day=31)),
        }

        self.transaction_10 = TenQFixWidthFieldLineTransactionType10(**init_data)
        self.transaction_24 = TenQFixWidthFieldLineTransactionType24(**init_data)
        self.transaction_26 = TenQFixWidthFieldLineTransactionType26(**init_data)

    def serialize_transaction(self, cpr_nummer, amount_in_dkk, afstem_noegle, rate_text, leverandoer_ident):
        data = {
            "cpr_nummer": cpr_nummer,
            "rate_beloeb": TenQTransaction.format_amount(amount_in_dkk * 100),  # Amount is in øre, so multiply by 100
            'afstem_noegle': afstem_noegle,
            "leverandoer_ident": leverandoer_ident,
        }
        # Initial two lines
        result_lines = [
            self.transaction_10.serialize_transaction(**data),
            self.transaction_24.serialize_transaction(**data),
        ]
        # One type 26 line for each line in the rate text.
        for line_nr, line in enumerate(rate_text.splitlines()):
            result_lines.append(
                self.transaction_26.serialize_transaction(
                    line_number=str(line_nr).rjust(3, '0'),
                    rate_text=line,
                    **data
                ),
            )

        return '\r\n'.join(result_lines)


# afstem_noegle = '44edf2b0-9e2d-40fa-8087-cb37cfbdb66'  # SET PROPERTY HERE Skal vaere unik pr. dataleverandoer identifikation og pr. G19-transaktiontype og pr. kommune (hordcoded based on random uuid)
# cpr_nummer = '2507919858'  # TEST-CPR-NUMMER som brugt i eksempel fra dokumentation
# tilbagebetaling = 200

# # Construct the writer
# transaction_creator = TransactionCreator(due_date=datetime.now(), tax_year=2020)
# print(transaction_creator.make_transaction(cpr_nummer=cpr_nummer, rate_beloeb=tilbagebetaling, afstem_noegle=afstem_noegle))
