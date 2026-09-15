"""
intent_classifier.py

Converts a natural-language question into a structured Intent (see
intent_schema.py) using the Claude API. This is the only module in the
system that talks to the LLM for the purpose of understanding the question
(a separate call, in response_formatter.py, handles generating the final
natural-language answer).

Requires the ANTHROPIC_API_KEY environment variable to be set.
"""

from __future__ import annotations

import json
import os
from datetime import date

from . import constants as C
from .intent_schema import Intent

try:
    import anthropic
    import httpx
except ImportError:
    anthropic = None
    httpx = None


MODEL = "claude-sonnet-4-6"

# Today's date is injected into the prompt so relative date phrases like
# "last month" or "this quarter" resolve correctly regardless of when the
# question is asked. The dataset itself covers all of 2025.
DATASET_DATE_MIN = C.EXPECTED_DATE_MIN
DATASET_DATE_MAX = C.EXPECTED_DATE_MAX


SYSTEM_PROMPT = f"""You are the intent-classification layer for an Uber ride-data \
analyst agent. Your ONLY job is to convert a user's natural-language question \
into a structured JSON intent object. You do not answer the question yourself.

DATASET CONTEXT:
- Ride data for Delhi/NCR, covering {DATASET_DATE_MIN} to {DATASET_DATE_MAX} (one full year).
- Vehicle types: {C.VEHICLE_TYPES}
- Booking statuses: {C.ALL_BOOKING_STATUSES}
- Payment methods: {C.PAYMENT_METHODS}
- Pickup/Drop locations: 176 named areas in Delhi/NCR (you do not have the full \
list memorized — pass through whatever location names the user mentions verbatim).
- Metrics available for financial/rating fields ONLY exist for Completed and \
Incomplete rides (cancelled rides have no Booking Value, Ride Distance, or ratings).

OUTPUT SCHEMA (return ONLY this JSON, nothing else, no markdown fences):
{{
  "intent_type": one of ["summary", "top_n", "comparison", "time_series", "distribution", "cancellation_reasons"],
  "metric": one of ["ride_count", "total_revenue", "avg_booking_value", "avg_ride_distance", "avg_driver_rating", "avg_customer_rating", "total_distance"] or null,
  "dimension": a column name to group by (e.g. "Vehicle Type", "Pickup Location", "Payment Method", "Booking Status") or null,
  "grain": one of ["day", "week", "month", "quarter", "day_of_week", "hour"] or null (only for time_series),
  "top_n": integer or null (only for top_n, default 10 if user says "top" without a number),
  "comparison_values": list of specific values being compared (e.g. ["Auto", "Go Sedan"]) or null (only for comparison),
  "cancellation_by": "customer" or "driver" or null (only for cancellation_reasons),
  "filters": {{
    "date_range": {{"start": "YYYY-MM-DD" or null, "end": "YYYY-MM-DD" or null}} or null,
    "statuses": list of booking statuses or null,
    "vehicle_types": list of vehicle types or null,
    "pickup_locations": list of location names or null,
    "drop_locations": list of location names or null,
    "payment_methods": list of payment methods or null
  }},
  "clarification_needed": boolean,
  "clarification_question": string or null (only if clarification_needed is true)
}}

INTENT TYPE GUIDE:
- "summary": broad/overview questions ("how's business doing", "give me an overview")
- "top_n": ranking questions ("top 5 locations", "most popular vehicle", "which X has the most Y")
- "comparison": explicitly comparing 2+ specific named things ("Auto vs Go Sedan", "compare UPI and Cash")
- "time_series": trend/change-over-time questions ("trend over months", "rides by hour of day")
- "distribution": spread/histogram questions ("distribution of ratings", "how are booking values spread")
- "cancellation_reasons": specifically about WHY cancellations happened

RULES:
1. If the question is genuinely ambiguous (e.g. "show me the data" with no clear metric \
or dimension), set clarification_needed=true and write a specific clarification_question. \
Do not guess wildly.
2. Default metric to "ride_count" when the user asks about volume/popularity without \
specifying revenue, distance, or ratings.
3. Resolve month names to the year 2025 (the only year in the dataset) unless the user \
specifies otherwise.
4. Never invent location names or vehicle types not implied by the user's question.
5. Return ONLY the JSON object. No prose, no markdown code fences.
"""


def classify_intent(question: str, api_key: str | None = None) -> Intent:
    """
    Classify a natural-language question into a structured Intent.

    Args:
        question: the user's raw question
        api_key: Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.

    Returns:
        Intent object (see intent_schema.py)

    Raises:
        RuntimeError: if the anthropic package isn't installed or no API key
            is available.
        ValueError: if Claude's response isn't valid JSON matching the schema.
    """
    if anthropic is None:
        raise RuntimeError(
            "The 'anthropic' package is not installed. Run: "
            "pip install anthropic --break-system-packages"
        )

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "No Anthropic API key found. Set the ANTHROPIC_API_KEY environment "
            "variable or pass api_key explicitly."
        )

    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(var, None)

    client = anthropic.Anthropic(
        api_key=key,
        timeout=60.0,
        max_retries=2,
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )

    raw_text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    # Defensive: strip markdown fences if the model added them despite instructions.
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Claude did not return valid JSON. Raw response: {raw_text!r}"
        ) from e

    intent = Intent.from_dict(parsed)
    errors = intent.validate()
    if errors and not intent.clarification_needed:
        raise ValueError(f"Intent failed validation: {errors}. Raw: {parsed!r}")

    return intent
