from datetime import date, datetime, timezone

from tenQ.dates import get_last_payment_date
from collections import OrderedDict
from decimal import Decimal


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
    def format_timestamp(dt: datetime):
        return '{:0%Y%m%d%H%M}'.format(dt)

    @staticmethod
    def format_date(d: date):
        return '{:%Y%m%d}'.format(d)

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

    def __init__(self, due_date: date, year: int, timestamp: datetime = None):
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

    def serialize_transaction(self, cpr_nummer: str, amount_in_dkk: int, afstem_noegle: str, rate_text: str, leverandoer_ident: str):
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


class G69TransactionWriter(object):

    alphanum = 1
    numeric = 2
    amount = 3
    fields = OrderedDict({
        # id: (name, width, type, required, pad)
        101: ('kaldenavn', 10, str, False, False),
        102: ('afstemningsenhed', 5, str, False, False),
        103: ('maskinnr', 5, int, True, True),
        104: ('eks_løbenr', 7, int, True, True),
        110: ('post_dato', 8, date, True, True),
        111: ('kontonr', 10, int, True, True),
        112: ('beløb', 13, Decimal, True, True),
        113: ('deb_kred', 1, str, True, False),
        114: ('regnskabsår', 4, int, False, True),
        116: ('bilag_arkiv_nr', 255, str, False, False),
        117: ('udbet_henv_nr', 20, int, False, False),
        118: ('valør_dato', 8, date, False, False),
        130: ('betaling_modtager_nrkode', 2, int, False, True),
        131: ('betaling_modtager', 10, int, False, True),
        132: ('ydelse_modtager_nrkode', 2, int, False, True),
        133: ('ydelse_modtager', 10, int, False, True),
        134: ('oplysningspligtig_nrkode', 2, int, False, True),
        135: ('oplysningspligtig', 10, int, False, True),
        136: ('oplysningspligt_kode', 1, str, False, False),
        150: ('postering_udtrækstekst_1', 5, str, False, False),
        151: ('postering_udtrækstekst_2', 5, str, False, False),
        152: ('postering_udtrækskode', 5, str, False, False),
        153: ('posteringstekst', 35, str, False, False),
        170: ('rekvisitionsnr', 10, int, False, True),
        171: ('delleverance', 1, str, False, False),
        180: ('bærer', 10, str, False, False),
        181: ('afdeling', 10, str, False, False),
        182: ('formål', 10, str, False, False),
        185: ('omvendt_betalingspligt', 2, int, False, True),
        200: ('kontering_fakturapulje', 1, str, False, False),
        201: ('konteret_af', 5, str, False, False),
        202: ('notat_short', 200, str, False, False),
        203: ('attesteret_af', 5, str, False, False),
        210: ('emne', 60, str, False, False),
        211: ('notat_long', 1024, str, False, False),
        250: ('ekstern_reference', 20, str, False, False),
        251: ('iris_nr', 20, str, False, False),
        300: ('projekt_nr', 20, str, False, False),
        301: ('projekt_art', 10, str, False, False),
        302: ('prisme_medarbejder', 10, str, False, False),
        303: ('salgspris', 13, Decimal, False, False),
        304: ('antal', 10, Decimal, False, False),
        305: ('linje_egenskab', 10, str, False, False),
        306: ('aktivitet_nr', 10, str, False, False),
    })

    # Set of required codes
    required = set([
        code
        for code, config in fields.items()
        if config[3]
    ])

    # mapping of codes with other codes that they require
    # (if 132 is set, 133 must be as well)
    required_together = {
        132: (133,), 133: (132,),
        170: (171,), 171: (170,),
        210: (211,), 211: (210,),
        300: (301, 304),
        301: (300, 304),
        302: (300, 301, 304),
        303: (300, 301, 304),
        304: (300, 301),
        305: (300, 301, 304),
        306: (300, 301, 304),
    }

    # mapping of codes that may not be present together
    # (if 210 is present, neither 116 or 200 may be)
    mutually_exclusive = {
        210: (116, 200),
        211: (116, 200)
    }

    # shorthands; it's easier to remember and provide
    # is_cvr=True than ydelse_modtager_nrkode=3
    aliases = {
        'is_cvr': {'field': 132, 'map': {False: 2, True: 3}},
        'is_kontering_fakturapulje': {'field': 200, map: {False: 'N', True: 'J'}},
        'is_debet': {'field': 113, 'map': {False: 'K', True: 'D'}},
        'is_kredit': {'field': 113, 'map': {False: 'D', True: 'K'}},
    }

    registreringssted = 0
    snitfladetype = 'G69'
    organisationsenhed = 0
    organisationstype = 1
    linjeformat = 'FLYD'

    # Line number in the file; successive calls to serialize_transaction increment this.
    # Be sure to use a new G69TransactionWriter or reset the line number when writing a new file
    line_number = 1

    def __init__(self, registreringssted: int, organisationsenhed: int):
        self.registreringssted = registreringssted
        self.organisationsenhed = organisationsenhed

    def reset_line_number(self):
        self.line_number = 1

    def serialize_transaction(self, post_type: str = 'NOR', **kwargs):
        output = []
        post_type = post_type.upper()
        if post_type not in ('NOR', 'PRI', 'SUP'):
            raise ValueError("post_type must be NOR, PRI or SUP")

        for alias, config in self.aliases.items():
            if alias in kwargs:
                name = self.fields[config['field']][0]
                if kwargs[alias] in config['map']:
                    kwargs[name] = config['map'][kwargs[alias]]

        # Header
        output.append(
            ''.join([
                str(self.registreringssted).rjust(3, '0'),
                self.snitfladetype,
                str(self.line_number).rjust(5, '0'),
                str(self.organisationsenhed).rjust(4, '0'),
                str(self.organisationstype).rjust(2, '0'),
                post_type,
                self.linjeformat
            ])
        )

        present_fields = set([
            code
            for code, config in self.fields.items()
            if config[0] in kwargs
        ])

        for code in self.required:
            name = self.fields[code][0]
            if name not in kwargs:
                raise ValueError(f"Field {name} required")

        for key, required in self.required_together.items():
            if key in present_fields:
                if not all([r in present_fields for r in required]):
                    raise ValueError(''.join([
                        f"When supplying {self.fields[key][0]}, you must also supply ",
                        (', '.join([f'"{self.fields[r][0]}"' for r in required]))
                    ]))

        for key, excluded in self.mutually_exclusive.items():
            if key in present_fields:
                if any([e in present_fields for e in excluded]):
                    raise ValueError(''.join([
                        f"When supplying {self.fields[key][0]}, you may not also supply ",
                        (', '.join([f'"{self.fields[e][0]}"' for e in excluded]))
                    ]))

        # data
        for code, config in self.fields.items():
            (name, width, required_type, required, pad) = config
            if name not in kwargs:
                if required:
                    raise KeyError(name)
            else:
                present_fields.add(code)
                value = kwargs[name]
                if type(value) != required_type:
                    if required_type == Decimal and type(value) == int:
                        value = Decimal(value)
                    else:
                        raise ValueError(f"{name}={value} must be of type {required_type}")
                if required_type == int:
                    value = G69TransactionWriter.format_nummer(value)
                elif required_type == date:
                    value = G69TransactionWriter.format_date(value)
                elif required_type == Decimal:
                    value = G69TransactionWriter.format_amount_kr(value)
                else:
                    value = str(value)
                if '&' in value:
                    raise ValueError(f"Value {name}={value} may not contain &")
                if len(value) > width:
                    raise ValueError(f"Value {name}={value} may not exceed length {width}")
                if pad:
                    value = value.rjust(width, '0')
                code = str(code).rjust(3, '0')
                output.append(f"{code}{value}")
                self.line_number += 1
        return '&'.join(output)

    def serialize_transaction_pair(self, post_type: str = 'NOR', **kwargs):
        return '\r\n'.join([
            self.serialize_transaction(post_type, **{**kwargs, 'is_debet': debet})
            for debet in (True, False)
        ])

    @staticmethod
    def format_timestamp(dt: datetime):
        return '{:0%Y%m%d%H%M}'.format(dt)

    @staticmethod
    def format_date(d: date):
        return '{:%Y%m%d}'.format(d)

    @staticmethod
    def format_omraade_nummer(year):
        return str(year)[1:]

    @staticmethod
    def format_amount_øre(amount):
        return str(abs(amount)) + ('-' if amount < 0 else ' ')

    @staticmethod
    def format_amount_kr(amount: Decimal):
        return G69TransactionWriter.format_amount_øre(int(amount * 100))

    @staticmethod
    def format_nummer(nummer):
        return str(nummer)
