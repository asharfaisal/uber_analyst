"""
intent_classifier.py

Groq-powered classifier (OpenAI-compatible, free tier). Falls back to
rule_based_classifier.py automatically in api/analyze.py if this fails.
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

MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
DATASET_DATE_MIN = C.EXPECTED_DATE_MIN
DATASET_DATE_MAX = C.EXPECTED_DATE_MAX

SYSTEM_PROMPT = f"""You are the intent-classification layer for an Uber ride-data \
analyst agent. Convert the user's question into a structured JSON intent object only.

DATASET CONTEXT:
- Ride data for Delhi/NCR, covering {DATASET_DATE_MIN} to {DATASET_DATE_MAX}.
- Vehicle types: {C.VEHICLE_TYPES}
- Booking statuses: {C.ALL_BOOKING_STATUSES}
- Payment methods: {C.PAYMENT_METHODS}
- Pickup/Drop locations: 176 named areas — pass through names verbatim.
- Financial/rating fields only exist for Completed and Incomplete rides.

You may receive prior Q&A history to resolve follow-ups (e.g. "what about in August?").

OUTPUT SCHEMA (JSON ONLY, no fences, no commentary):
{{
  "intent_type": one of ["summary", "top_n", "comparison", "time_series", "distribution", "cancellation_reasons"],
  "metric": one of ["ride_count", "total_revenue", "avg_booking_value", "avg_ride_distance", "avg_driver_rating", "avg_customer_rating", "total_distance", "unique_customers", "completion_rate"] or null,
  "dimension": column name or null,
  "grain": one of ["day", "week", "month", "quarter", "day_of_week", "hour"] or null,
  "top_n": integer or null (default 10),
  "comparison_values": list of specific values or null,
  "cancellation_by": "customer" or "driver" or null,
  "filters": {{
    "date_range": {{"start": "YYYY-MM-DD" or null, "end": "YYYY-MM-DD" or null}} or null,
    "statuses": list or null, "vehicle_types": list or null,
    "pickup_locations": list or null, "drop_locations": list or null,
    "payment_methods": list or null
  }},
  "clarification_needed": boolean,
  "clarification_question": string or null
}}

RULES:
1. If genuinely ambiguous, set clarification_needed=true with a specific question.
2. Comparison questions MUST include comparison_values for every item being compared.
3. Default metric to "ride_count" for volume/popularity questions.
4. Resolve month names to 2025 (the only year present).
5. Never invent location/vehicle names not implied by the question.
6. Return ONLY the JSON object.
"""


def classify_intent(question: str, conversation_history=None, api_key=None) -> Intent:
    if groq is None:
        raise RuntimeError("The 'groq' package is not installed.")

    key = (api_key or os.environ.get("GROQ_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("No Groq API key found (GROQ_API_KEY).")

    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(var, None)

    client = groq.Groq(api_key=key, timeout=60.0, max_retries=2)
    user_content = _build_user_message(question, conversation_history)

    response = client.chat.completions.create(
        model=MODEL, max_tokens=1000, temperature=0,
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


def _build_user_message(question: str, history) -> str:
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
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            raise ValueError(f"Model did not return valid JSON: {raw_text!r}") from e
    raise ValueError(f"Model did not return valid JSON: {raw_text!r}")