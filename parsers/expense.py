import datetime
from decimal import Decimal


class Expense:
    """
    An Expense

    """
    date: datetime.date
    page: str = ''
    category: str = ''
    amount: Decimal = Decimal(0)
    line_number: int = 0
    line: str = ''
    visa_debit_id: str = None
    reversal: bool = False

    def __init__(self, date: datetime.date):
        """
        Initialize the Expense

        Args:
            date: Must provide a date

        """
        self.date = date

    def __str__(self):
        """
        String representation of this expense

        """
        return f'Expense {self.date.isoformat()} {self.line} ({"-" if self.reversal else ""}{self.amount})'

    def __repr__(self):
        """
        Representation of this expense

        """
        return f'''<Expense date={self.date.isoformat()}, line="{self.line}", amount={self.amount}>'''
