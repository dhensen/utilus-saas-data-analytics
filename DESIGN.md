# Design

The project is a small `uv`-managed Python CLI. `main.py` handles command-line arguments
and JSON output, `src/loading.py` loads and validates CSV rows, `src/models.py` contains
typed dataclasses, and `src/metrics.py` contains the business metric calculations.

CSV validation is split into two stages. First, Pandera strict schemas validate the file
shape and coerce scalar values such as dates and prices. Rows that pass Pandera become
valid candidates; rejected rows are retained internally for logging. Second,
application-level checks reject rows that need cross-row context, such as duplicate
customer IDs, subscriptions for unknown customers, and subscriptions whose exclusive
`end_date` is not after `start_date`.

Subscriptions are modeled as half-open intervals: `[start_date, end_date)`. Monthly MRR
counts the full monthly price for any subscription overlapping a calendar month. Churn is
counted when a subscription ends and the same customer has no new subscription starting
within 30 days after the exclusive `end_date`, including the 30th day. Cohort retention
groups customers by signup month and checks whether they have any subscription active
exactly three calendar months after signup.

Overlapping subscriptions for the same customer are normalized before metrics are
calculated. If overlapping rows have the same monthly price, they are merged into one
continuous interval. If the later row has a different price, it is treated as a price
change and the earlier interval is shortened to end at the later row's `start_date`.
Keeping `end_date` exclusive makes this adjustment a clean handoff with no double-counted
day.

Adding another metric should only require a new function in `src/metrics.py` and adding
its result to `build_report`. The loader returns clean typed records plus data-quality
details, so metric functions do not need to know about CSV parsing or Pandera failure
formats. The JSON report contains compact data-quality counts; detailed rejected-row
records are logged to stderr or to `--log-file`.

## Failure behavior

Invalid row handling favors producing a partial report over failing the whole run. Bad row
values, duplicate customer IDs, unknown subscription customer IDs, and invalid date ranges
are rejected and logged; the report is still written from the remaining valid records.
Subscription overlap fixes are logged as adjusted rows, not rejected rows.

The CLI exits nonzero only for file-level problems that prevent meaningful validation:
missing files, unparseable CSV input, missing required columns, extra columns, or columns
in the wrong order. Pandera can coerce values inside existing columns, but it cannot infer
or create a missing column, so missing required columns are treated as a fatal file-shape
error rather than a row-level rejection.
