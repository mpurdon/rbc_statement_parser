#!/usr/bin/env python3
import datetime
import json
import os
import pathlib
import calendar
from dataclasses import dataclass
from decimal import Decimal

import natsort
import PyPDF2
import typer
import xlsxwriter

from dotenv import load_dotenv
from rich import print as rprint
from rich.progress import track
from rich.table import Column, Table, Style, Text

from parsers.expense import Expense
from parsers.my_main_money import MyMainMoney
from parsers.visa_avion_unlimited import VISAAvionUnlimited

app = typer.Typer(
    add_completion=False,
    # no_args_is_help=True,
)


@dataclass()
class AppOptions:
    """
    Application Options

    """
    statement_path: str = './statements'
    output_path: str = './output'
    categories_path: str = './categories.json'
    ignored_path: str = './ignored.json'
    verbose: bool = False
    dry_run: bool = False


app_options = AppOptions()

# folder paths
statement_path = pathlib.Path(app_options.statement_path)
output_path = pathlib.Path(app_options.output_path)

categories = {}
ignored = []


def debug(message):
    """
    Print a statement if verbose mode has been set

    """
    global app_options

    if app_options.verbose:
        rprint(message)


def load_ignored(display: bool = False):
    """
    Load the ignored categories

    """
    global ignored

    ignored = []
    debug(f'loading ignored from {app_options.categories_path}')


def load_categories(display: bool = False):
    """
    Load the categories from the config file

    """
    global categories

    categories = {}
    debug(f'loading categories from {app_options.categories_path}')
    table = Table('Page', 'Category', 'Patterns')
    with open(app_options.categories_path) as cf:
        config = json.load(cf)

        last_page = None
        last_category = None
        for page, page_categories in config.items():
            for category, patterns in page_categories.items():
                for pattern, friendly_name in patterns.items():
                    # If we didn't provide a friendly name, just use the pattern
                    if friendly_name is None:
                        friendly_name = pattern

                    add_page = False
                    add_category = False

                    if page is not last_page:
                        last_page = page
                        add_page = True

                    if category is not last_category:
                        last_category = category
                        add_category = True

                    table.add_row(
                        page if add_page else '',
                        category if add_category else '',
                        f'{pattern} ({friendly_name})',
                    )
                    categories[pattern] = (page, category, friendly_name)

    if display:
        rprint(table)


def process_statement(statement: pathlib.Path):
    """
    Process a statement

    Args:
        statement: The statement to parse

    """
    pages_expenses = []
    pages_nsfs = []

    try:
        statement_date = datetime.date.fromisoformat(statement.stem[-10:])
    except ValueError:
        rprint(f'{statement.stem} is not a valid statement file, skipping')
        return pages_expenses, pages_nsfs

    debug(f'statement date: {statement_date}')
    debug(f'processing statement: {statement}')

    statement_parsers = {
        'My Main Money Account': MyMainMoney,
        'VISA Avion Unlimited': VISAAvionUnlimited,
    }

    parser = None
    for statement_name, parser_klass in statement_parsers.items():
        if statement.match(f'*{statement_name}*'):
            app_options.verbose and rprint(f'using parser "{parser_klass.__name__}"')
            parser = parser_klass(categories, options=app_options, start_date=statement_date)

    if parser is None:
        raise ValueError(f'could not find a parser for {statement}')

    with open(statement, 'rb') as f:
        pdf_reader = PyPDF2.PdfFileReader(f)
        debug(f'Pages: {pdf_reader.numPages}')

        previous_page_last_line = ''
        for page_number in range(0, pdf_reader.numPages):
            page = pdf_reader.getPage(page_number)
            expenses, nsfs, previous_page_last_line = parser.process_page(
                page_number,
                page,
                previous_page_last_line
            )
            pages_expenses.extend(expenses)
            pages_nsfs.extend(nsfs)

    return pages_expenses, pages_nsfs


def process_statements():
    """
    Process the statements in the configured path

    """
    rprint(f'processing [yellow]{statement_path}[/yellow] and outputting to [yellow]{output_path}[/yellow]')
    statement_items = track(
        natsort.natsorted(statement_path.iterdir()),
        description='Processing Statements...',
        auto_refresh=False,
        transient=True
    )

    all_expenses = []
    all_nsfs = []

    for path_item in statement_items:
        if path_item.is_file():
            statement_expenses, statement_nsfs = process_statement(path_item)
            all_expenses.extend(statement_expenses)
            all_nsfs.extend(statement_nsfs)

    return all_expenses, all_nsfs


