from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path


COUNTRIES = ["NL", "DE", "FR", "SE", "UK", "DK", "BE"]
PLANS = [("basic", 25), ("pro", 55)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate larger customers/subscriptions CSV files with realistic data quality issues."
    )
    parser.add_argument(
        "size",
        type=int,
        help="Approximate number of data rows to write to each generated CSV.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.size < 1:
        raise SystemExit("size must be at least 1")

    random.seed(args.seed)
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    customer_ids = write_customers(data_dir / "customers_big.csv", args.size)
    write_subscriptions(data_dir / "subscriptions_big.csv", args.size, customer_ids)
    return 0


def write_customers(path: Path, size: int) -> list[str]:
    customer_ids = [f"C{i:06d}" for i in range(1, size + 1)]

    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["customer_id", "signup_date", "country"])

        for index, customer_id in enumerate(customer_ids, start=1):
            signup = date(2023, 1, 1) + timedelta(days=random.randint(0, 730))
            country = random.choice(COUNTRIES)

            if index % 211 == 0:
                signup_value = f"{signup.year}-13-{signup.day:02d}"
            else:
                signup_value = signup.isoformat()

            if index % 157 == 0:
                country = ""
            elif index % 173 == 0:
                country = country.lower()

            if index % 503 == 0 and index > 1:
                row_customer_id = customer_ids[index - 2]
            else:
                row_customer_id = customer_id

            writer.writerow([row_customer_id, signup_value, country])

    return customer_ids


def write_subscriptions(path: Path, size: int, customer_ids: list[str]) -> None:
    with path.open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["customer_id", "start_date", "end_date", "plan", "monthly_price"])

        for index in range(1, size + 1):
            customer_id = random.choice(customer_ids)
            start = date(2023, 1, 1) + timedelta(days=random.randint(0, 820))
            duration_days = random.randint(20, 240)
            end = start + timedelta(days=duration_days)
            plan, price = random.choice(PLANS)

            if random.random() < 0.45:
                end_value = ""
            else:
                end_value = end.isoformat()

            if index % 197 == 0:
                customer_id = f"CUNKNOWN{index:06d}"
            if index % 223 == 0:
                end_value = f"{end.year}-02-30"
            if index % 241 == 0:
                price_value: str | int = "thirty"
            else:
                price_value = price
            if index % 263 == 0:
                end_value = (start - timedelta(days=10)).isoformat()
            if index % 307 == 0:
                plan = "baisc"
            if index % 331 == 0:
                start_value = f" {start.isoformat()} "
            else:
                start_value = start.isoformat()
            if index % 379 == 0:
                end_value = " "

            writer.writerow([customer_id, start_value, end_value, plan, price_value])


if __name__ == "__main__":
    raise SystemExit(main())
