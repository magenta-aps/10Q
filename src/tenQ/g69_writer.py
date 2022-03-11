from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal


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
        'is_kontering_fakturapulje': {'field': 200, map: {False: 'N', True: 'J'}}
    }

    registreringssted = 0
    snitfladetype = 'G69'
    organisationsenhed = 0
    organisationstype = 1
    linjeformat = 'FLYD'
    line_number = 1  # Line number in the file; successive calls to serialize_transaction increment this.
                     # Be sure to use a new G69TransactionWriter or reset the line number when writing a new file

    def __init__(self, registreringssted: int, organisationsenhed: int):
        self.registreringssted = registreringssted
        self.organisationsenhed = organisationsenhed

    def reset_line_number(self):
        self.line_number = 1

    def serialize_transaction(self, post_type, **kwargs):
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
            str(self.registreringssted).rjust(3, '0') +
            self.snitfladetype +
            str(self.line_number).rjust(5, '0') +
            str(self.organisationsenhed).rjust(4, '0') +
            str(self.organisationstype).rjust(2, '0') +
            post_type +
            self.linjeformat
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
                    raise ValueError(
                        f"When supplying {self.fields[key][0]}, you must also supply " +
                        (', '.join([f'"{self.fields[r][0]}"' for r in required]))
                    )

        for key, excluded in self.mutually_exclusive.items():
            if key in present_fields:
                if any([e in present_fields for e in excluded]):
                    raise ValueError(
                        f"When supplying {self.fields[key][0]}, you may not also supply " +
                        (', '.join([f'"{self.fields[e][0]}"' for e in excluded]))
                    )

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

    def serialize_transaction_pair(self, post_type, **kwargs):
        for dk in ('D', 'K'):
            kwargs.update({'deb_kred': dk})
            self.serialize_transaction(post_type, **kwargs)

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