@app.callback(invoke_without_command=True)
def main(verbose: bool = False, dry_run: bool = False):
    """
    Process the statements

    Args:
        verbose: Should the program output verbose messages
        dry_run: Should the program not make any changes (readonly)

    """
    # Copy options to global options
    app_options.verbose = verbose
    app_options.dry_run = dry_run

    loaded = load_dotenv()
    if not loaded:
        raise RuntimeError('could not load environment file')

    app_options.statement_path = os.environ.get('STATEMENT_DIR')
    app_options.output_path = os.environ.get('OUTPUT_DIR')


@app.command()
def list_categories():
    """
    List all configured categories

    """
    load_categories(display=True)


@app.command()
def list_files():
    """
    List the available statements

    """
    debug(f'looking for statements in {statement_path}')
    table = Table('Statement', title='Statements')
    for entry in natsort.natsorted(statement_path.iterdir()):
        if entry.is_file():
            table.add_row(entry.name)

    rprint(table)


def display_expenses(expenses: list[Expense]):
    """
    Display the list of expenses

    Args:
        expenses:

    """
    table = Table(
        'Date',
        'Page',
        'Category',
        'Expense',
        Column(header='Amount', justify='right'),
        title='Statements'
    )

    for expense in sorted(expenses, key=lambda e: e.date):
        table.add_row(
            expense.date.isoformat(),
            expense.page,
            expense.category,
            expense.line,
            expense.amount.to_eng_string(),
        )

    rprint(table)


def filter_visa_debit_corrections(expenses: list[Expense]):
    """
    Remove corrected VISA virtual debit™ expenses

    """
    debug(f'filtering {len(expenses)} expenses')

    virtual_debit_map = {}
    for index, expense in enumerate(expenses):
        if expense.visa_debit_id is not None:
            if expense.visa_debit_id in virtual_debit_map:
                debug(f'removing corrected expense {expense} ')
                # @ToDo: this can't be efficient ...
                try:
                    expenses.remove(virtual_debit_map[expense.visa_debit_id])
                    expenses.remove(expense)
                except ValueError as e:
                    debug(f'[red]{e}[/red]')
                continue

            debug(f'adding {expense} to map')
            virtual_debit_map[expense.visa_debit_id] = expense

    debug(f'{len(expenses)} expenses remain after filtering')
    return expenses


def generate_report(expenses: list[Expense]):
    """
    Generate an Expense report grouped by Year, Page and Category

    """
    report = {}

    for expense in expenses:
        if expense.date.year not in report:
            report[expense.date.year] = {}

        if expense.page not in report[expense.date.year]:
            report[expense.date.year][expense.page] = {}

        if expense.category not in report[expense.date.year][expense.page]:
            report[expense.date.year][expense.page][expense.category] = []

        report[expense.date.year][expense.page][expense.category].append(expense)

    return report


