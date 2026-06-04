# Design

## How the code is structured

The project is a small `uv`-managed Python CLI. `main.py` handles command-line arguments,
orchestration, JSON output, and optional data-quality logging. `src/loading.py` reads CSV
files, validates them with strict/coercing Pandera schemas, and applies cross-row cleanup.
`src/models.py` contains typed dataclasses for customers, subscriptions, rejected rows, and
adjusted rows. `src/metrics.py` contains the metric calculations and report assembly.

## How the business rules are modeled

Subscriptions are modeled as half-open intervals: `[start_date, end_date)`, so `end_date`
is exclusive. Monthly MRR sums the full monthly price for every normalized subscription
that overlaps a calendar month. Churn is counted when a subscription has an `end_date` and
the customer has no later subscription starting within 30 days after that date, including
the 30th day. Cohorts are grouped by signup month; 3-month retention checks whether the
customer has any subscription active exactly three calendar months after signup.

Overlapping subscriptions for the same customer are normalized before metrics run. Same
price overlaps are merged into one continuous interval. If the later row has a different
price, it is treated as a price change and the earlier interval is shortened to end at the
later row's `start_date`.

## How another metric would be added

Add a new function to `src/metrics.py` that takes the already validated and normalized
records, then add its result to `build_report`. For example, monthly ARPU could be added as
monthly MRR divided by the number of active customers in that month. The loader and CLI
would not need to change. If metrics grow, a future improvement would be to turn
`metrics.py` into a `metrics/` package where each metric lives in its own submodule.

## Assumptions and known trade-offs

`end_date` is assumed to be exclusive.

Invalid row handling favors a partial report over failing the whole run. Bad row values,
duplicate customer IDs, unknown subscription customer IDs, and invalid date ranges are
rejected and logged; overlap fixes are logged as adjusted rows. The JSON report contains
only compact data-quality counts, while detailed records go to stderr or `--log-file`.

The CLI exits nonzero only for file-level problems that prevent meaningful validation:
missing files, unparseable CSV input, missing required columns, extra columns, or columns
in the wrong order. Pandera can coerce values inside existing columns, but it cannot infer
or create missing columns, so missing required columns are fatal file-shape errors.
