from collections import OrderedDict
from datetime import date, datetime, timezone
from decimal import Decimal

from tenQ.dates import get_last_payment_date_from_due_date


# Temporary class for serializing transaction data in a writer
# Uses KMD GE550010Q v 15
# Eller se online dokumentation https://aka.nanoq.gl/etaxOIO/FileFormats/Prisme/10Q.aspx
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

    def parse(self, line):
        data = {}
        pos = 0
        for name, length, default in self.fieldspec:
            data[name] = line[pos:pos+length]
            pos += length
        return data

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
        # amount angives i ører og fortegn angives som sidste karakter
        sign = '-' if amount < 0 else '+'
        return str(abs(amount)).rjust(10, '0') + sign

    @staticmethod
    def format_nummer(nummer, width):
        # Efter aftale anvendes skatteaaret som omraadenummer
        return str(nummer).rjust(width, '0')

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

    def __init__(self, due_date: date, year: int, leverandoer_ident: str, timestamp: datetime = None,
                 periode_fra: date = None, periode_til: date = None, creation_date: date = None,
                 faktura_no: str = None, bruger_nummer: str = None, betal_art: str = None,
                 last_payment_date: date = None, opkraev_date: date = None, interest_date: date = None
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
            bruger_nummer = '0900'
        if betal_art is None:
            betal_art = 209
        if faktura_no is None:
            faktura_no = ''
        omraad_nummer = TenQTransaction.format_omraade_nummer(year)
        if last_payment_date is None:
            last_payment_date = get_last_payment_date_from_due_date(due_date)
        if opkraev_date is None:
            opkraev_date = last_payment_date
        if interest_date is None:
            interest_date = last_payment_date

        init_data = {
            'time_stamp': TenQTransaction.format_timestamp(timestamp),
            'leverandoer_ident': leverandoer_ident,
            'omraad_nummer': omraad_nummer,
            'paalign_aar': year,
            # Note that the names of the following two datefields have different
            # meanings in Prisme and in the 10Q format. The way there are used
            # here results in the correct data in Prisme.
            'opkraev_dato': TenQTransaction.format_date(opkraev_date),
            'forfald_dato': TenQTransaction.format_date(due_date),
            'betal_dato': TenQTransaction.format_date(last_payment_date),
            'rentefri_dato': TenQTransaction.format_date(interest_date),
            'stiftelse_dato': TenQTransaction.format_date(creation_date),
            'fra_periode': TenQTransaction.format_date(periode_fra),
            'til_periode': TenQTransaction.format_date(periode_til),
            'faktura_no': faktura_no,
            'bruger_nummer': bruger_nummer,
            'betal_art': betal_art,
        }

        self.transaction_10 = TenQFixWidthFieldLineTransactionType10(**init_data)
        self.transaction_24 = TenQFixWidthFieldLineTransactionType24(**init_data)
        self.transaction_26 = TenQFixWidthFieldLineTransactionType26(**init_data)

        self.transaction_map = {
            "10": self.transaction_10,
            "24": self.transaction_24,
            "26": self.transaction_26,
        }

    def parse(self, text):
        data = []
        for line in text.split("\r\n"):
            transaction_object = self.transaction_map.get(line[4:6])
            if transaction_object:
                data.append(transaction_object.parse(line))
        return data

    def serialize_transaction(self,
                              cpr_nummer: str, amount_in_dkk: int, afstem_noegle: str, rate_text: str,
                              sag_nummer: int = 0, individ_type: int = 20, rate_nummer: int = 999, belob_type: int = 1,
                              rentefri_beloeb: int = 0, opkraev_kode: int = 1):
        data = {
            "cpr_nummer": cpr_nummer,
            "rate_beloeb": TenQTransaction.format_amount(amount_in_dkk * 100),  # Amount is in øre, so multiply by 100
            'afstem_noegle': afstem_noegle,
            'sag_nummer': TenQTransaction.format_nummer(sag_nummer, 2),
            'individ_type': TenQTransaction.format_nummer(individ_type, 2),
            'rate_nummer': TenQTransaction.format_nummer(rate_nummer, 3),
            'belob_type': belob_type,
            'rentefri_beloeb': TenQTransaction.format_amount(rentefri_beloeb),
            'opkraev_kode': opkraev_kode,
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
# transaction_creator = TenQTransactionWriter(due_date=datetime.now(), year=2020)
# print(transaction_creator.serialize_transaction(cpr_nummer=cpr_nummer, rate_beloeb=tilbagebetaling, afstem_noegle=afstem_noegle))


class G69TransactionWriter(object):
    '''
    Writer for G69 transactions
    See doc at https://aka.nanoq.gl/etaxOIO/FileFormats/Prisme/G69.aspx
    '''
    alphanum = 1
    numeric = 2
    amount = 3
    fields = OrderedDict({
        # name: (id, width, type, required, pad)
        'kaldenavn': (101, 10, str, False, False),
        'afstemningsenhed': (102, 5, str, False, False),
        'maskinnr': (103, 5, int, True, True),
        'eks_løbenr': (104, 7, int, True, True),
        'post_dato': (110, 8, date, True, True),
        'kontonr': (111, 15, int, True, True),
        'beløb': (112, 13, Decimal, True, True),
        'deb_kred': (113, 1, str, True, False),
        'regnskabsår': (114, 4, int, False, True),
        'bilag_arkiv_nr': (116, 255, str, False, False),
        'udbet_henv_nr': (117, 20, int, False, False),
        'valør_dato': (118, 8, date, False, False),
        'betaling_modtager_nrkode': (130, 2, int, False, True),
        'betaling_modtager': (131, 10, int, False, True),
        'ydelse_modtager_nrkode': (132, 2, int, False, True),
        'ydelse_modtager': (133, 10, str, False, False),
        'oplysningspligtig_nrkode': (134, 2, int, False, True),
        'oplysningspligtig': (135, 10, int, False, True),
        'oplysningspligt_kode': (136, 1, str, False, False),
        'postering_udtrækstekst_1': (150, 5, str, False, False),
        'postering_udtrækstekst_2': (151, 5, str, False, False),
        'postering_udtrækskode': (152, 5, str, False, False),
        'posteringstekst': (153, 35, str, False, False),
        'rekvisitionsnr': (170, 10, int, False, True),
        'delleverance': (171, 1, str, False, False),
        'bærer': (180, 10, str, False, False),
        'afdeling': (181, 10, str, False, False),
        'formål': (182, 10, str, False, False),
        'omvendt_betalingspligt': (185, 2, int, False, True),
        'kontering_fakturapulje': (200, 1, str, False, False),
        'konteret_af': (201, 5, str, False, False),
        'notat_short': (202, 200, str, False, False),
        'attesteret_af': (203, 5, str, False, False),
        'emne': (210, 60, str, False, False),
        'notat_long': (211, 1024, str, False, False),
        'ekstern_reference': (250, 20, str, False, False),
        'iris_nr': (251, 20, str, False, False),
        'projekt_nr': (300, 20, str, False, False),
        'projekt_art': (301, 10, str, False, False),
        'prisme_medarbejder': (302, 10, str, False, False),
        'salgspris': (303, 13, Decimal, False, False),
        'antal': (304, 10, Decimal, False, False),
        'linje_egenskab': (305, 10, str, False, False),
        'aktivitet_nr': (306, 10, str, False, False),
    })

    # Set of required codes
    required = set([
        name
        for name, config in fields.items()
        if config[3]
    ])

    # mapping of codes with other codes that they require
    # (if ydelse_modtager_nrkode is set, ydelse_modtager must be as well)
    required_together = {
        'ydelse_modtager_nrkode': ('ydelse_modtager',), 'ydelse_modtager': ('ydelse_modtager_nrkode',),
        'rekvisitionsnr': ('delleverance',), 'delleverance': ('rekvisitionsnr',),
        'emne': ('notat_long',), 'notat_long': ('emne',),
        'projekt_nr': ('projekt_art', 'antal'),
        'projekt_art': ('projekt_nr', 'antal'),
        'prisme_medarbejder': ('projekt_nr', 'projekt_art', 'antal'),
        'salgspris': ('projekt_nr', 'projekt_art', 'antal'),
        'antal': ('projekt_nr', 'projekt_art'),
        'linje_egenskab': ('projekt_nr', 'projekt_art', 'antal'),
        'aktivitet_nr': ('projekt_nr', 'projekt_art', 'antal'),
    }

    # mapping of codes that may not be present together
    # (if emne is present, neither bilag_arkiv_nr or kontering_fakturapulje may be)
    mutually_exclusive = {
        'emne': ('bilag_arkiv_nr', 'kontering_fakturapulje'),
        'notat_long': ('bilag_arkiv_nr', 'kontering_fakturapulje')
    }

    # shorthands; it's easier to remember and provide
    # is_cvr=True than ydelse_modtager_nrkode=3
    aliases = {
        'is_cvr': {'field': 'ydelse_modtager_nrkode', 'map': {False: 2, True: 3}},
        'is_kontering_fakturapulje': {'field': 'kontering_fakturapulje', map: {False: 'N', True: 'J'}},
        'is_debet': {'field': 'deb_kred', 'map': {False: 'K', True: 'D'}},
        'is_kredit': {'field': 'deb_kred', 'map': {False: 'D', True: 'K'}},
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
                name = config['field']
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

        present_fields = set([name for name in self.fields if name in kwargs])

        for name in self.required:
            if name not in kwargs:
                raise ValueError(f"Field {name} required")

        for name, required in self.required_together.items():
            if name in present_fields:
                if not all([r in present_fields for r in required]):
                    raise ValueError(f"When supplying {name}, you must also supply " + (', '.join(required)))

        for name, excluded in self.mutually_exclusive.items():
            if name in present_fields:
                if any([e in present_fields for e in excluded]):
                    raise ValueError(f"When supplying {name}, you may not also supply " + (', '.join(excluded)))

        # data
        for name, config in self.fields.items():
            (code, width, required_type, required, pad) = config
            if name not in kwargs:
                if required:
                    raise KeyError(name)
            else:
                value = kwargs[name]
                if type(value) != required_type:
                    if required_type == Decimal and type(value) == int:
                        value = Decimal(value)
                    elif required_type == str and type(value) == int:
                        value = str(value)
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
