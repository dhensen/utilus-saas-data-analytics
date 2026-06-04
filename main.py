from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.loading import load_analytics_data
from src.metrics import build_report
from src.models import AnalyticsData


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SaaS analytics JSON report from CSV exports.")
    parser.add_argument("customers_csv", type=Path)
    parser.add_argument("subscriptions_csv", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Optional path for data-quality errors. Defaults to stderr.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        analytics_data = load_analytics_data(args.customers_csv, args.subscriptions_csv)
        report = build_report(analytics_data)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    log_data_quality_issues(analytics_data, args.log_file)
    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


def log_data_quality_issues(data: AnalyticsData, log_file: Path | None) -> None:
    if not data.rejected_rows and not data.adjusted_rows:
        return

    logger = logging.getLogger("data_quality")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler: logging.Handler
    if log_file is None:
        handler = logging.StreamHandler(sys.stderr)
    else:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_file, mode="w")

    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    logger.info("Rejected rows: %s", len(data.rejected_rows))
    for row in data.rejected_rows:
        logger.info(json.dumps(row.to_dict(), sort_keys=True))
    logger.info("Adjusted rows: %s", len(data.adjusted_rows))
    for row in data.adjusted_rows:
        logger.info(json.dumps(row.to_dict(), sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
