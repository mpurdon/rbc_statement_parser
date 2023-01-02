import datetime
from decimal import Decimal


class NSF:
    """
    An Expense that was returned NSF

    """
    date: datetime.date
    page: str = ''
    category: str = ''
    amount: Decimal = Decimal(0)
    line_number: int = 0
    line: str = ''

    def __init__(self, date: datetime.date):
        """
        Initialize the NSFd Expense

        Args:
            date: Must provide a date

        """
        self.date = date

    def __str__(self):
        """
        String representation of this NSFd expense

        """
        return f'NSF {self.date.isoformat()} {self.line} ({self.amount})'

    def __repr__(self):
        """
        Representation of this NSFd expense

        """
        return f'''<NSF date={self.date.isoformat()}, line="{self.line}", amount={self.amount}>'''
