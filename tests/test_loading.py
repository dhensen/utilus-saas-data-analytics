import pytest

from src.loading import load_analytics_data


def test_load_separates_valid_candidates_and_rejected_rows(tmp_path) -> None:
    customers_csv = tmp_path / "customers.csv"
    subscriptions_csv = tmp_path / "subscriptions.csv"
    customers_csv.write_text(
        "\n".join(
            [
                "customer_id,signup_date,country",
                "C001,2024-01-01,NL",
                "C002,2024-02-30,DE",
                "C001,2024-01-02,DE",
                "",
            ]
        )
    )
    subscriptions_csv.write_text(
        "\n".join(
            [
                "customer_id,start_date,end_date,plan,monthly_price",
                'C001, 2024-01-01 , ,basic,"30"',
                "C002,2024-01-01,,basic,30",
                "C999,2024-01-01,,basic,30",
                "C001,2024-02-01,2024-01-01,basic,30",
                "C001,2024-02-01,,basic,thirty",
                "",
            ]
        )
    )

    data = load_analytics_data(customers_csv, subscriptions_csv)

    assert [customer.customer_id for customer in data.customers] == ["C001"]
    assert len(data.subscriptions) == 1
    rejected_reasons = {row.reason for row in data.rejected_rows}
    assert "signup_date is not a valid ISO date" in rejected_reasons
    assert "duplicate customer_id; first valid occurrence is used" in rejected_reasons
    assert "unknown customer_id" in rejected_reasons
    assert "end_date must be after start_date for half-open intervals" in rejected_reasons
    assert "monthly_price is not numeric" in rejected_reasons
    valid_subscription = next(
        row
        for row in data.valid_candidate_rows
        if row.source == "subscriptions" and row.record_id == "C001"
    )
    assert {coercion.field for coercion in valid_subscription.coerced_fields} >= {
        "start_date",
        "end_date",
        "monthly_price",
    }


def test_strict_schema_rejects_extra_columns(tmp_path) -> None:
    customers_csv = tmp_path / "customers.csv"
    subscriptions_csv = tmp_path / "subscriptions.csv"
    customers_csv.write_text("customer_id,signup_date,country,extra\nC001,2024-01-01,NL,x\n")
    subscriptions_csv.write_text(
        "customer_id,start_date,end_date,plan,monthly_price\nC001,2024-01-01,,basic,30\n"
    )

    with pytest.raises(ValueError, match="extra columns: extra"):
        load_analytics_data(customers_csv, subscriptions_csv)


def test_overlapping_subscriptions_with_same_price_are_merged(tmp_path) -> None:
    customers_csv = tmp_path / "customers.csv"
    subscriptions_csv = tmp_path / "subscriptions.csv"
    customers_csv.write_text("customer_id,signup_date,country\nC001,2024-01-01,NL\n")
    subscriptions_csv.write_text(
        "\n".join(
            [
                "customer_id,start_date,end_date,plan,monthly_price",
                "C001,2024-02-05,2024-04-01,pro,55",
                "C001,2024-03-15,2024-05-01,pro,55",
                "",
            ]
        )
    )

    data = load_analytics_data(customers_csv, subscriptions_csv)

    assert len(data.subscriptions) == 1
    subscription = data.subscriptions[0]
    assert subscription.start_date.isoformat() == "2024-02-05"
    assert subscription.end_date and subscription.end_date.isoformat() == "2024-05-01"
    assert subscription.monthly_price == 55.0
    assert [row.reason for row in data.adjusted_rows] == [
        "overlapping subscription with same price merged"
    ]


def test_overlapping_subscriptions_with_new_price_adjust_previous_end_date(tmp_path) -> None:
    customers_csv = tmp_path / "customers.csv"
    subscriptions_csv = tmp_path / "subscriptions.csv"
    customers_csv.write_text("customer_id,signup_date,country\nC001,2024-01-01,NL\n")
    subscriptions_csv.write_text(
        "\n".join(
            [
                "customer_id,start_date,end_date,plan,monthly_price",
                "C001,2024-01-01,2024-04-01,basic,30",
                "C001,2024-03-15,2024-06-01,pro,50",
                "",
            ]
        )
    )

    data = load_analytics_data(customers_csv, subscriptions_csv)

    actual_ranges = [
        (sub.start_date.isoformat(), sub.end_date.isoformat(), sub.monthly_price)
        for sub in data.subscriptions
    ]
    assert actual_ranges == [
        ("2024-01-01", "2024-03-15", 30.0),
        ("2024-03-15", "2024-06-01", 50.0),
    ]
    assert [row.reason for row in data.adjusted_rows] == [
        "overlapping subscription adjusted for later price change"
    ]
