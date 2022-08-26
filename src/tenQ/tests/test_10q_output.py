import unittest
from datetime import date, datetime, timezone, timedelta
from tenQ.writer import TenQTransactionWriter


class OutputTest(unittest.TestCase):

    def setUp(self):
        self.transaction_writers = [
            TenQTransactionWriter(
                leverandoer_ident='10Q',
                creation_date=date(2022, 2, 10),
                due_date=date(2022, 2, 18),
                year=2022,
                timestamp=datetime(2022, 2, 18, 12, 35, 57, tzinfo=timezone.utc),
            ),
            TenQTransactionWriter(
                leverandoer_ident='10Q',
                creation_date=date(2022, 2, 10),
                due_date=date(2022, 2, 18),
                year=2022,
                timestamp=datetime(2022, 2, 18, 12, 35, 57, tzinfo=timezone(timedelta(hours=12))),
            )
        ]

    def test_writer_successful(self):
        for writer in self.transaction_writers:
            prisme10Q_content = writer.serialize_transaction(
                cpr_nummer='1234567890',
                amount_in_dkk=1000,
                afstem_noegle='e688d6a6fc65424483819520bbbe7745',
                rate_text='Testing\r\nwith\r\nlines',
            )
            self.assertEqual(
                prisme10Q_content,
                '\r\n'.join([
                    ' 10Q100202202181235090002220920221234567890001234567890',
                    ' 10Q24020220218123509000222092022123456789000209990000100000+10000000000+'
                    '120220221202202182022022120220221000                                       '
                    '202202102022010120221231                                                   '
                    '                                                        '
                    'e688d6a6fc65424483819520bbbe7745',
                    ' 10Q2602022021812350900022209202212345678900020999000Testing',
                    ' 10Q2602022021812350900022209202212345678900020999001with',
                    ' 10Q2602022021812350900022209202212345678900020999002lines'
                ])
            )

    def test_writer_invalid_input(self):
        defaults = {
            'cpr_nummer': '1234567890',
            'amount_in_dkk': 1000,
            'afstem_noegle': 'e688d6a6fc65424483819520bbbe7745',
            'rate_text': 'hephey',
        }
        too_long = {
            'cpr_nummer': '12345678901',
            'amount_in_dkk': 1000000000,
            'afstem_noegle': 'e688d6a6fc65424483819520bbbe7745xxxx',
        }
        for writer in self.transaction_writers:
            for key, value in too_long.items():
                with self.assertRaises(ValueError):
                    writer.serialize_transaction(**{
                        **defaults,
                        key: value,
                    })
