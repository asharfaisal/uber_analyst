"""
intent_schema.py

Defines the structured intent format shared between the classifier(s) and
the query planner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import constants as C

VALID_INTENT_TYPES = [
    "summary",
    "top_n",
    "comparison",
    "time_series",
    "distribution",
    "cancellation_reasons",
]

VALID_METRICS = [
    "ride_count",
    "total_revenue",
    "avg_booking_value",
    "avg_ride_distance",
    "avg_driver_rating",
    "avg_customer_rating",
    "total_distance",
    "unique_customers",   # summary-only: not aggregatable by dimension
    "completion_rate",    # summary-only: not aggregatable by dimension
]

VALID_GRAINS = ["day", "week", "month", "quarter", "day_of_week", "hour"]

VALID_DIMENSIONS = [
    C.COL_VEHICLE_TYPE,
    C.COL_PICKUP_LOCATION,
    C.COL_DROP_LOCATION,
    C.COL_PAYMENT_METHOD,
    C.COL_BOOKING_STATUS,
    C.COL_CUSTOMER_ID,
]


_DIMENSION_ALIASES = {
    "vehicle_type": C.COL_VEHICLE_TYPE, "vehicletype": C.COL_VEHICLE_TYPE,
    "vehicle": C.COL_VEHICLE_TYPE, "car_type": C.COL_VEHICLE_TYPE,
    "pickup_location": C.COL_PICKUP_LOCATION, "pickuplocation": C.COL_PICKUP_LOCATION,
    "pickup": C.COL_PICKUP_LOCATION,
    "drop_location": C.COL_DROP_LOCATION, "droplocation": C.COL_DROP_LOCATION,
    "drop": C.COL_DROP_LOCATION, "destination": C.COL_DROP_LOCATION,
    "payment_method": C.COL_PAYMENT_METHOD, "paymentmethod": C.COL_PAYMENT_METHOD,
    "payment": C.COL_PAYMENT_METHOD,
    "booking_status": C.COL_BOOKING_STATUS, "bookingstatus": C.COL_BOOKING_STATUS,
    "status": C.COL_BOOKING_STATUS,
    "customer_id": C.COL_CUSTOMER_ID, "customerid": C.COL_CUSTOMER_ID,
    "customer": C.COL_CUSTOMER_ID,
}


def _normalize_dimension(dim):
    """LLMs frequently return a dimension as snake_case ('vehicle_type')
    despite the prompt asking for the exact column name ('Vehicle Type'),
    since that mirrors the snake_case convention used for `metric`. Rather
    than relying on the model to always format this exactly right, map
    common variants to the real column name here."""
    if dim is None:
        return None
    if dim in VALID_DIMENSIONS:
        return dim
    key = str(dim).strip().lower().replace(" ", "_")
    return _DIMENSION_ALIASES.get(key, dim)


@dataclass
class Filters:
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    statuses: Optional[list] = None
    vehicle_types: Optional[list] = None
    pickup_locations: Optional[list] = None
    drop_locations: Optional[list] = None
    payment_methods: Optional[list] = None


@dataclass
class Intent:
    intent_type: str
    metric: Optional[str] = None
    dimension: Optional[str] = None
    grain: Optional[str] = None
    top_n: Optional[int] = None
    comparison_values: Optional[list] = None
    cancellation_by: Optional[str] = None
    filters: Filters = field(default_factory=Filters)
    clarification_needed: bool = False
    clarification_question: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Intent":
        filters_dict = d.get("filters") or {}
        date_range = filters_dict.get("date_range") or {}
        filters = Filters(
            date_start=date_range.get("start"),
            date_end=date_range.get("end"),
            statuses=filters_dict.get("statuses"),
            vehicle_types=filters_dict.get("vehicle_types"),
            pickup_locations=filters_dict.get("pickup_locations"),
            drop_locations=filters_dict.get("drop_locations"),
            payment_methods=filters_dict.get("payment_methods"),
        )
        return cls(
            intent_type=d["intent_type"],
            metric=d.get("metric"),
            dimension=_normalize_dimension(d.get("dimension")),
            grain=d.get("grain"),
            top_n=d.get("top_n"),
            comparison_values=d.get("comparison_values"),
            cancellation_by=d.get("cancellation_by"),
            filters=filters,
            clarification_needed=d.get("clarification_needed", False),
            clarification_question=d.get("clarification_question"),
        )

    def validate(self) -> list:
        errors = []
        if self.intent_type not in VALID_INTENT_TYPES:
            errors.append(f"Invalid intent_type: {self.intent_type}")
        if self.metric is not None and self.metric not in VALID_METRICS:
            errors.append(f"Invalid metric: {self.metric}")
        if self.grain is not None and self.grain not in VALID_GRAINS:
            errors.append(f"Invalid grain: {self.grain}")
        if self.intent_type == "time_series" and self.grain is None:
            errors.append("time_series intent requires a grain")
        if self.intent_type == "top_n" and self.dimension is None:
            errors.append("top_n intent requires a dimension")
        if self.intent_type == "comparison" and not self.comparison_values:
            errors.append("comparison intent requires comparison_values")
        if self.intent_type == "cancellation_reasons" and self.cancellation_by not in (
            "customer", "driver",
        ):
            errors.append("cancellation_reasons intent requires cancellation_by")
        return errors