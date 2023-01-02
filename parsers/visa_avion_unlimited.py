from datetime import datetime
from decimal import Decimal
from typing import Tuple

from parsers.common import Parser
from parsers.expense import Expense

import calendar
import re

month_names = '|'.join(calendar.month_abbr[m].upper() for m in range(1, 13))
date_regex_pattern = r'^((%s) (\d+))' % month_names
date_regex = re.compile(date_regex_pattern)

# dollar_regex_pattern = r'-?(\d{1,3}(,\d{3})+|\d+)(\.(\d{2}))'
dollar_regex_pattern = r'\$((\d{1,3},?)+(\.\d{2}))$'
dollar_regex = re.compile(dollar_regex_pattern)


class VISAAvionUnlimited(Parser):
    """
    Parser for VISA Statements

    """

    @property
    def start_of_items(self):
        return 'TRANSACTION POSTINGACTIVITY DESCRIPTION AMOUNT ($)DATE DATE'

    def process_page_lines(self, line_items: list[str], previous_line_item=''):
        """
        Parse the extracted data

        """

        def get_next_line(line_iterable):
            try:
                return next(line_iterable)
            except StopIteration:
                return None

        found_start = False

        # line_items = [i for i in line_items if not i.startswith('Foreign Currency')]

        processed_lines = []
        processed_nsfs = []

        line_number = 1
        line_items_itr = iter(line_items)
        line_item = next(line_items_itr)
        previous_line_item = ''
        while line_item is not None:

            if line_item == self.start_of_items:
                self.debug(f'[green]found header on line #{line_number}[/green]')
                found_start = True
                line_number += 1
                line_item = get_next_line(line_items_itr)
                continue

            if not found_start:
                line_number += 1
                line_item = get_next_line(line_items_itr)
                continue

            self.debug(f'[yellow]{line_number:3d}[/yellow]: [grey58]{line_item}[/grey58]')

            current_date = ''
            if found_start:
                expense = self.process_line(line_number, line_item, previous_line_item)
                previous_line_item = line_item
                if expense is None:
                    line_number += 1
                    line_item = get_next_line(line_items_itr)
                    continue

                if expense.date:
                    current_date = expense.date
                else:
                    expense.date = current_date

                # Check expense line for the amount
                # eg APR 27 APR 27 OVERLIMIT FEE $29.00

                # We found an expense, try to find the dollar amount
                if len(expense.line) > 0:
                    found_amount = False
                    amount_lines_processed = 1
                    while not found_amount and amount_lines_processed <= 2:
                        next_line = get_next_line(line_items_itr)
                        self.debug(
                            f'[purple]{line_number + amount_lines_processed:3d}[/purple]: [grey58]{next_line}[/grey58]'
                        )
                        match = dollar_regex.search(next_line)

                        if match is not None:
                            expense.amount = Decimal(match.groups()[0].replace(',', ''))
                            found_amount = True
                            break

                        amount_lines_processed += 1

                    if not found_amount:
                        raise ValueError(f'could not find amount for expense on line {line_number}')

                    line_number += amount_lines_processed
                    processed_lines.append(expense)

            line_item = get_next_line(line_items_itr)
            line_number += 1

        return processed_lines, processed_nsfs, previous_line_item

    def process_line(self, line_number: int, line: str, previous_line: str) -> [Tuple, None]:
        """
        Process the current line

        Args:
            line_number: The line number in the statement
            line: The expense line in the statement
            previous_line: The previous line

        """
        # Check if the date is specified
        date_match = date_regex.search(line)
        if date_match is not None:
            date_parts = date_match.groups()
            new_date_string = f'{date_parts[2]} {date_parts[1].capitalize()}'
            new_date = datetime.strptime(f'{new_date_string} {self.current_year}', '%d %b %Y').date()
            self.current_date = new_date

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

        result = Expense(
            date=self.current_date,
        )

        # Check if the line is one we care about
        for category_pattern in self.categories:
            if category_pattern in line:
                page, category, friendly_name = self.categories[category_pattern]
                self.debug(f'{line_number:3d}: "{line}" matches category {category_pattern}')
                result.page = page
                result.category = category
                result.line = line[14:]
                result.line = friendly_name
                result.line_number = line_number

                return result

        return None