def display_report(report_data):
    """
    Display the generated report

    """
    monthly_pages = [
        'Housing and Utilities',
    ]

    totals = {}
    table = Table(
        'Year',
        'Page',
        'Category',
        'Vendor',
        'Date',
        Column(header='Amount', justify='right'),
        title='Business Expenses'
    )
    for year, pages in report_data.items():
        table.add_row(
            str(year),
            style=Style(
                bgcolor='blue'
            )
        )
        for page, page_categories in pages.items():
            if page in monthly_pages:
                continue

            table.add_row(
                '',
                page,
            )

            for category, items in page_categories.items():

                if category != '':
                    table.add_row(
                        '',
                        '',
                        category,
                    )
                for item in sorted(items, key=lambda i: i.date):
                    assert isinstance(item, Expense)
                    table.add_row('', '', '', item.line, item.date.isoformat(), item.amount.to_eng_string())
                    if year not in totals:
                        totals[year] = {}
                    if page not in totals[year]:
                        totals[year][page] = {}
                    if category not in totals[year][page]:
                        totals[year][page][category] = Decimal(0)
                    totals[year][page][category] += item.amount
                # Add the total for the category
                table.add_row(
                    '',
                    '',
                    '',
                    '',
                    Text(
                        'Total',
                        justify='right',
                        style=Style(
                            color='grey53',
                        )
                    ),
                    Text(
                        totals[year][page][category].to_eng_string(),
                        style=Style(
                            color='grey53',
                        )
                    ),
                )

    rprint(table)

    # Collect Monthly Expenses
    monthly_expenses = {}

    totals = {}

    for year, pages in report_data.items():
        for page, page_categories in pages.items():
            if page not in monthly_pages:
                continue
            for category, items in page_categories.items():
                for item in items:
                    assert isinstance(item, Expense)
                    if year not in totals:
                        totals[year] = {}
                    if page not in totals[year]:
                        totals[year][page] = {}
                    if category not in totals[year][page]:
                        totals[year][page][category] = {}
                    if item.line not in totals[year][page][category]:
                        totals[year][page][category][item.line] = {}
                    if item.date.month not in totals[year][page][category][item.line]:
                        totals[year][page][category][item.line][item.date.month] = [
                            item.amount.to_eng_string()
                        ]
                    else:
                        totals[year][page][category][item.line][item.date.month].append(item.amount.to_eng_string())
                    if 'total' not in totals[year][page][category][item.line]:
                        totals[year][page][category][item.line]['total'] = Decimal(0)

                    totals[year][page][category][item.line]['total'] += item.amount

    debug(totals)

    month_names = [Column(header=calendar.month_abbr[m], justify='right') for m in range(1, 13)]
    table = Table(
        'Year',
        'Page',
        'Category',
        'Vendor',
        *month_names,
        Column(header='Total', justify='right'),
        title='Monthly Expenses'
    )

    last_year = None
    for year, pages in totals.items():
        if year != last_year:
            table.add_row(
                str(year),
                style=Style(
                    bgcolor='blue'
                )
            )
            last_year = year

        last_page = None
        for page, categories in pages.items():
            if page != last_page:
                table.add_row('', page)
                last_page = last_page

            last_category = None
            for category, vendors in categories.items():
                if category != last_category:
                    table.add_row('', '', category)
                    last_category = category

                for vendor, items in vendors.items():
                    month_amounts = ['---', ] * 12
                    for m in range(1, 13):
                        if m in items:
                            month_amounts[m - 1] = '\n'.join(items[m])

                    table.add_row(
                        '', '', '', vendor,
                        *month_amounts,
                        items['total'].to_eng_string()
                    )

    rprint(table)


