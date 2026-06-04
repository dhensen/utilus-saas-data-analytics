from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaErrors

from src.models import AnalyticsData, Coercion, Customer, RejectedRow, Subscription, ValidCandidateRow

CUSTOMER_COLUMNS = ["customer_id", "signup_date", "country"]
SUBSCRIPTION_COLUMNS = ["customer_id", "start_date", "end_date", "plan", "monthly_price"]


def customer_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "customer_id": pa.Column(str, nullable=False),
            "signup_date": pa.Column(pa.DateTime, nullable=False),
            "country": pa.Column(str, nullable=True),
        },
        strict=True,
        coerce=True,
    )


def subscription_schema() -> pa.DataFrameSchema:
    return pa.DataFrameSchema(
        {
            "customer_id": pa.Column(str, nullable=False),
            "start_date": pa.Column(pa.DateTime, nullable=False),
            "end_date": pa.Column(pa.DateTime, nullable=True),
            "plan": pa.Column(str, nullable=False),
            "monthly_price": pa.Column(float, nullable=False),
        },
        strict=True,
        coerce=True,
    )


def load_analytics_data(customers_path: Path, subscriptions_path: Path) -> AnalyticsData:
    customer_raw = _read_raw_csv(customers_path, CUSTOMER_COLUMNS, "customers")
    subscription_raw = _read_raw_csv(subscriptions_path, SUBSCRIPTION_COLUMNS, "subscriptions")

    customer_validated, customer_candidates, customer_rejects = _validate_customers(customer_raw)
    subscription_validated, subscription_candidates, subscription_rejects = _validate_subscriptions(
        subscription_raw
    )

    customers, customer_business_rejects = _build_customers(customer_validated)
    subscriptions, subscription_business_rejects = _build_subscriptions(
        subscription_validated, {customer.customer_id for customer in customers}
    )

    rejected_row_keys = {
        ("customers", reject.row_number) for reject in (*customer_rejects, *customer_business_rejects)
    } | {
        ("subscriptions", reject.row_number)
        for reject in (*subscription_rejects, *subscription_business_rejects)
    }
    valid_candidate_rows = [
        row
        for row in (*customer_candidates, *subscription_candidates)
        if (row.source, row.row_number) not in rejected_row_keys
    ]

    return AnalyticsData(
        customers=customers,
        subscriptions=subscriptions,
        valid_candidate_rows=valid_candidate_rows,
        rejected_rows=[
            *customer_rejects,
            *subscription_rejects,
            *customer_business_rejects,
            *subscription_business_rejects,
        ],
    )


