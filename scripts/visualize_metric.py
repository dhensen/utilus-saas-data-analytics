# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "matplotlib>=3.9.0",
# ]
# ///
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize one metric from the SaaS report JSON.")
    parser.add_argument("report_json", type=Path)
    parser.add_argument(
        "metric",
        choices=("mrr", "churn", "retention"),
        help="Metric to visualize.",
    )
    parser.add_argument("output_png", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = json.loads(args.report_json.read_text())

    args.output_png.parent.mkdir(parents=True, exist_ok=True)
    if args.metric == "mrr":
        plot_mrr(report["monthly_mrr"], args.output_png)
    elif args.metric == "churn":
        plot_churn(report["monthly_churned_customers"], args.output_png)
    else:
        plot_retention(report["signup_cohorts"], args.output_png)

    print(f"Wrote {args.output_png}")
    return 0


def plot_mrr(rows: list[dict[str, Any]], output_png: Path) -> None:
    months = [row["month"] for row in rows]
    values = [row["mrr"] for row in rows]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(months, values, marker="o", linewidth=2)
    ax.set_title("Monthly Recurring Revenue")
    ax.set_xlabel("Month")
    ax.set_ylabel("MRR")
    ax.grid(axis="y", alpha=0.3)
    finish(fig, output_png)


def plot_churn(rows: list[dict[str, Any]], output_png: Path) -> None:
    months = [row["month"] for row in rows]
    values = [row["churned_customers"] for row in rows]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(months, values)
    ax.set_title("Monthly Churned Customers")
    ax.set_xlabel("Month")
    ax.set_ylabel("Churned customers")
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.3)
    finish(fig, output_png)


def plot_retention(rows: list[dict[str, Any]], output_png: Path) -> None:
    months = [row["cohort_month"] for row in rows]
    values = [row["retention_rate_3m"] * 100 for row in rows]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(months, values)
    ax.set_title("3-Month Signup Cohort Retention")
    ax.set_xlabel("Signup cohort")
    ax.set_ylabel("Retention rate (%)")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.3)
    finish(fig, output_png)


def finish(fig: plt.Figure, output_png: Path) -> None:
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()
    fig.savefig(output_png, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
