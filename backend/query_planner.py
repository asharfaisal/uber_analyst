"""
query_planner.py

Takes a validated Intent (see intent_schema.py) and executes it against the
data engine, returning a structured result plus metadata about what was run.
This is the layer that decides *which* data_engine functions to call and in
*what order* — it contains no LLM calls and is fully deterministic, which is
what makes it unit-testable without hitting the Claude API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from . import data_engine as de
from .intent_schema import Intent


@dataclass
class QueryResult:
    intent_type: str
    data: Any  # pd.Series, pd.DataFrame, or dict depending on intent_type
    row_count: int  # number of underlying rows the query executed against
    is_empty: bool
    metadata: dict  # echoes back metric/dimension/filters used, for the formatter


def _apply_filters(df: pd.DataFrame, intent: Intent) -> pd.DataFrame:
    """Apply every filter present on the intent, in a fixed, predictable order."""
    f = intent.filters
    result = df

    if f.date_start or f.date_end:
        result = de.filter_by_date_range(result, f.date_start, f.date_end)
    if f.statuses:
        result = de.filter_by_status(result, f.statuses)
    if f.vehicle_types:
        result = de.filter_by_vehicle_type(result, f.vehicle_types)
    if f.pickup_locations or f.drop_locations:
        result = de.filter_by_location(result, f.pickup_locations, f.drop_locations)
    if f.payment_methods:
        result = de.filter_by_payment_method(result, f.payment_methods)

    return result


def execute_intent(df: pd.DataFrame, intent: Intent) -> QueryResult:
    """
    Execute a validated Intent against the dataset.

    Raises:
        ValueError: if the intent fails validation (should have been caught
            earlier, but this is a defensive second check).
    """
    errors = intent.validate()
    if errors:
        raise ValueError(f"Cannot execute invalid intent: {errors}")

    filtered = _apply_filters(df, intent)
    row_count = len(filtered)

    metadata = {
        "metric": intent.metric,
        "dimension": intent.dimension,
        "grain": intent.grain,
        "filters_applied": _describe_filters(intent),
    }

    if row_count == 0:
        return QueryResult(
            intent_type=intent.intent_type,
            data=None,
            row_count=0,
            is_empty=True,
            metadata=metadata,
        )

    dispatch = {
        "summary": _run_summary,
        "top_n": _run_top_n,
        "comparison": _run_comparison,
        "time_series": _run_time_series,
        "distribution": _run_distribution,
        "cancellation_reasons": _run_cancellation_reasons,
    }

    handler = dispatch[intent.intent_type]
    data = handler(filtered, intent)

    return QueryResult(
        intent_type=intent.intent_type,
        data=data,
        row_count=row_count,
        is_empty=False,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Per-intent handlers
# ---------------------------------------------------------------------------

def _run_summary(df: pd.DataFrame, intent: Intent) -> dict:
    return de.get_summary(df)


def _run_top_n(df: pd.DataFrame, intent: Intent) -> pd.Series:
    metric = intent.metric or "ride_count"
    n = intent.top_n or 10
    return de.get_top_n(df, intent.dimension, metric=metric, n=n)


def _run_comparison(df: pd.DataFrame, intent: Intent) -> pd.Series:
    metric = intent.metric or "ride_count"
    dimension = intent.dimension or _infer_comparison_dimension(df, intent.comparison_values)
    return de.get_comparison(df, metric, dimension, intent.comparison_values)


def _run_time_series(df: pd.DataFrame, intent: Intent) -> pd.Series:
    metric = intent.metric or "ride_count"
    return de.get_time_series(df, metric=metric, grain=intent.grain)


def _run_distribution(df: pd.DataFrame, intent: Intent) -> pd.Series:
    field = intent.dimension or intent.metric
    if field is None:
        raise ValueError("distribution intent requires a dimension or metric field")
    # Map metric name to actual column name if needed
    field = _METRIC_TO_COLUMN.get(field, field)
    return de.get_distribution(df, field)


def _run_cancellation_reasons(df: pd.DataFrame, intent: Intent) -> pd.Series:
    return de.get_cancellation_reasons(df, by=intent.cancellation_by)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_METRIC_TO_COLUMN = {
    "total_revenue": "Booking Value",
    "avg_booking_value": "Booking Value",
    "avg_ride_distance": "Ride Distance",
    "total_distance": "Ride Distance",
    "avg_driver_rating": "Driver Ratings",
    "avg_customer_rating": "Customer Rating",
}


def _infer_comparison_dimension(df: pd.DataFrame, values: list[str]) -> str:
    """If the intent didn't specify which column the comparison_values belong
    to, infer it by checking which categorical column actually contains
    those values."""
    from . import constants as C

    candidate_columns = [
        C.COL_VEHICLE_TYPE,
        C.COL_PAYMENT_METHOD,
        C.COL_PICKUP_LOCATION,
        C.COL_DROP_LOCATION,
        C.COL_BOOKING_STATUS,
    ]
    for col in candidate_columns:
        if set(values).issubset(set(df[col].unique())):
            return col
    raise ValueError(
        f"Could not infer which column contains comparison values: {values}"
    )


def _describe_filters(intent: Intent) -> dict:
    """Human-readable echo of applied filters, for use in response formatting."""
    f = intent.filters
    described = {}
    if f.date_start or f.date_end:
        described["date_range"] = f"{f.date_start or 'start'} to {f.date_end or 'end'}"
    if f.statuses:
        described["statuses"] = f.statuses
    if f.vehicle_types:
        described["vehicle_types"] = f.vehicle_types
    if f.pickup_locations:
        described["pickup_locations"] = f.pickup_locations
    if f.drop_locations:
        described["drop_locations"] = f.drop_locations
    if f.payment_methods:
        described["payment_methods"] = f.payment_methods
    return described
