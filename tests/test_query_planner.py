"""
test_query_planner.py

Tests the query planner using hand-crafted Intent objects — this validates
the planning/execution logic completely independently of the Claude API,
since Intent objects here are constructed directly rather than classified
from natural language.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import constants as C
from backend import data_engine as de
from backend import query_planner as qp
from backend.intent_schema import Intent, Filters


DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uber.xlsx")


@pytest.fixture(scope="module")
def df():
    return de.load_data(DATA_PATH)


class TestSummaryIntent:
    def test_basic_summary(self, df):
        intent = Intent(intent_type="summary")
        result = qp.execute_intent(df, intent)
        assert result.intent_type == "summary"
        assert result.is_empty is False
        assert result.data["total_rides"] == 150_000

    def test_summary_with_date_filter(self, df):
        intent = Intent(
            intent_type="summary",
            filters=Filters(date_start="2025-01-01", date_end="2025-01-31"),
        )
        result = qp.execute_intent(df, intent)
        assert result.row_count < 150_000
        assert result.data["total_rides"] == result.row_count


class TestTopNIntent:
    def test_top_n_vehicle_by_ride_count(self, df):
        intent = Intent(
            intent_type="top_n",
            metric="ride_count",
            dimension=C.COL_VEHICLE_TYPE,
            top_n=3,
        )
        result = qp.execute_intent(df, intent)
        assert len(result.data) == 3
        assert result.data.index[0] == "Auto"
        assert result.data.iloc[0] == 37_419

    def test_top_n_defaults_to_10(self, df):
        intent = Intent(intent_type="top_n", dimension=C.COL_PICKUP_LOCATION)
        result = qp.execute_intent(df, intent)
        assert len(result.data) == 10

    def test_top_n_with_status_filter(self, df):
        intent = Intent(
            intent_type="top_n",
            metric="total_revenue",
            dimension=C.COL_VEHICLE_TYPE,
            top_n=5,
            filters=Filters(statuses=[C.STATUS_COMPLETED]),
        )
        result = qp.execute_intent(df, intent)
        assert result.data.index[0] == "Auto"  # highest revenue vehicle


class TestComparisonIntent:
    def test_explicit_dimension(self, df):
        intent = Intent(
            intent_type="comparison",
            metric="ride_count",
            dimension=C.COL_VEHICLE_TYPE,
            comparison_values=["Auto", "Go Sedan"],
        )
        result = qp.execute_intent(df, intent)
        assert result.data["Auto"] == 37_419
        assert result.data["Go Sedan"] == 27_141

    def test_inferred_dimension(self, df):
        # dimension is None -> planner must infer it's Vehicle Type
        intent = Intent(
            intent_type="comparison",
            metric="ride_count",
            comparison_values=["Auto", "Bike"],
        )
        result = qp.execute_intent(df, intent)
        assert result.data["Auto"] == 37_419
        assert result.data["Bike"] == 22_517

    def test_inferred_dimension_payment_methods(self, df):
        intent = Intent(
            intent_type="comparison",
            metric="ride_count",
            comparison_values=["UPI", "Cash"],
        )
        result = qp.execute_intent(df, intent)
        assert result.data["UPI"] == 45_909
        assert result.data["Cash"] == 25_367


class TestTimeSeriesIntent:
    def test_monthly_trend(self, df):
        intent = Intent(intent_type="time_series", metric="ride_count", grain="month")
        result = qp.execute_intent(df, intent)
        assert result.data.sum() == 150_000
        assert list(result.data.index)[0] == "January"

    def test_hourly_trend(self, df):
        intent = Intent(intent_type="time_series", metric="ride_count", grain="hour")
        result = qp.execute_intent(df, intent)
        assert len(result.data) == 24


class TestDistributionIntent:
    def test_categorical_distribution(self, df):
        intent = Intent(intent_type="distribution", dimension=C.COL_PAYMENT_METHOD)
        result = qp.execute_intent(df, intent)
        assert result.data["UPI"] == 45_909

    def test_numeric_distribution_via_metric(self, df):
        intent = Intent(intent_type="distribution", metric="avg_booking_value")
        result = qp.execute_intent(df, intent)
        # Should resolve to Booking Value column and bin it
        assert result.data.sum() == df[C.COL_BOOKING_VALUE].notna().sum()


class TestCancellationReasonsIntent:
    def test_customer_reasons(self, df):
        intent = Intent(intent_type="cancellation_reasons", cancellation_by="customer")
        result = qp.execute_intent(df, intent)
        assert result.data.sum() == 10_500

    def test_driver_reasons(self, df):
        intent = Intent(intent_type="cancellation_reasons", cancellation_by="driver")
        result = qp.execute_intent(df, intent)
        assert result.data.sum() == 27_000


class TestEmptyResults:
    def test_impossible_filter_combo_returns_empty(self, df):
        # No rides exist outside the dataset's date range
        intent = Intent(
            intent_type="summary",
            filters=Filters(date_start="2026-01-01", date_end="2026-12-31"),
        )
        result = qp.execute_intent(df, intent)
        assert result.is_empty is True
        assert result.row_count == 0
        assert result.data is None


class TestValidation:
    def test_invalid_intent_type_raises(self, df):
        intent = Intent(intent_type="not_a_real_type")
        with pytest.raises(ValueError):
            qp.execute_intent(df, intent)

    def test_time_series_without_grain_raises(self, df):
        intent = Intent(intent_type="time_series", metric="ride_count")
        with pytest.raises(ValueError):
            qp.execute_intent(df, intent)

    def test_top_n_without_dimension_raises(self, df):
        intent = Intent(intent_type="top_n", metric="ride_count")
        with pytest.raises(ValueError):
            qp.execute_intent(df, intent)


class TestFilterDescription:
    def test_metadata_echoes_filters(self, df):
        intent = Intent(
            intent_type="top_n",
            dimension=C.COL_VEHICLE_TYPE,
            filters=Filters(
                date_start="2025-06-01",
                date_end="2025-06-30",
                vehicle_types=["Auto", "Bike"],
            ),
        )
        result = qp.execute_intent(df, intent)
        assert "date_range" in result.metadata["filters_applied"]
        assert "vehicle_types" in result.metadata["filters_applied"]
