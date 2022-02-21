import unittest
from datetime import date

from tenQ.dates import get_due_date, get_last_payment_date, get_last_payment_date_from_due_date


class Test10QDateCalculation(unittest.TestCase):
    # Test data in format:
    #   '<reference_date>': ('collect_date', 'last_payment_date')
    #
    # Rule for due date is "first day of next month plus 3 months".
    #
    # Rule for last payment date is first workday on or after the
    # 20th of the same month as the due date.
    #
    test_data = {
        # First of a month, non-dst => dst
        '2020-01-01': ('2020-05-01', '2020-05-20'),

        # Not first of a month
        '2020-01-02': ('2020-05-01', '2020-05-20'),

        # feb 29th in a leap year, skip saturday => monday
        '2020-02-29': ('2020-06-01', '2020-06-22'),

        # feb 28th in a non leap year, skip sunday => monday
        '2021-02-28': ('2021-06-01', '2021-06-21'),

        # Wrapping around end-of-year
        '2020-12-30': ('2021-04-01', '2021-04-20'),

        # dst => non-dst
        '2020-07-05': ('2020-11-01', '2020-11-20'),
    }

    def test_10q_dates(self):
        for ref_date_str, target_dates in self.test_data.items():
            due_date_str, last_payment_date_str = target_dates

            ref_date = date.fromisoformat(ref_date_str)
            due_date = date.fromisoformat(due_date_str)
            last_payment_date = date.fromisoformat(last_payment_date_str)

            calculated_due_date = get_due_date(ref_date)
            calculated_lpd = get_last_payment_date(ref_date)
            calculated_lpd2 = get_last_payment_date_from_due_date(calculated_due_date)

            self.assertEqual(
                calculated_due_date, due_date,
                'Ref date %s: Calculated due date correct' % ref_date.isoformat()
            )
            self.assertEqual(
                calculated_lpd, last_payment_date,
                'Ref date %s: Calculated last payment date correct' % ref_date.isoformat()
            )
            self.assertEqual(
                calculated_lpd, calculated_lpd2,
                'Ref date %s: Last payment date is the same when calculated '
                'from ref date and due date' % ref_date.isoformat()
            )
