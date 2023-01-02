import datetime

import PyPDF2

from abc import ABC, abstractmethod
from rich import print as rprint
from rich.text import Text, Style

from parsers.nsf import NSF


class Parser(ABC):
    """
    Common Parser Methods

    """
    current_date = None
    current_year: int = None

    def __init__(self, categories, options, start_date: datetime.date):
        """
        Parser initializer

        Args:
            categories: The categories to apply
            options: The application options
            start_date: The start date of the statement

        """
        self.categories = categories
        self.options = options
        self.start_date = start_date
        self.current_year = start_date.year

    @property
    @abstractmethod
    def start_of_items(self):
        pass

    def debug(self, message: [str, Text]):
        """
        Display a debug message

        Args:
            message:

        """
        if self.options.verbose:
            rprint(message)

    def process_page_lines(self, line_items, previous_line_item=''):
        """
        Parse the extracted data

        """
        found_start = False

        processed_expenses = []
        processed_nsfs = []
        for line_number, line_item in enumerate(line_items, start=1):
            if line_item == self.start_of_items:
                self.debug(f'[green]found header on line #{line_number}[/green]')
                found_start = True
                continue

            if not found_start:
                continue

            self.debug(f'[yellow4]{line_number:3d}[/yellow4]: [grey58]{line_item}[/grey58]')

            current_date = ''
            if found_start:
                processed_item = self.process_line(line_number, line_item, previous_line_item)
                previous_line_item = line_item

                if processed_item is None:
                    continue

                if processed_item.date:
                    current_date = processed_item.date
                else:
                    processed_item.year = self.current_year
                    processed_item.date = f'{current_date}'

                if isinstance(processed_item, NSF):
                    processed_nsfs.append(processed_item)
                elif len(processed_item.line) > 0:
                    processed_expenses.append(processed_item)

        return processed_expenses, processed_nsfs, previous_line_item

    def process_page(self, page_number, page: PyPDF2.PageObject, previous_page_last_line):
        """
        Process a page from the statement

        """
        self.debug(Text(f'Processing page {page_number + 1}{" " * 79}', style=Style(bgcolor='blue_violet')))
        line_items = page.extract_text().splitlines()

        return self.process_page_lines(line_items, previous_page_last_line)

    @abstractmethod
    def process_line(self, line_number: int, line_item: str, previous_line: str):
        """
        Process a line item from a statement

        Args:
            line_number: The line number of the page
            line_item: The line to process
            previous_line: The previous line

        """
