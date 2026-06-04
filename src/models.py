from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Coercion:
    field: str
    original_value: object
    coerced_value: object

    def to_dict(self) -> dict[str, object]:
        return {
            "field": self.field,
            "original_value": self.original_value,
            "coerced_value": self.coerced_value,
        }


@dataclass(frozen=True)
class ValidCandidateRow:
    source: str
    row_number: int
    record_id: str
    coerced_fields: tuple[Coercion, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "row_number": self.row_number,
            "record_id": self.record_id,
            "coerced_fields": [coercion.to_dict() for coercion in self.coerced_fields],
        }


@dataclass(frozen=True)
class RejectedRow:
    source: str
    row_number: int
    record_id: str
    field: str
    reason: str
    original_value: object
    coerced_value: object | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "row_number": self.row_number,
            "record_id": self.record_id,
            "field": self.field,
            "reason": self.reason,
            "original_value": self.original_value,
            "coerced_value": self.coerced_value,
        }


@dataclass(frozen=True)
class AdjustedRow:
    source: str
    row_number: int
    record_id: str
    field: str
    reason: str
    original_value: object
    adjusted_value: object

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "row_number": self.row_number,
            "record_id": self.record_id,
            "field": self.field,
            "reason": self.reason,
            "original_value": self.original_value,
            "adjusted_value": self.adjusted_value,
        }


@dataclass(frozen=True)
class Customer:
    customer_id: str
    signup_date: date
    country: str
    row_number: int


@dataclass(frozen=True)
class Subscription:
    customer_id: str
    start_date: date
    end_date: date | None
    plan: str
    monthly_price: float
    row_number: int


@dataclass
class AnalyticsData:
    customers: list[Customer]
    subscriptions: list[Subscription]
    valid_candidate_rows: list[ValidCandidateRow] = field(default_factory=list)
    rejected_rows: list[RejectedRow] = field(default_factory=list)
    adjusted_rows: list[AdjustedRow] = field(default_factory=list)

    def data_quality_summary_dict(self) -> dict[str, object]:
        return {
            "valid_candidate_rows": len(self.valid_candidate_rows),
            "rejected_rows": len(self.rejected_rows),
            "adjusted_rows": len(self.adjusted_rows),
        }
