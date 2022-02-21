# Utility module containing date calculation methods for the 10Q format

from datetime import date, timedelta


# Dates for final statements and their charges are defined by law. This
# module contains methods that makes it easy to calculate the dates correctly
# given a reference input date.

# Due date is defined as 1st of next month plus 3 months relative to the
# reference date. Here it is calculated by taking the first of the reference
# month and adding four months.
def get_due_date(reference_date: date):

    # Our resulting day should always be the 1st
    due_date = reference_date.replace(day=1)

    # always add 4 months so we get "first of next month + 3 months"
    add_months = 4

    # Add months, making sure to adjust year as neccessary
    if due_date.month+add_months <= 12:
        due_date = due_date.replace(month=due_date.month+add_months)
    else:
        due_date = due_date.replace(year=due_date.year+1, month=due_date.month+add_months-12)

    # Create the target date, but with the same time input as the reference
    # datetime.
    return date(
        year=due_date.year,
        month=due_date.month,
        day=due_date.day,
    )


# Last payment date is the first workday on or after the 20th in the same month
# as the due date.
def get_last_payment_date_from_due_date(due_date: date):
    # Always the 20th of same month
    result = due_date.replace(day=20)

    # Cannot pay on saturday on sunday, so add the needed days to
    # get to monday, if neccessary.
    if result.weekday() in (5, 6):
        missing_days = 7 - result.weekday()
        result += timedelta(days=missing_days)

    return result


def get_last_payment_date(reference_date: date):
    return get_last_payment_date_from_due_date(
        get_due_date(reference_date)
    )
