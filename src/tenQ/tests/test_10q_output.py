import unittest
from datetime import datetime, timezone
from tenQ.writer import TenQTransactionWriter


class OutputTest(unittest.TestCase):

    def setUp(self):
        self.transaction_writer = TenQTransactionWriter(
            due_date=datetime(2022, 2, 18, 12, 4, 14, tzinfo=timezone.utc),
            year=2022,
            timestamp=datetime(2022, 2, 18, 12, 35, 57, tzinfo=timezone.utc)
        )

    def test_writer_successful(self):
        prisme10Q_content = self.transaction_writer.serialize_transaction(
            cpr_nummer='1234567890',
            amount_in_dkk=1000,
            afstem_noegle='e688d6a6fc65424483819520bbbe7745',
            rate_text='Testing\r\nwith\r\nlines',
            leverandoer_ident='10Q',
        )
        self.assertEqual(
            prisme10Q_content,
            '\r\n'.join([
                ' 10Q100202202181235090002220920221234567890001234567890',
                ' 10Q24020220218123509000222092022123456789000209990000100000+10000000000+'
                '120220620202202182022062020220620000                                       '
                '202202182022010120221231                                                   '
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
            'leverandoer_ident': 'test'
        }
        too_long = {
            'cpr_nummer': '12345678901',
            'amount_in_dkk': 1000000000,
            'afstem_noegle': 'e688d6a6fc65424483819520bbbe7745xxxx',
            'leverandoer_ident': 'Too long'
        }
        for key, value in too_long.items():
            with self.assertRaises(ValueError):
                self.transaction_writer.serialize_transaction(**{
                    **defaults,
                    key: value,
                })
