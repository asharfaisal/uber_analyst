"""
intent_schema.py

Defines the structured intent format that the Intent Classifier produces and
the Query Planner consumes. Keeping this as an explicit schema (rather than
an ad-hoc dict shape scattered across files) makes it possible to validate
Claude's output and to unit-test the planner with hand-written intents that
never touch the API.

INTENT SHAPE (as JSON / dict):
{
    "intent_type": "summary" | "top_n" | "comparison" | "time_series" |
                    "distribution" | "cancellation_reasons",
    "metric": "ride_count" | "total_revenue" | "avg_booking_value" |
              "avg_ride_distance" | "avg_driver_rating" |
              "avg_customer_rating" | "total_distance" | null,
    "dimension": "<column name>" | null,
    "grain": "day" | "week" | "month" | "quarter" | "day_of_week" | "hour" | null,
    "top_n": <int> | null,
    "comparison_values": [<str>, ...] | null,
    "cancellation_by": "customer" | "driver" | null,
    "filters": {
        "date_range": {"start": "YYYY-MM-DD" | null, "end": "YYYY-MM-DD" | null} | null,
        "statuses": [<str>, ...] | null,
        "vehicle_types": [<str>, ...] | null,
        "pickup_locations": [<str>, ...] | null,
        "drop_locations": [<str>, ...] | null,
        "payment_methods": [<str>, ...] | null
    },
    "clarification_needed": <bool>,
    "clarification_question": <str> | null
}

Only the fields relevant to a given intent_type need to be non-null; the
planner ignores irrelevant fields.
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
        """Build an Intent from a raw dict (e.g. parsed JSON from Claude)."""
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
            dimension=d.get("dimension"),
            grain=d.get("grain"),
            top_n=d.get("top_n"),
            comparison_values=d.get("comparison_values"),
            cancellation_by=d.get("cancellation_by"),
            filters=filters,
            clarification_needed=d.get("clarification_needed", False),
            clarification_question=d.get("clarification_question"),
        )

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty list = valid). The
        planner should refuse to execute an Intent with errors."""
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
