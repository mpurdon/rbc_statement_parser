# Royal Bank Statement Parser

Parses Royal Bank of Canada™ bank statements and compiles expenses from them.

## Running the Script

Enable the poetry virtual environment:

```shell
poetry shell
```

Run the script,

```shell
./main.py --help
```

You should see output similar to:

```shell
 Usage: main.py [OPTIONS] COMMAND [ARGS]...

╭─ Options ─────────────────────────────────────────────────────────────────────────────────╮
│ --verbose    --no-verbose      [default: no-verbose]                                      │
│ --dry-run    --no-dry-run      [default: no-dry-run]                                      │
│ --help                         Show this message and exit.                                │
╰───────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ────────────────────────────────────────────────────────────────────────────────╮
│ export                         Export a report for the given statement files              │
│ list-categories                List all configured categories                             │
│ list-files                     List the available statements                              │
│ process                        Process the statement files                                │
│ report                         Generate a report for the given statement files            │
╰───────────────────────────────────────────────────────────────────────────────────────────╯

```

## Configuration
Configuration for the parser categories should be placed in the root folder as `categories.json`, you can find an example here:

https://gist.github.com/mpurdon/f52ae8216d1ec851873abacea047720f

## To Do Items

### Handle NSF Items

When an NSF item is found, pop the previous expense off the list. NSF items look similar to this:

```text
"2020-02-12"
Item returned NSF 224.19 - 306.33
Utility Bill Pmt Enbridge Gas 224.19
```

## Handle NSF fees

When several NSF fees are processed at the same time, they stack. Multiple NSF fees look like this:

```text
NSF item fee 2 @ $45.00 90.00 1,089.50
```

## Handle Credit Card Over Limit Fees

When a purchase goes over the limit, a fee is applied. This expense line is different from the rest in that it has the
amount on the same line. Over limit fees look like this:

```text
JAN 28 JAN 28 OVERLIMIT FEE $29.00
```
