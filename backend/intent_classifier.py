"""
intent_classifier.py

Converts a natural-language question into a structured Intent (see
intent_schema.py) using Groq's chat completions API (OpenAI-compatible,
free tier). This is the only module in the system that talks to the LLM for
the purpose of understanding the question (a separate call, in
response_formatter.py, handles generating the final natural-language answer).

Supports conversation history so follow-up questions like "what about in
August?" or "and by revenue instead?" can be resolved using the context of
the previous question -- the history is included in the prompt as plain
text, not sent as separate chat turns, since we only want it to inform
intent extraction, not have the model "chat" about past answers.

Requires the GROQ_API_KEY environment variable to be set. Get a free key at
https://console.groq.com/keys
"""

from __future__ import annotations

import json
import os
import re

from . import constants as C
from .intent_schema import Intent

try:
    import groq
except ImportError:
    groq = None


MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

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

You may be given a short history of the previous question(s) and answer(s) in this \
conversation. Use it ONLY to resolve follow-up questions that depend on context \
(e.g. "what about in August?" after a question about vehicle types should reuse \
"vehicle type" as the dimension; "and by revenue?" should keep the prior filters \
but change the metric). If the current question is fully self-contained, ignore \
the history.

OUTPUT SCHEMA (return ONLY this JSON, nothing else, no markdown fences, no commentary):
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
or dimension, and no resolvable history), set clarification_needed=true and write a \
specific clarification_question. Do not guess wildly.
2. Default metric to "ride_count" when the user asks about volume/popularity without \
specifying revenue, distance, or ratings.
3. Resolve month names to the year 2025 (the only year in the dataset) unless the user \
specifies otherwise.
4. Never invent location names or vehicle types not implied by the user's question.
5. Return ONLY the JSON object. No prose, no markdown code fences, no commentary before or after.
"""


def classify_intent(
    question: str,
    conversation_history: list[dict] | None = None,
    api_key: str | None = None,
) -> Intent:
    """
    Classify a natural-language question into a structured Intent.

    Args:
        question: the user's raw question
        conversation_history: optional list of {"question": str, "narrative": str}
            dicts from prior turns in this conversation, most recent last.
            Used to resolve follow-up questions. Pass the last 3-5 turns at
            most -- more than that adds cost without adding useful context.
        api_key: Groq API key. Falls back to GROQ_API_KEY env var.

    Returns:
        Intent object (see intent_schema.py)

    Raises:
        RuntimeError: if the groq package isn't installed or no API key is
            available.
        ValueError: if the model's response isn't valid JSON matching the schema.
    """
    if groq is None:
        raise RuntimeError(
            "The 'groq' package is not installed. Run: "
            "pip install groq --break-system-packages"
        )

    key = (api_key or os.environ.get("GROQ_API_KEY") or "").strip()
    if not key:
        raise RuntimeError(
            "No Groq API key found. Set the GROQ_API_KEY environment "
            "variable or pass api_key explicitly."
        )

    # Clear stray proxy env vars that can cause spurious connection errors
    # in some serverless environments.
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(var, None)

    client = groq.Groq(api_key=key, timeout=60.0, max_retries=2)

    user_content = _build_user_message(question, conversation_history)

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=1000,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    raw_text = response.choices[0].message.content.strip()
    parsed = _parse_json_response(raw_text)

    intent = Intent.from_dict(parsed)
    errors = intent.validate()
    if errors and not intent.clarification_needed:
        raise ValueError(f"Intent failed validation: {errors}. Raw: {parsed!r}")

    return intent


def _build_user_message(question: str, history: list[dict] | None) -> str:
    if not history:
        return question

    lines = ["Previous conversation (most recent last):"]
    for turn in history[-5:]:
        lines.append(f"Q: {turn.get('question', '')}")
        lines.append(f"A: {turn.get('narrative', '')}")
    lines.append("")
    lines.append(f"Current question: {question}")
    return "\n".join(lines)


def _parse_json_response(raw_text: str) -> dict:
    """Defensively extract a JSON object from the model's response, in case
    it added markdown fences or stray commentary despite instructions."""
    text = raw_text.strip()

    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Last resort: find the first {...} block in the text.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Model did not return valid JSON. Raw response: {raw_text!r}"
            ) from e

    raise ValueError(f"Model did not return valid JSON. Raw response: {raw_text!r}")