def export_report(report_data):
    """
    Export the generated report to excel

    """
    monthly_pages = [
        'Housing and Utilities',
    ]

    month_names = [calendar.month_abbr[m] for m in range(1, 13)]

    totals = {}
    for year, pages in report_data.items():
        workbook = xlsxwriter.Workbook(f'output/{year}-expenses.xlsx')

        header_format = workbook.add_format(
            {
                'bold': True,
                'align': 'center',
            }
        )

        category_format = workbook.add_format(
            {
                'bold': True,
                'bg_color': 'silver',
            }
        )

        vendor_format = workbook.add_format(
            {
                'align': 'right',
            }
        )

        total_format = workbook.add_format(
            {
                'bold': True,
                'align': 'right',
                'num_format': '#,##0.00',
            }
        )

        currency_format = workbook.add_format(
            {
                'align': 'right',
                'valign': 'top',
                # 'num_format': '[$$-409]#,##0.00',
                'num_format': '#,##0.00',
                'text_wrap': True,
            }
        )

        for page, page_categories in pages.items():
            if page in monthly_pages:
                continue

            worksheet = workbook.add_worksheet(page)
            worksheet.set_column(0, 0, 18)
            worksheet.set_column(1, 1, 28, vendor_format)
            worksheet.set_column(1, 2, 36, vendor_format)
            worksheet.set_column(2, 3, 12, currency_format)
            current_row = 0
            worksheet.write_row(current_row, 0, ['Category', 'Vendor', 'Date', 'Amount', ], header_format)
            current_row += 1

            for category, items in page_categories.items():

                if category != '':
                    worksheet.set_row(current_row, cell_format=category_format)
                    worksheet.write(current_row, 0, category)
                    current_row += 1

                for item in sorted(items, key=lambda i: i.date):
                    assert isinstance(item, Expense)
                    worksheet.write_row(current_row, 1, [item.line, item.date.isoformat(), item.amount])
                    current_row += 1

                    if year not in totals:
                        totals[year] = {}
                    if page not in totals[year]:
                        totals[year][page] = {}
                    if category not in totals[year][page]:
                        totals[year][page][category] = Decimal(0)
                    totals[year][page][category] += item.amount

                # Add the total for the category
                worksheet.write_row(
                    current_row, 2, ['Total', totals[year][page][category]], total_format
                )
                current_row += 1

        report_pages = report_data[year]
        report_totals = {}

        debug('processing monthly_pages')
        for report_page, report_page_categories in report_pages.items():
            if report_page not in monthly_pages:
                debug(f'skipping page {report_page}')
                continue
            debug(f'processing page {report_page}')
            for category, items in report_page_categories.items():
                for item in items:
                    assert isinstance(item, Expense)
                    if report_page not in report_totals:
                        report_totals[report_page] = {}
                    if category not in report_totals[report_page]:
                        report_totals[report_page][category] = {}
                    if item.line not in report_totals[report_page][category]:
                        report_totals[report_page][category][item.line] = {}
                    if item.date.month not in report_totals[report_page][category][item.line]:
                        report_totals[report_page][category][item.line][item.date.month] = [
                            item.amount
                        ]
                    else:
                        report_totals[report_page][category][item.line][item.date.month].append(item.amount)
                    if 'total' not in report_totals[report_page][category][item.line]:
                        report_totals[report_page][category][item.line]['total'] = Decimal(0)

                    report_totals[report_page][category][item.line]['total'] += item.amount

        debug('generating monthly expenses')
        for monthly_page, monthly_categories in report_totals.items():
            debug(f'adding page: {monthly_page}')
            worksheet = workbook.add_worksheet(monthly_page)
            worksheet.set_column(0, 0, 18)
            worksheet.set_column(1, 1, 28)
            for c in range(2, 14):
                worksheet.set_column(2, c, 8, currency_format)
            worksheet.set_column(14, 14, 9, total_format)
            current_row = 0
            headers = ['Category', 'Vendor', *month_names, 'Total', ]
            worksheet.write_row(current_row, 0, headers, header_format)
            current_row += 1

            last_category = None
            for category, vendors in monthly_categories.items():
                debug(f'processing {category=}')
                if category != last_category:
                    category_row = [None] * 15
                    category_row[0] = category
                    worksheet.write_row(current_row, 0, category_row, category_format)
                    current_row += 1
                    last_category = category

                for vendor, items in vendors.items():
                    month_amounts = ['---', ] * 12
                    for m in range(1, 13):
                        if m in items:
                            if len(items[m]) == 1:
                                month_amounts[m - 1] = items[m][0]
                            else:
                                month_amounts[m - 1] = '\n'.join(i.to_eng_string() for i in items[m])

                    month_amounts.insert(0, vendor)
                    month_amounts.append(items['total'])
                    worksheet.write_row(current_row, 1, month_amounts, currency_format)
                    current_row += 1

        workbook.close()
        debug(f'saved workbook "{workbook.filename}"')


def get_expenses(statement: str):
    """
    Get the expenses for the given statement(s)

    """
    load_categories()

    if len(statement) == 0:
        statement_expenses, statement_nsfs = process_statements()
    else:
        path_item = pathlib.Path(statement)
        statement_expenses, statement_nsfs = process_statement(path_item)

    # @ToDo Process the NSFs here
    rprint(statement_nsfs)
    return filter_visa_debit_corrections(statement_expenses)


@app.command()
def process(statement: str = ''):
    """
    Process the statement files

    """
    display_expenses(
        get_expenses(statement)
    )


@app.command()
def report(statement: str = ''):
    """
    Generate a report for the given statement files

    """
    display_report(
        generate_report(
            get_expenses(statement)
        )
    )


@app.command()
def export(statement: str = ''):
    """
    Export a report for the given statement files

    """
    export_report(
        generate_report(
            get_expenses(statement)
        )
    )


if __name__ == '__main__':
    app()
