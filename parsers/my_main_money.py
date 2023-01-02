from datetime import datetime
from decimal import Decimal
from typing import Tuple

from parsers.common import Parser
from parsers.expense import Expense
from parsers.nsf import NSF

import calendar
import re

month_names = '|'.join(calendar.month_abbr[m] for m in range(1, 13))
date_regex_pattern = r'(^\d+ (%s))' % month_names
date_regex = re.compile(date_regex_pattern)

# dollar_regex_pattern = r'-?(\d{1,3}(,\d{3})+|\d+)(\.(\d{2}))'
dollar_regex_pattern = r'((\d{1,3},?)+(\.\d{2}))'
dollar_regex = re.compile(dollar_regex_pattern)

visa_debit_regex_pattern = r'Visa Debit (purchase|correction|refund) - (\d+)'
visa_debit_regex = re.compile(visa_debit_regex_pattern)

nsf_regex_pattern = r'Item returned NSF ((\d{1,3},?)+(\.\d{2}))'
nsf_regex = re.compile(nsf_regex_pattern)

unreported_pages = [
    'Ignore',
    'Food'
]


class MyMainMoney(Parser):
    """
    Parser for My Main Money Account Statements

    """

    @property
    def start_of_items(self):
        return 'Date Description Withdrawals ($) Deposits ($) Balance ($)'

    def process_line(self, line_number: int, line: str, previous_line: str) -> [Tuple, None]:
        """
        Process the current line

        Args:
            line_number: The line number in the statement
            line: The expense line in the statement
            previous_line: The previous line

        """
        # Check if the date is specified and handle that
        date_match = date_regex.match(line)
        if date_match is not None:
            new_date_string = date_match.groups()[0]
            new_date = datetime.strptime(f'{new_date_string} {self.current_year}', '%d %b %Y').date()
            self.debug(
                f'[cornflower_blue]{line_number:3d}: changing current date from "{self.current_date}" to "{new_date}"[/cornflower_blue]'
            )

            # Handle statements that start in Dec of the previous year
            if self.current_date is None and new_date.month == 12:
                new_year = self.current_year - 1
                self.debug(
                    f'[royal_blue1]{line_number:3d}: changing current year from "{self.current_year}" to "{new_year}"[/royal_blue1]'
                )
                self.current_year = new_year

            # Handle statements spanning more than one year after the start
            if self.current_date is not None and self.current_date.month == 12 and new_date.month == 1:
                new_year = self.current_year + 1
                self.debug(
                    f'[royal_blue1]{line_number:3d}: changing current year from "{self.current_year}" to "{new_year}"[/royal_blue1]'
                )
                self.current_year = new_year

            self.current_date = new_date

        nsf_match = nsf_regex.match(line)
        if nsf_match is not None:
            processing_result = NSF(
                date=self.current_date
            )
            amount = nsf_match.groups()[0]
            processing_result.amount = Decimal(amount.replace(',', ''))
            self.debug(f'[yellow]NSF Item {amount} returned: "{line}"[/yellow]')

            return processing_result

        processing_result = Expense(
            date=self.current_date
        )

        # We have to do some special handling for VISA virtual debits because they correct USD amounts
        # We check the previous line to see if it was a Virtual Debit header and deal with it
        visa_debit_match = visa_debit_regex.search(previous_line)
        if visa_debit_match is not None:
            # self.debug(f'[purple]previous line:[/purple] [white]"{previous_line}"[/white]')
            mode, purchase_id = visa_debit_match.groups()
            if mode == 'correction':
                self.debug(f'[orange_red1]adding correction for {purchase_id}[/orange_red1]')
                processing_result.reversal = True
            elif mode == 'refund':
                self.debug(f'[orange_red1]adding refund for {purchase_id}[/orange_red1]')
                processing_result.reversal = True
            else:
                self.debug(f'[orange_red1]adding purchase {purchase_id}[/orange_red1]')

            processing_result.visa_debit_id = purchase_id

        # Check if the line is one we care about
        for category_pattern in self.categories:
            if category_pattern in line:
                page, category, friendly_name = self.categories[category_pattern]
                if page not in unreported_pages:
                    self.debug(f'"{line}" matches category {category_pattern}')

                processing_result.page = page
                processing_result.category = category
                dollar_match = dollar_regex.search(line)
                if dollar_match is None:
                    raise ValueError(f'could not find amount in: "{line}"')
                amount = dollar_match.groups()[0]
                processing_result.amount = Decimal(amount.replace(',', ''))
                line_without_interact = re.sub(r'^Interac purchase - \d+\s', '', line[0:dollar_match.span()[0] - 1])
                line_without_date = date_regex.sub('', line_without_interact)
                processing_result.line = line_without_date.strip()
                processing_result.line = friendly_name
                break
        else:
            return None

        return processing_result
