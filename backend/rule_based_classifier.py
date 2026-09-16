"""
rule_based_classifier.py

A deterministic, keyword-based intent classifier — no LLM, no API cost.
Used as the primary classifier when no Anthropic API credit is available,
or as an automatic fallback if the Claude-powered classifier fails for any
reason (rate limit, billing, network).

This will never be as flexible as the Claude classifier for oddly-phrased
questions, but it reliably handles direct, clearly-worded questions about
the dataset's known vehicle types, payment methods, statuses, and metrics
— which covers most realistic usage of a demo/project like this one.
"""

from __future__ import annotations

import re
from datetime import date

from . import constants as C
from .intent_schema import Intent, Filters

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

_DAYS_IN_MONTH_2025 = {
    1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
    7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31,
}

_METRIC_KEYWORDS = [
    (["revenue", "earning", "income", "money made", "sales"], "total_revenue"),
    (["average booking value", "avg booking value", "average fare", "avg fare",
      "booking value"], "avg_booking_value"),
    (["distance", "km", "kilometer"], "avg_ride_distance"),
    (["driver rating", "driver ratings"], "avg_driver_rating"),
    (["customer rating", "customer ratings"], "avg_customer_rating"),
    (["how many customers", "unique customers", "total customers",
      "number of customers", "customer count"], "unique_customers"),
    (["completion rate", "completed rate"], "completion_rate"),
]

_DIMENSION_KEYWORDS = [
    (["vehicle", "car type"], C.COL_VEHICLE_TYPE),
    (["payment method", "payment type", "paid by", "upi", "cash"], C.COL_PAYMENT_METHOD),
    (["pickup location", "pickup area", "pickup"], C.COL_PICKUP_LOCATION),
    (["drop location", "drop area", "destination"], C.COL_DROP_LOCATION),
    (["booking status", "status"], C.COL_BOOKING_STATUS),
]

_GRAIN_KEYWORDS = [
    (["by hour", "hourly", "time of day"], "hour"),
    (["by day of week", "day of the week", "weekday"], "day_of_week"),
    (["by week", "weekly"], "week"),
    (["by quarter", "quarterly"], "quarter"),
    (["by month", "monthly", "over time", "trend", "over the year"], "month"),
    (["by day", "daily"], "day"),
]


def classify_intent_rule_based(question: str) -> Intent:
    """
    Classify a question using keyword matching. Always returns a valid,
    executable Intent (never raises) — if nothing specific matches, it
    falls back to a "summary" intent so the user still gets an answer
    rather than an error.
    """
    q = question.lower().strip()

    intent_type = _detect_intent_type(q)
    metric = _detect_metric(q)
    dimension = _detect_dimension(q)
    grain = _detect_grain(q) if intent_type == "time_series" else None
    top_n = _detect_top_n(q) if intent_type == "top_n" else None
    comparison_values = _detect_comparison_values(q) if intent_type == "comparison" else None
    cancellation_by = _detect_cancellation_by(q) if intent_type == "cancellation_reasons" else None
    filters = _detect_filters(q)

    # Comparison needs a dimension too, for the planner to know which
    # column the comparison_values belong to (it can also infer this later).
    if intent_type == "comparison" and not comparison_values:
        # Couldn't find specific values to compare -> fall back to top_n
        # on whatever dimension was detected, which is still a useful answer.
        intent_type = "top_n"
        top_n = 10

    if intent_type == "top_n" and dimension is None:
        dimension = C.COL_VEHICLE_TYPE  # sensible default for "most popular" questions

    if intent_type == "distribution" and dimension is None and metric is None:
        dimension = C.COL_VEHICLE_TYPE

    return Intent(
        intent_type=intent_type,
        metric=metric,
        dimension=dimension,
        grain=grain,
        top_n=top_n,
        comparison_values=comparison_values,
        cancellation_by=cancellation_by,
        filters=filters,
        clarification_needed=False,
        clarification_question=None,
    )


def _detect_intent_type(q: str) -> str:
    if any(kw in q for kw in ["why", "reason", "cancellation reason", "cancel"]) and \
       any(kw in q for kw in ["cancel", "reason"]):
        return "cancellation_reasons"
    if any(kw in q for kw in [" vs ", " versus ", "compare"]):
        return "comparison"
    if any(kw in q for kw in ["trend", "over time", "by month", "by hour",
                                "by day", "by week", "by quarter", "over the year"]):
        return "time_series"
    if any(kw in q for kw in ["distribution", "spread", "histogram", "how are",
                                "range of"]):
        return "distribution"
    if any(kw in q for kw in ["top ", "most popular", "highest", "which", "best",
                                "leading", "rank"]):
        return "top_n"
    return "summary"


def _detect_metric(q: str) -> str | None:
    for keywords, metric in _METRIC_KEYWORDS:
        if any(kw in q for kw in keywords):
            return metric
    return None


def _detect_dimension(q: str) -> str | None:
    for keywords, dimension in _DIMENSION_KEYWORDS:
        if any(kw in q for kw in keywords):
            return dimension
    # Try direct vehicle-type name matches (e.g. "which is more popular, Auto or Bike")
    for vt in C.VEHICLE_TYPES:
        if vt.lower() in q:
            return C.COL_VEHICLE_TYPE
    for pm in C.PAYMENT_METHODS:
        if pm.lower() in q:
            return C.COL_PAYMENT_METHOD
    return None


def _detect_grain(q: str) -> str:
    for keywords, grain in _GRAIN_KEYWORDS:
        if any(kw in q for kw in keywords):
            return grain
    return "month"  # sensible default for any unqualified "trend" question


def _detect_top_n(q: str) -> int:
    match = re.search(r"top\s+(\d+)", q)
    if match:
        return int(match.group(1))
    return 10


def _detect_comparison_values(q: str) -> list[str] | None:
    found = [vt for vt in C.VEHICLE_TYPES if vt.lower() in q]
    if len(found) >= 2:
        return found
    found = [pm for pm in C.PAYMENT_METHODS if pm.lower() in q]
    if len(found) >= 2:
        return found
    found = [s for s in C.ALL_BOOKING_STATUSES if s.lower() in q]
    if len(found) >= 2:
        return found
    return None


def _detect_cancellation_by(q: str) -> str:
    if "driver" in q:
        return "driver"
    return "customer"


def _detect_filters(q: str) -> Filters:
    filters = Filters()

    # Vehicle type filter (only if not already used as the dimension/comparison)
    matched_vehicles = [vt for vt in C.VEHICLE_TYPES if vt.lower() in q]
    if matched_vehicles and len(matched_vehicles) == 1:
        filters.vehicle_types = matched_vehicles

    # Payment method filter
    matched_payments = [pm for pm in C.PAYMENT_METHODS if pm.lower() in q]
    if matched_payments and len(matched_payments) == 1:
        filters.payment_methods = matched_payments

    # Status filter
    matched_statuses = [s for s in C.ALL_BOOKING_STATUSES if s.lower() in q]
    if matched_statuses and len(matched_statuses) == 1:
        filters.statuses = matched_statuses

    # Month filter -> resolves to a date range within 2025 (the only year present)
    for month_name, month_num in MONTH_NAMES.items():
        if month_name in q:
            days = _DAYS_IN_MONTH_2025[month_num]
            filters.date_start = f"2025-{month_num:02d}-01"
            filters.date_end = f"2025-{month_num:02d}-{days:02d}"
            break

    return filters
