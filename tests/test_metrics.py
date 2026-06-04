from datetime import date

from src.metrics import monthly_churned_customers, monthly_mrr, signup_cohorts
from src.models import Customer, Subscription


def test_mrr_uses_half_open_month_overlap() -> None:
    subscriptions = [
        Subscription("C001", date(2024, 1, 15), date(2024, 2, 1), "basic", 30.0, 2),
        Subscription("C002", date(2024, 2, 29), None, "pro", 50.0, 3),
    ]

    assert monthly_mrr(subscriptions) == [
        {"month": "2024-01", "mrr": 30.0},
        {"month": "2024-02", "mrr": 50.0},
    ]


def test_churn_resubscription_on_day_30_prevents_churn() -> None:
    subscriptions = [
        Subscription("C001", date(2024, 1, 1), date(2024, 1, 31), "basic", 30.0, 2),
        Subscription("C001", date(2024, 3, 1), None, "basic", 30.0, 3),
    ]

    assert monthly_churned_customers(subscriptions) == []


def test_churn_resubscription_after_day_30_counts_churn() -> None:
    subscriptions = [
        Subscription("C001", date(2024, 1, 1), date(2024, 1, 31), "basic", 30.0, 2),
        Subscription("C001", date(2024, 3, 2), None, "basic", 30.0, 3),
    ]

    assert monthly_churned_customers(subscriptions) == [
        {"month": "2024-01", "churned_customers": 1}
    ]


def test_retention_counts_active_at_three_month_checkpoint() -> None:
    customers = [
        Customer("C001", date(2024, 1, 15), "NL", 2),
        Customer("C002", date(2024, 1, 20), "DE", 3),
    ]
    subscriptions = [
        Subscription("C001", date(2024, 1, 15), date(2024, 4, 16), "basic", 30.0, 2),
        Subscription("C002", date(2024, 1, 20), date(2024, 4, 20), "basic", 30.0, 3),
    ]

    assert signup_cohorts(customers, subscriptions) == [
        {
            "cohort_month": "2024-01",
            "cohort_size": 2,
            "active_after_3_months": 1,
            "retention_rate_3m": 0.5,
        }
    ]
