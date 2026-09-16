"""
api/analyze.py

Vercel Python serverless function. Single endpoint: POST /api/analyze
Body: {"question": "<natural language question>"}

Response (success):
{
  "needs_clarification": false,
  "narrative": "...",
  "chart_type": "bar" | "line" | "kpi_cards" | "none",
  "title": "...",
  "labels": [...],
  "values": [...],
  "unit": "₹" | "rides" | "km" | "stars" | null,
  "raw_summary": {...} | null,   // only for chart_type == "kpi_cards"
  "row_count": <int>
}

Response (needs clarification):
{ "needs_clarification": true, "clarification_question": "..." }

The dataset is loaded once per warm serverless instance (module-level cache)
rather than once per request, since re-parsing a 150k-row Excel file on
every invocation would be far too slow for a chat-like experience.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import data_engine as de
from backend import intent_classifier as ic
from backend import rule_based_classifier as rbc
from backend import query_planner as qp
from backend import response_formatter as rf

_df_cache = None


def _get_df():
    """Load and cache the dataset for the lifetime of this warm instance."""
    global _df_cache
    if _df_cache is None:
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "uber.xlsx")
        _df_cache = de.load_data(data_path)
    return _df_cache


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        # CORS preflight
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw_body or b"{}")
            question = (body.get("question") or "").strip()

            if not question:
                self._send(400, {"error": "The 'question' field is required."})
                return

            df = _get_df()

            used_classifier = "llm"
            try:
                intent = ic.classify_intent(question)
            except Exception:
                intent = rbc.classify_intent_rule_based(question)
                used_classifier = "rule_based"

            if intent.clarification_needed:
                self._send(200, {
                    "needs_clarification": True,
                    "clarification_question": intent.clarification_question,
                })
                return

            result = qp.execute_intent(df, intent)
            formatted = rf.format_for_visualization(result, question)

            try:
                narrative = rf.generate_narrative(question, formatted, result.metadata)
            except Exception:
                # Narrative generation is a nice-to-have on top of correct
                # data; never let it take down the whole response.
                narrative = rf.generate_fallback_narrative(formatted, result.metadata)

                self._send(200, {
                "needs_clarification": False,
                "narrative": narrative,
                "chart_type": formatted.chart_type,
                "title": formatted.title,
                "labels": formatted.labels,
                "values": formatted.values,
                "unit": formatted.unit,
                "raw_summary": formatted.raw_summary,
                "row_count": result.row_count,
                "classifier_used": used_classifier,
                })

        except Exception as e:  # noqa: BLE001 - last-resort safety net
            self._send(500, {"error": f"Unexpected server error: {e}"})

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, status: int, payload: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))
