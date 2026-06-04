# Design

The project is a small `uv`-managed Python CLI. `main.py` handles command-line arguments and JSON output, `src/loading.py` loads and validates CSV rows, `src/models.py` contains typed dataclasses, and `src/metrics.py` contains the business metric calculations.

CSV validation is split into two stages. First, Pandera strict schemas validate the file shape and coerce scalar values such as dates and prices. Rows that fail schema validation are recorded in `data_quality.rejected_rows`. Rows that pass Pandera become `valid_candidate_rows`. Second, application-level checks reject rows that need cross-row context, such as duplicate customer IDs, subscriptions for unknown customers, and subscriptions whose exclusive `end_date` is not after `start_date`.

Subscriptions are modeled as half-open intervals: `[start_date, end_date)`. Monthly MRR counts the full monthly price for any subscription overlapping a calendar month. Churn is counted when a subscription ends and the same customer has no new subscription starting within 30 days after the exclusive `end_date`, including the 30th day. Cohort retention groups customers by signup month and checks whether they have any subscription active exactly three calendar months after signup.

Adding another metric should only require a new function in `src/metrics.py` and adding its result to `build_report`. The loader returns clean typed records plus data-quality details, so metric functions do not need to know about CSV parsing or Pandera failure formats.

Known trade-off: invalid row handling favors producing a partial report over failing the whole run. The CLI still exits nonzero when the CSV shape is unusable, such as missing or extra columns.
