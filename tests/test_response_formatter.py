"""
test_response_formatter.py

Tests the deterministic parts of response_formatter.py: format_for_visualization
and generate_fallback_narrative. Both run without any API access, so these
tests validate the full non-LLM path end-to-end using the real dataset.

generate_narrative() (the Claude-powered version) is NOT tested here since
it requires a live API key — see test_response_formatter_live.py (skipped
by default) for that.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import constants as C
from backend import data_engine as de
from backend import query_planner as qp
from backend import response_formatter as rf
from backend.intent_schema import Intent, Filters


DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uber.xlsx")


@pytest.fixture(scope="module")
def df():
    return de.load_data(DATA_PATH)


class TestSummaryFormatting:
    def test_summary_becomes_kpi_cards(self, df):
        intent = Intent(intent_type="summary")
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        assert formatted.chart_type == "kpi_cards"
        assert formatted.raw_summary["total_rides"] == 150_000

    def test_summary_fallback_narrative(self, df):
        intent = Intent(intent_type="summary")
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        narrative = rf.generate_fallback_narrative(formatted, result.metadata)
        assert "150,000" in narrative
        assert "%" in narrative


class TestTopNFormatting:
    def test_top_n_becomes_bar_chart(self, df):
        intent = Intent(
            intent_type="top_n", metric="ride_count",
            dimension=C.COL_VEHICLE_TYPE, top_n=5,
        )
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        assert formatted.chart_type == "bar"
        assert len(formatted.labels) == 5
        assert len(formatted.values) == 5
        assert formatted.labels[0] == "Auto"
        assert formatted.values[0] == 37419
        assert formatted.unit == "rides"

    def test_top_n_revenue_has_currency_unit(self, df):
        intent = Intent(
            intent_type="top_n", metric="total_revenue",
            dimension=C.COL_VEHICLE_TYPE, top_n=3,
            filters=Filters(statuses=[C.STATUS_COMPLETED]),
        )
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        assert formatted.unit == "₹"
        assert formatted.title == "Total revenue"

    def test_top_n_fallback_narrative_mentions_leader(self, df):
        intent = Intent(
            intent_type="top_n", metric="ride_count",
            dimension=C.COL_VEHICLE_TYPE, top_n=5,
        )
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        narrative = rf.generate_fallback_narrative(formatted, result.metadata)
        assert "Auto" in narrative
        assert "37,419" in narrative or "37419" in narrative


class TestComparisonFormatting:
    def test_comparison_becomes_bar_chart(self, df):
        intent = Intent(
            intent_type="comparison", metric="ride_count",
            comparison_values=["Auto", "Go Sedan"],
        )
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        assert formatted.chart_type == "bar"
        assert formatted.labels == ["Auto", "Go Sedan"]
        assert formatted.values == [37419.0, 27141.0]


class TestTimeSeriesFormatting:
    def test_time_series_becomes_line_chart(self, df):
        intent = Intent(intent_type="time_series", metric="ride_count", grain="month")
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        assert formatted.chart_type == "line"
        assert len(formatted.labels) == 12
        assert formatted.labels[0] == "January"
        assert "month" in formatted.title


class TestDistributionFormatting:
    def test_distribution_becomes_bar_chart(self, df):
        intent = Intent(intent_type="distribution", dimension=C.COL_PAYMENT_METHOD)
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        assert formatted.chart_type == "bar"
        assert "UPI" in formatted.labels


class TestCancellationReasonsFormatting:
    def test_cancellation_reasons_becomes_bar_chart(self, df):
        intent = Intent(intent_type="cancellation_reasons", cancellation_by="driver")
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        assert formatted.chart_type == "bar"
        assert sum(formatted.values) == 27_000


class TestEmptyResultFormatting:
    def test_empty_result_becomes_none_chart(self, df):
        intent = Intent(
            intent_type="summary",
            filters=Filters(date_start="2026-01-01", date_end="2026-12-31"),
        )
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        assert formatted.chart_type == "none"
        assert formatted.labels == []

    def test_empty_result_fallback_narrative(self, df):
        intent = Intent(
            intent_type="summary",
            filters=Filters(date_start="2026-01-01", date_end="2026-12-31"),
        )
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        narrative = rf.generate_fallback_narrative(formatted, result.metadata)
        assert "No rides matched" in narrative


class TestJSONSerializability:
    """Ensures the formatted output can actually cross the Python -> React
    boundary as JSON — a real requirement, not just a nice-to-have."""

    def test_top_n_output_is_json_serializable(self, df):
        import json
        intent = Intent(
            intent_type="top_n", metric="ride_count",
            dimension=C.COL_VEHICLE_TYPE, top_n=5,
        )
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        payload = {
            "chart_type": formatted.chart_type,
            "title": formatted.title,
            "labels": formatted.labels,
            "values": formatted.values,
            "unit": formatted.unit,
        }
        serialized = json.dumps(payload)
        assert json.loads(serialized) == payload

    def test_summary_output_is_json_serializable(self, df):
        import json
        intent = Intent(intent_type="summary")
        result = qp.execute_intent(df, intent)
        formatted = rf.format_for_visualization(result)
        serialized = json.dumps(formatted.raw_summary)
        assert json.loads(serialized) is not None
