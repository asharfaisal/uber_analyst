"""
response_formatter.py

Takes a QueryResult (from query_planner.py) and produces the final answer
in two parts:

1. `format_for_visualization()` — deterministic, no LLM. Converts pandas
   Series/DataFrame/dict results into a plain JSON-serializable structure
   the React frontend can render directly (chart type + labels + values).
   Fully unit-testable.

2. `generate_narrative()` — calls Claude to turn the numbers into a short,
   readable explanation. This is a separate, focused API call from intent
   classification: here Claude only writes prose about numbers it's given,
   it never sees the raw dataset and cannot hallucinate figures.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

try:
    import anthropic
except ImportError:
    anthropic = None

from .query_planner import QueryResult

MODEL = "claude-sonnet-4-6"


@dataclass
class FormattedResponse:
    chart_type: str  # "bar" | "line" | "kpi_cards" | "table" | "none"
    title: str
    labels: list
    values: list
    unit: Optional[str]  # e.g. "₹", "rides", "km", "stars" — for axis/label formatting
    raw_summary: Optional[dict]  # only populated for intent_type == "summary"


# ---------------------------------------------------------------------------
# Metric metadata — drives units and chart-type defaults
# ---------------------------------------------------------------------------

_METRIC_UNITS = {
    "ride_count": "rides",
    "total_revenue": "₹",
    "avg_booking_value": "₹",
    "avg_ride_distance": "km",
    "total_distance": "km",
    "avg_driver_rating": "stars",
    "avg_customer_rating": "stars",
}

_METRIC_LABELS = {
    "ride_count": "Ride count",
    "total_revenue": "Total revenue",
    "avg_booking_value": "Average booking value",
    "avg_ride_distance": "Average ride distance",
    "total_distance": "Total distance",
    "avg_driver_rating": "Average driver rating",
    "avg_customer_rating": "Average customer rating",
}


def format_for_visualization(result: QueryResult, question: str = "") -> FormattedResponse:
    """
    Convert a QueryResult into a chart-ready structure. Pure function, no
    network calls — every branch is deterministic based on intent_type.
    """
    if result.is_empty:
        return FormattedResponse(
            chart_type="none",
            title="No data found",
            labels=[],
            values=[],
            unit=None,
            raw_summary=None,
        )

    metric = result.metadata.get("metric")
    unit = _METRIC_UNITS.get(metric)
    metric_label = _METRIC_LABELS.get(metric, metric or "")

    handlers = {
        "summary": _format_summary,
        "top_n": _format_series_as_bar,
        "comparison": _format_series_as_bar,
        "time_series": _format_series_as_line,
        "distribution": _format_series_as_bar,
        "cancellation_reasons": _format_series_as_bar,
    }

    handler = handlers[result.intent_type]
    return handler(result, metric_label, unit)


def _format_summary(result: QueryResult, metric_label: str, unit: Optional[str]) -> FormattedResponse:
    return FormattedResponse(
        chart_type="kpi_cards",
        title="Overview",
        labels=[],
        values=[],
        unit=None,
        raw_summary=result.data,
    )


def _format_series_as_bar(result: QueryResult, metric_label: str, unit: Optional[str]) -> FormattedResponse:
    series: pd.Series = result.data
    labels = [str(x) for x in series.index.tolist()]
    values = [round(float(v), 2) if pd.notna(v) else 0 for v in series.values.tolist()]
    title = metric_label or result.intent_type.replace("_", " ").title()
    return FormattedResponse(
        chart_type="bar",
        title=title,
        labels=labels,
        values=values,
        unit=unit,
        raw_summary=None,
    )


def _format_series_as_line(result: QueryResult, metric_label: str, unit: Optional[str]) -> FormattedResponse:
    series: pd.Series = result.data
    labels = [str(x) for x in series.index.tolist()]
    values = [round(float(v), 2) if pd.notna(v) else 0 for v in series.values.tolist()]
    grain = result.metadata.get("grain", "")
    title = f"{metric_label or 'Value'} over {grain}" if grain else (metric_label or "Trend")
    return FormattedResponse(
        chart_type="line",
        title=title,
        labels=labels,
        values=values,
        unit=unit,
        raw_summary=None,
    )


# ---------------------------------------------------------------------------
# Narrative generation (Claude call)
# ---------------------------------------------------------------------------

NARRATIVE_SYSTEM_PROMPT = """You are a business analyst writing a short, direct \
answer to a question about Uber ride data (Delhi/NCR, full year 2025).

You will be given:
1. The user's original question
2. The exact numbers that answer it (already computed — do not question or \
recompute them)
3. Metadata about filters that were applied

Write a 1-4 sentence answer that:
- States the direct answer first
- Adds one relevant insight or comparison if the data supports it (e.g. "23% \
higher than the next vehicle type")
- Uses the numbers EXACTLY as given — never round differently, never invent \
figures not present in the data
- Mentions applied filters naturally if they narrow the scope (e.g. "In August, ...")
- Is plain, confident business language — no hedging, no "it appears that"

Do not describe the chart. Do not say "as you can see". Do not add a generic \
closing sentence. Just answer the question.
"""


def generate_narrative(
    question: str,
    formatted: FormattedResponse,
    metadata: dict,
    api_key: Optional[str] = None,
) -> str:
    """
    Generate a natural-language narrative answer using Claude, grounded
    strictly in the already-computed numbers (formatted.raw_summary or
    formatted.labels/values). Claude never sees the raw dataset here.
    """
    if anthropic is None:
        raise RuntimeError(
            "The 'anthropic' package is not installed. Run: "
            "pip install anthropic --break-system-packages"
        )
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("No Anthropic API key found (ANTHROPIC_API_KEY).")

    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(var, None)

    client = anthropic.Anthropic(
        api_key=key,
        timeout=60.0,
        max_retries=2,
    )

    if formatted.chart_type == "none":
        data_payload = "No rows matched the applied filters."
    elif formatted.raw_summary is not None:
        data_payload = str(formatted.raw_summary)
    else:
        data_payload = str(dict(zip(formatted.labels, formatted.values)))

    user_message = (
        f"Question: {question}\n\n"
        f"Computed data: {data_payload}\n\n"
        f"Unit: {formatted.unit or 'count'}\n"
        f"Filters applied: {metadata.get('filters_applied', {})}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=NARRATIVE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()


def generate_fallback_narrative(formatted: FormattedResponse, metadata: dict) -> str:
    """
    Deterministic, non-LLM narrative used when no API key is available or
    the narrative call fails. Not as fluent, but never wrong and never down.
    """
    if formatted.chart_type == "none":
        return "No rides matched those filters. Try widening the date range or removing a filter."

    if formatted.raw_summary is not None:
        s = formatted.raw_summary
        return (
            f"{s['total_rides']:,} total rides, {s['completion_rate']}% completed, "
            f"₹{s['total_revenue']:,.0f} in revenue from completed rides."
        )

    if not formatted.labels:
        return "No data to summarize."

    top_label = formatted.labels[0]
    top_value = formatted.values[0]
    unit = formatted.unit or ""
    return f"{top_label} leads with {top_value:,.2f} {unit}.".strip()
