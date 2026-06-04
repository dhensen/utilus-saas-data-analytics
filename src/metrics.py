from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from src.models import AnalyticsData, Customer, Subscription


def build_report(data: AnalyticsData) -> dict[str, object]:
    return {
        "monthly_churned_customers": monthly_churned_customers(data.subscriptions),
        "monthly_mrr": monthly_mrr(data.subscriptions),
        "signup_cohorts": signup_cohorts(data.customers, data.subscriptions),
        "data_quality": data.data_quality_dict(),
    }


def monthly_mrr(subscriptions: list[Subscription]) -> list[dict[str, object]]:
    if not subscriptions:
        return []

    first_month = _month_start(min(subscription.start_date for subscription in subscriptions))
    last_month = _latest_relevant_month(subscriptions)
    rows: list[dict[str, object]] = []

    current = first_month
    while current <= last_month:
        next_month = current + relativedelta(months=1)
        mrr = sum(
            subscription.monthly_price
            for subscription in subscriptions
            if _overlaps(subscription, current, next_month)
        )
        rows.append({"month": _month_key(current), "mrr": round(float(mrr), 2)})
        current = next_month

    return rows


def monthly_churned_customers(subscriptions: list[Subscription]) -> list[dict[str, object]]:
    churn_counts: dict[str, int] = defaultdict(int)
    by_customer: dict[str, list[Subscription]] = defaultdict(list)
    for subscription in subscriptions:
        by_customer[subscription.customer_id].append(subscription)

    for customer_subscriptions in by_customer.values():
        ordered = sorted(customer_subscriptions, key=lambda item: item.start_date)
        for subscription in ordered:
            if subscription.end_date is None:
                continue
            window_end = subscription.end_date + timedelta(days=30)
            has_timely_resubscription = any(
                later.start_date >= subscription.end_date and later.start_date <= window_end
                for later in ordered
                if later is not subscription
            )
            if not has_timely_resubscription:
                churn_counts[_month_key(subscription.end_date)] += 1

    return [
        {"month": month, "churned_customers": churn_counts[month]}
        for month in sorted(churn_counts)
    ]


def signup_cohorts(
    customers: list[Customer], subscriptions: list[Subscription]
) -> list[dict[str, object]]:
    subscriptions_by_customer: dict[str, list[Subscription]] = defaultdict(list)
    for subscription in subscriptions:
        subscriptions_by_customer[subscription.customer_id].append(subscription)

    cohorts: dict[str, list[Customer]] = defaultdict(list)
    for customer in customers:
        cohorts[_month_key(customer.signup_date)].append(customer)

    rows: list[dict[str, object]] = []
    for cohort_month in sorted(cohorts):
        cohort_customers = cohorts[cohort_month]
        retained = 0
        for customer in cohort_customers:
            checkpoint = customer.signup_date + relativedelta(months=3)
            if any(
                _active_on(subscription, checkpoint)
                for subscription in subscriptions_by_customer.get(customer.customer_id, [])
            ):
                retained += 1

        cohort_size = len(cohort_customers)
        rows.append(
            {
                "cohort_month": cohort_month,
                "cohort_size": cohort_size,
                "active_after_3_months": retained,
                "retention_rate_3m": round(retained / cohort_size, 4) if cohort_size else 0.0,
            }
        )

    return rows


def _overlaps(subscription: Subscription, period_start: date, period_end: date) -> bool:
    subscription_end = subscription.end_date or date.max
    return subscription.start_date < period_end and subscription_end > period_start


def _active_on(subscription: Subscription, checkpoint: date) -> bool:
    return subscription.start_date <= checkpoint and (
        subscription.end_date is None or checkpoint < subscription.end_date
    )


def _latest_relevant_month(subscriptions: list[Subscription]) -> date:
    finite_ends = [subscription.end_date for subscription in subscriptions if subscription.end_date]
    open_starts = [
        subscription.start_date for subscription in subscriptions if subscription.end_date is None
    ]
    latest = max([*finite_ends, *open_starts])
    return _month_start(latest)


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"
