# SPDX-FileCopyrightText: 2024 Magenta ApS <info@magenta.dk>
#
# SPDX-License-Identifier: MPL-2.0

from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal


class G69TransactionWriter(object):
    """
    Writer for G69 transactions
    See doc at https://aka.nanoq.gl/etaxOIO/FileFormats/Prisme/G69.aspx
    """

    alphanum = 1
    numeric = 2
    amount = 3
    fields = OrderedDict(
        {
            # name: (id, width, type, required, pad)
            "kaldenavn": (101, 10, str, False, False),
            "afstemningsenhed": (102, 5, str, False, False),
            "maskinnr": (103, 5, int, True, True),
            "eks_løbenr": (104, 7, int, True, True),
            "post_dato": (110, 8, date, True, True),
            "kontonr": (111, 40, int, True, 15),
            "beløb": (112, 13, Decimal, True, True),
            "deb_kred": (113, 1, str, True, False),
            "regnskabsår": (114, 4, int, False, True),
            "bilag_arkiv_nr": (116, 255, str, False, False),
            "udbet_henv_nr": (117, 20, int, False, False),
            "valør_dato": (118, 8, date, False, False),
            "betaling_modtager_nrkode": (130, 2, int, False, True),
            "betaling_modtager": (131, 10, int, False, True),
            "ydelse_modtager_nrkode": (132, 2, int, False, True),
            "ydelse_modtager": (133, 10, str, False, False),
            "oplysningspligtig_nrkode": (134, 2, int, False, True),
            "oplysningspligtig": (135, 10, int, False, True),
            "oplysningspligt_kode": (136, 1, str, False, False),
            "postering_udtrækstekst_1": (150, 5, str, False, False),
            "postering_udtrækstekst_2": (151, 5, str, False, False),
            "postering_udtrækskode": (152, 5, str, False, False),
            "posteringstekst": (153, 35, str, False, False),
            "rekvisitionsnr": (170, 10, int, False, True),
            "delleverance": (171, 1, str, False, False),
            "bærer": (180, 10, str, False, False),
            "afdeling": (181, 10, str, False, False),
            "formål": (182, 10, str, False, False),
            "omvendt_betalingspligt": (185, 2, int, False, True),
            "kontering_fakturapulje": (200, 1, str, False, False),
            "konteret_af": (201, 5, str, False, False),
            "notat_short": (202, 200, str, False, False),
            "attesteret_af": (203, 5, str, False, False),
            "emne": (210, 60, str, False, False),
            "notat_long": (211, 1024, str, False, False),
            "ekstern_reference": (250, 20, str, False, False),
            "iris_nr": (251, 20, str, False, False),
            "projekt_nr": (300, 20, str, False, False),
            "projekt_art": (301, 10, str, False, False),
            "prisme_medarbejder": (302, 10, str, False, False),
            "salgspris": (303, 13, Decimal, False, False),
            "antal": (304, 10, Decimal, False, False),
            "linje_egenskab": (305, 10, str, False, False),
            "aktivitet_nr": (306, 10, str, False, False),
        }
    )

    # Set of required codes
    required = set([name for name, config in fields.items() if config[3]])

    # mapping of codes with other codes that they require
    # (if ydelse_modtager_nrkode is set, ydelse_modtager must be as well)
    required_together = {
        "ydelse_modtager_nrkode": ("ydelse_modtager",),
        "ydelse_modtager": ("ydelse_modtager_nrkode",),
        "rekvisitionsnr": ("delleverance",),
        "delleverance": ("rekvisitionsnr",),
        "emne": ("notat_long",),
        "notat_long": ("emne",),
        "projekt_nr": ("projekt_art", "antal"),
        "projekt_art": ("projekt_nr", "antal"),
        "prisme_medarbejder": ("projekt_nr", "projekt_art", "antal"),
        "salgspris": ("projekt_nr", "projekt_art", "antal"),
        "antal": ("projekt_nr", "projekt_art"),
        "linje_egenskab": ("projekt_nr", "projekt_art", "antal"),
        "aktivitet_nr": ("projekt_nr", "projekt_art", "antal"),
    }

    # mapping of codes that may not be present together
    # (if emne is present, neither bilag_arkiv_nr or kontering_fakturapulje may be)
    mutually_exclusive = {
        "emne": ("bilag_arkiv_nr", "kontering_fakturapulje"),
        "notat_long": ("bilag_arkiv_nr", "kontering_fakturapulje"),
    }

    # shorthands; it's easier to remember and provide
    # is_cvr=True than ydelse_modtager_nrkode=3
    aliases = {
        "is_cvr": {"field": "ydelse_modtager_nrkode", "map": {False: 2, True: 3}},
        "is_kontering_fakturapulje": {
            "field": "kontering_fakturapulje",
            map: {False: "N", True: "J"},
        },
        "is_debet": {"field": "deb_kred", "map": {False: "K", True: "D"}},
        "is_kredit": {"field": "deb_kred", "map": {False: "D", True: "K"}},
    }

    registreringssted = 0
    snitfladetype = "G69"
    organisationsenhed = 0
    organisationstype = 1
    linjeformat = "FLYD"

    def __init__(self, registreringssted: int, organisationsenhed: int):
        self.registreringssted = registreringssted
        self.organisationsenhed = organisationsenhed

        # Line number in the file; successive calls to serialize_transaction increment this.
        # Be sure to use a new G69TransactionWriter or reset the line number when writing a new file
        self.line_number = 1

    def reset_line_number(self):
        self.line_number = 1

    def serialize_transaction(self, post_type: str = "NOR", **kwargs):
        output = []
        post_type = post_type.upper()
        if post_type not in ("NOR", "PRI", "SUP"):
            raise ValueError("post_type must be NOR, PRI or SUP")

        for alias, config in self.aliases.items():
            if alias in kwargs:
                name = config["field"]
                if kwargs[alias] in config["map"]:
                    kwargs[name] = config["map"][kwargs[alias]]

        # Header
        output.append(
            "".join(
                [
                    str(self.registreringssted).rjust(3, "0"),
                    self.snitfladetype,
                    str(self.line_number).rjust(5, "0"),
                    str(self.organisationsenhed).rjust(4, "0"),
                    str(self.organisationstype).rjust(2, "0"),
                    post_type,
                    self.linjeformat,
                ]
            )
        )

        present_fields = set([name for name in self.fields if name in kwargs])

        for name in self.required:
            if name not in kwargs:
                raise ValueError(f"Field {name} required")

        for name, required in self.required_together.items():
            if name in present_fields:
                if not all([r in present_fields for r in required]):
                    raise ValueError(
                        f"When supplying {name}, you must also supply "
                        + (", ".join(required))
                    )

        for name, excluded in self.mutually_exclusive.items():
            if name in present_fields:
                if any([e in present_fields for e in excluded]):
                    raise ValueError(
                        f"When supplying {name}, you may not also supply "
                        + (", ".join(excluded))
                    )

        # data
        for name, config in self.fields.items():
            (code, width, required_type, required, pad) = config
            if name not in kwargs:
                if required:
                    raise KeyError(name)
            else:
                value = kwargs[name]
                if not isinstance(value, required_type):
                    if required_type is Decimal and isinstance(value, int):
                        value = Decimal(value)
                    elif required_type is str and isinstance(value, int):
                        value = str(value)
                    else:
                        raise ValueError(
                            f"{name}={value} must be of type {required_type}"
                        )
                if required_type == int:
                    value = G69TransactionWriter.format_nummer(value)
                elif required_type == date:
                    value = G69TransactionWriter.format_date(value)
                elif required_type == Decimal:
                    value = G69TransactionWriter.format_amount_kr(value)
                else:
                    value = str(value)
                if "&" in value:
                    raise ValueError(f"Value {name}={value} may not contain &")
                if len(value) > width:
                    raise ValueError(
                        f"Value {name}={value} may not exceed length {width}"
                    )
                if pad:
                    if isinstance(pad, bool):
                        # `pad` is True - use `width` to set the padding
                        value = value.rjust(width, "0")
                    else:
                        # `pad` is an int - use `pad` to set the padding
                        value = value.rjust(pad, "0")
                code = str(code).rjust(3, "0")
                output.append(f"{code}{value}")
        self.line_number += 1
        return "&".join(output)

    def serialize_transaction_pair(self, post_type: str = "NOR", **kwargs):
        return "\r\n".join(
            [
                self.serialize_transaction(post_type, **{**kwargs, "is_debet": debet})
                for debet in (True, False)
            ]
        )

    @staticmethod
    def format_timestamp(dt: datetime):
        return "{:0%Y%m%d%H%M}".format(dt)

    @staticmethod
    def format_date(d: date):
        return "{:%Y%m%d}".format(d)

    @staticmethod
    def format_omraade_nummer(year):
        return str(year)[1:]

    @staticmethod
    def format_amount_øre(amount):
        return str(abs(amount)) + ("-" if amount < 0 else " ")

    @staticmethod
    def format_amount_kr(amount: Decimal):
        return G69TransactionWriter.format_amount_øre(int(amount * 100))

    @staticmethod
    def format_nummer(nummer):
        return str(nummer)