def _read_raw_csv(path: Path, expected_columns: list[str], source: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except FileNotFoundError as exc:
        raise ValueError(f"{source} file not found: {path}") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(f"{source} CSV could not be parsed: {exc}") from exc

    columns = list(df.columns)
    if columns != expected_columns:
        missing = [column for column in expected_columns if column not in columns]
        extra = [column for column in columns if column not in expected_columns]
        details = []
        if missing:
            details.append(f"missing columns: {', '.join(missing)}")
        if extra:
            details.append(f"extra columns: {', '.join(extra)}")
        if not details:
            details.append(f"expected column order: {', '.join(expected_columns)}")
        raise ValueError(f"{source} CSV has invalid columns ({'; '.join(details)})")

    df = df.copy()
    df.index = df.index.astype(int)
    return df


def _validate_customers(
    raw: pd.DataFrame,
) -> tuple[pd.DataFrame, list[ValidCandidateRow], list[RejectedRow]]:
    normalized, coercions = _normalize_strings(raw, CUSTOMER_COLUMNS)
    return _validate_frame(
        normalized,
        raw,
        customer_schema(),
        "customers",
        "customer_id",
        coercions,
        date_fields=("signup_date",),
        numeric_fields=(),
    )


def _validate_subscriptions(
    raw: pd.DataFrame,
) -> tuple[pd.DataFrame, list[ValidCandidateRow], list[RejectedRow]]:
    normalized, coercions = _normalize_strings(raw, SUBSCRIPTION_COLUMNS)
    blank_end_dates = normalized["end_date"].eq("")
    for idx in normalized.index[blank_end_dates]:
        coercions.setdefault(idx, []).append(Coercion("end_date", raw.at[idx, "end_date"], None))
    normalized.loc[blank_end_dates, "end_date"] = pd.NA

    return _validate_frame(
        normalized,
        raw,
        subscription_schema(),
        "subscriptions",
        "customer_id",
        coercions,
        date_fields=("start_date", "end_date"),
        numeric_fields=("monthly_price",),
    )


def _validate_frame(
    normalized: pd.DataFrame,
    raw: pd.DataFrame,
    schema: pa.DataFrameSchema,
    source: str,
    record_id_field: str,
    coercions: dict[int, list[Coercion]],
    date_fields: Iterable[str],
    numeric_fields: Iterable[str],
) -> tuple[pd.DataFrame, list[ValidCandidateRow], list[RejectedRow]]:
    failed_indices: set[int] = set()
    failure_cases = pd.DataFrame()

    try:
        validated = schema.validate(normalized, lazy=True)
    except SchemaErrors as exc:
        failure_cases = exc.failure_cases
        failed_indices = {
            int(index)
            for index in failure_cases.get("index", pd.Series(dtype=object)).dropna().tolist()
            if str(index).isdigit()
        }
        candidate = normalized.drop(index=list(failed_indices))
        validated = schema.validate(candidate, lazy=True) if not candidate.empty else candidate

    rejects = _schema_rejects(failure_cases, raw, source, record_id_field)

    candidates: list[ValidCandidateRow] = []
    for idx in validated.index:
        row_coercions = list(coercions.get(int(idx), []))
        row_coercions.extend(_type_coercions(raw.loc[idx], validated.loc[idx], date_fields, numeric_fields))
        candidates.append(
            ValidCandidateRow(
                source=source,
                row_number=_row_number(idx),
                record_id=str(validated.at[idx, record_id_field]),
                coerced_fields=tuple(_dedupe_coercions(row_coercions)),
            )
        )

    return validated, candidates, rejects


def _normalize_strings(
    raw: pd.DataFrame, columns: list[str]
) -> tuple[pd.DataFrame, dict[int, list[Coercion]]]:
    normalized = raw.copy()
    coercions: dict[int, list[Coercion]] = {}
    for column in columns:
        for idx, value in raw[column].items():
            stripped = value.strip() if isinstance(value, str) else value
            if stripped != value:
                coercions.setdefault(int(idx), []).append(Coercion(column, value, stripped))
                normalized.at[idx, column] = stripped
    return normalized, coercions


def _schema_rejects(
    failure_cases: pd.DataFrame, raw: pd.DataFrame, source: str, record_id_field: str
) -> list[RejectedRow]:
    rejects: list[RejectedRow] = []
    if failure_cases.empty:
        return rejects

    seen: set[tuple[int, str, str]] = set()
    for _, failure in failure_cases.iterrows():
        raw_index = failure.get("index")
        if pd.isna(raw_index):
            continue
        idx = int(raw_index)
        field = str(failure.get("column") or "<schema>")
        reason = str(failure.get("failure_case"))
        key = (idx, field, reason)
        if key in seen:
            continue
        seen.add(key)
        original_value = raw.at[idx, field] if field in raw.columns else None
        rejects.append(
            RejectedRow(
                source=source,
                row_number=_row_number(idx),
                record_id=str(raw.at[idx, record_id_field]) if record_id_field in raw.columns else "",
                field=field,
                reason=_friendly_reason(field, reason),
                original_value=original_value,
                coerced_value=None,
            )
        )
    return rejects


def _friendly_reason(field: str, failure_case: str) -> str:
    if field in {"signup_date", "start_date", "end_date"}:
        return f"{field} is not a valid ISO date"
    if field == "monthly_price":
        return "monthly_price is not numeric"
    if failure_case in {"None", "<NA>", "nan"}:
        return f"{field} is required"
    return f"{field} failed validation: {failure_case}"


def _type_coercions(
    raw_row: pd.Series,
    validated_row: pd.Series,
    date_fields: Iterable[str],
    numeric_fields: Iterable[str],
) -> list[Coercion]:
    coercions: list[Coercion] = []
    for field in date_fields:
        original = raw_row[field]
        value = validated_row[field]
        coerced = None if pd.isna(value) else value.date().isoformat()
        if original.strip() == "" and coerced is None:
            continue
        if str(original).strip() != str(coerced):
            coercions.append(Coercion(field, original, coerced))
    for field in numeric_fields:
        original = raw_row[field]
        coerced = float(validated_row[field])
        if str(original).strip() != str(coerced):
            coercions.append(Coercion(field, original, coerced))
    return coercions


def _dedupe_coercions(coercions: list[Coercion]) -> list[Coercion]:
    deduped: list[Coercion] = []
    seen: set[tuple[str, str, str]] = set()
    for coercion in coercions:
        key = (coercion.field, str(coercion.original_value), str(coercion.coerced_value))
        if key not in seen:
            seen.add(key)
            deduped.append(coercion)
    return deduped


def _build_customers(validated: pd.DataFrame) -> tuple[list[Customer], list[RejectedRow]]:
    customers: list[Customer] = []
    rejects: list[RejectedRow] = []
    seen_ids: set[str] = set()

    for idx, row in validated.iterrows():
        customer_id = str(row["customer_id"])
        if customer_id in seen_ids:
            rejects.append(
                RejectedRow(
                    source="customers",
                    row_number=_row_number(idx),
                    record_id=customer_id,
                    field="customer_id",
                    reason="duplicate customer_id; first valid occurrence is used",
                    original_value=customer_id,
                )
            )
            continue
        seen_ids.add(customer_id)
        customers.append(
            Customer(
                customer_id=customer_id,
                signup_date=row["signup_date"].date(),
                country=str(row["country"]),
                row_number=_row_number(idx),
            )
        )
    return customers, rejects


def _build_subscriptions(
    validated: pd.DataFrame, known_customer_ids: set[str]
) -> tuple[list[Subscription], list[RejectedRow]]:
    subscriptions: list[Subscription] = []
    rejects: list[RejectedRow] = []

    for idx, row in validated.iterrows():
        customer_id = str(row["customer_id"])
        start_date = row["start_date"].date()
        end_date = None if pd.isna(row["end_date"]) else row["end_date"].date()

        if customer_id not in known_customer_ids:
            rejects.append(
                RejectedRow(
                    source="subscriptions",
                    row_number=_row_number(idx),
                    record_id=customer_id,
                    field="customer_id",
                    reason="unknown customer_id",
                    original_value=customer_id,
                )
            )
            continue
        if end_date is not None and end_date <= start_date:
            rejects.append(
                RejectedRow(
                    source="subscriptions",
                    row_number=_row_number(idx),
                    record_id=customer_id,
                    field="end_date",
                    reason="end_date must be after start_date for half-open intervals",
                    original_value=end_date.isoformat(),
                    coerced_value=end_date.isoformat(),
                )
            )
            continue

        subscriptions.append(
            Subscription(
                customer_id=customer_id,
                start_date=start_date,
                end_date=end_date,
                plan=str(row["plan"]),
                monthly_price=float(row["monthly_price"]),
                row_number=_row_number(idx),
            )
        )

    return subscriptions, rejects


def _row_number(index: object) -> int:
    return int(index) + 2
