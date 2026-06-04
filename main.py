from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.loading import load_analytics_data
from src.metrics import build_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SaaS analytics JSON report from CSV exports.")
    parser.add_argument("customers_csv", type=Path)
    parser.add_argument("subscriptions_csv", type=Path)
    parser.add_argument("output_json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        analytics_data = load_analytics_data(args.customers_csv, args.subscriptions_csv)
        report = build_report(analytics_data)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
