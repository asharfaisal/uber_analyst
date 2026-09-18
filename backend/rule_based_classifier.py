"""
rule_based_classifier.py

A deterministic, keyword-based intent classifier — no LLM, no API cost.
Serves as an automatic fallback if the LLM-powered classifier fails for any
reason (no key, no credits, network issue, rate limit).
"""

from __future__ import annotations

import re

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
    q = question.lower().strip()

    intent_type = _detect_intent_type(q)
    metric = _detect_metric(q)
    dimension = _detect_dimension(q)
    grain = _detect_grain(q) if intent_type == "time_series" else None
    top_n = _detect_top_n(q) if intent_type == "top_n" else None
    comparison_values = _detect_comparison_values(q) if intent_type == "comparison" else None
    cancellation_by = _detect_cancellation_by(q) if intent_type == "cancellation_reasons" else None
    filters = _detect_filters(q)

    if intent_type == "comparison" and not comparison_values:
        intent_type = "top_n"
        top_n = 10

    if intent_type == "top_n" and dimension is None:
        dimension = C.COL_VEHICLE_TYPE

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
    # Only classify as "why did cancellations happen" if the question
    # actually asks for a reason -- "cancel" alone (e.g. "trend of
    # cancellations") should NOT trigger this, or every cancellation-
    # related question gets misrouted away from what was actually asked.
    if any(kw in q for kw in ["why", "reason"]) and "cancel" in q:
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


def _detect_metric(q: str):
    for keywords, metric in _METRIC_KEYWORDS:
        if any(kw in q for kw in keywords):
            return metric
    return None


def _detect_dimension(q: str):
    for keywords, dimension in _DIMENSION_KEYWORDS:
        if any(kw in q for kw in keywords):
            return dimension
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
    return "month"


def _detect_top_n(q: str) -> int:
    match = re.search(r"top\s+(\d+)", q)
    if match:
        return int(match.group(1))
    return 10


def _detect_comparison_values(q: str):
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

    matched_vehicles = [vt for vt in C.VEHICLE_TYPES if vt.lower() in q]
    if matched_vehicles and len(matched_vehicles) == 1:
        filters.vehicle_types = matched_vehicles

    matched_payments = [pm for pm in C.PAYMENT_METHODS if pm.lower() in q]
    if matched_payments and len(matched_payments) == 1:
        filters.payment_methods = matched_payments

    matched_statuses = [s for s in C.ALL_BOOKING_STATUSES if s.lower() in q]
    if matched_statuses and len(matched_statuses) == 1:
        filters.statuses = matched_statuses

    for month_name, month_num in MONTH_NAMES.items():
        if month_name in q:
            days = _DAYS_IN_MONTH_2025[month_num]
            filters.date_start = f"2025-{month_num:02d}-01"
            filters.date_end = f"2025-{month_num:02d}-{days:02d}"
            break

    return filters