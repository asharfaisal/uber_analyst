"""
test_data_engine.py

Validates data_engine.py against known values from the discovery phase.
Every test either checks an exact count (things we know precisely from
discovery) or a sanity bound (things that should just be internally
consistent).
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import constants as C
from backend import data_engine as de


DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "uber.xlsx")


@pytest.fixture(scope="module")
def df():
    return de.load_data(DATA_PATH)


# ---------------------------------------------------------------------------
# Loading & derived columns
# ---------------------------------------------------------------------------

class TestLoading:
    def test_row_count(self, df):
        assert len(df) == C.EXPECTED_ROW_COUNT

    def test_date_range(self, df):
        assert df[C.COL_DATE].min().strftime("%Y-%m-%d") == C.EXPECTED_DATE_MIN
        assert df[C.COL_DATE].max().strftime("%Y-%m-%d") == C.EXPECTED_DATE_MAX

    def test_no_duplicates(self, df):
        assert df.duplicated().sum() == 0

    def test_derived_columns_exist(self, df):
        for col in ["hour", "day_of_week", "month", "month_name",
                    "week", "quarter", "is_completed", "is_cancelled",
                    "has_financials"]:
            assert col in df.columns

    def test_hour_extraction_range(self, df):
        hours = df["hour"].dropna()
        assert hours.min() >= 0
        assert hours.max() <= 23

    def test_is_completed_flag_matches_status(self, df):
        completed_by_flag = df[df["is_completed"]]
        completed_by_status = df[df[C.COL_BOOKING_STATUS] == C.STATUS_COMPLETED]
        assert len(completed_by_flag) == len(completed_by_status)

    def test_month_name_reflects_month_number(self, df):
        sample = df.sample(50, random_state=42)
        for _, row in sample.iterrows():
            assert row[C.COL_DATE].month == row["month"]
            assert row[C.COL_DATE].month_name() == row["month_name"]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_total_rides(self, df):
        summary = de.get_summary(df)
        assert summary["total_rides"] == 150_000

    def test_status_breakdown_matches_known_counts(self, df):
        summary = de.get_summary(df)
        breakdown = summary["status_breakdown"]
        assert breakdown[C.STATUS_COMPLETED] == 93_000
        assert breakdown[C.STATUS_CANCELLED_BY_DRIVER] == 27_000
        assert breakdown[C.STATUS_CANCELLED_BY_CUSTOMER] == 10_500
        assert breakdown[C.STATUS_NO_DRIVER_FOUND] == 10_500
        assert breakdown[C.STATUS_INCOMPLETE] == 9_000

    def test_completion_rate(self, df):
        summary = de.get_summary(df)
        assert summary["completion_rate"] == pytest.approx(62.0, abs=0.1)

    def test_avg_booking_value_matches_discovery(self, df):
        summary = de.get_summary(df)
        # Discovery found mean booking value ~508.30 across all rows with
        # financials (completed + incomplete). get_summary only averages
        # over 'completed', so we expect it close but not identical —
        # sanity bound instead of exact match.
        assert 400 < summary["avg_booking_value"] < 600

    def test_vehicle_type_counts(self, df):
        summary = de.get_summary(df)
        vt = summary["vehicle_types"]
        assert vt["Auto"] == 37_419
        assert vt["Go Mini"] == 29_806
        assert vt["Uber XL"] == 4_449


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

class TestFiltering:
    def test_filter_by_date_range_bounds(self, df):
        result = de.filter_by_date_range(df, "2025-01-01", "2025-01-31")
        assert result[C.COL_DATE].min() >= pd.Timestamp("2025-01-01")
        assert result[C.COL_DATE].max() <= pd.Timestamp("2025-01-31")
        assert len(result) > 0

    def test_filter_by_date_range_unbounded_start(self, df):
        result = de.filter_by_date_range(df, None, "2025-01-31")
        assert result[C.COL_DATE].max() <= pd.Timestamp("2025-01-31")

    def test_filter_by_status_single(self, df):
        result = de.filter_by_status(df, [C.STATUS_COMPLETED])
        assert len(result) == 93_000
        assert (result[C.COL_BOOKING_STATUS] == C.STATUS_COMPLETED).all()

    def test_filter_by_status_multiple(self, df):
        result = de.filter_by_status(
            df, [C.STATUS_CANCELLED_BY_CUSTOMER, C.STATUS_CANCELLED_BY_DRIVER]
        )
        assert len(result) == 10_500 + 27_000

    def test_filter_by_vehicle_type(self, df):
        result = de.filter_by_vehicle_type(df, ["Auto"])
        assert len(result) == 37_419
        assert (result[C.COL_VEHICLE_TYPE] == "Auto").all()

    def test_filter_by_location_pickup_only(self, df):
        result = de.filter_by_location(df, pickup=["Khandsa"])
        assert (result[C.COL_PICKUP_LOCATION] == "Khandsa").all()
        assert len(result) == 949

    def test_filter_by_payment_method(self, df):
        result = de.filter_by_payment_method(df, ["UPI"])
        assert (result[C.COL_PAYMENT_METHOD] == "UPI").all()
        assert len(result) == 45_909


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

class TestAggregation:
    def test_aggregate_ride_count_by_vehicle(self, df):
        result = de.aggregate_by_metric(df, "ride_count", C.COL_VEHICLE_TYPE)
        assert result.iloc[0] == 37_419  # Auto should be #1
        assert result.index[0] == "Auto"

    def test_aggregate_unknown_metric_raises(self, df):
        with pytest.raises(ValueError):
            de.aggregate_by_metric(df, "not_a_real_metric", C.COL_VEHICLE_TYPE)

    def test_aggregate_total_revenue_by_status(self, df):
        result = de.aggregate_by_metric(df, "total_revenue", C.COL_BOOKING_STATUS)
        # Cancelled/No Driver Found statuses have no booking value -> NaN sum -> 0
        assert result[C.STATUS_COMPLETED] > 0

    def test_get_top_n_default(self, df):
        result = de.get_top_n(df, C.COL_VEHICLE_TYPE, n=3)
        assert len(result) == 3
        assert result.index[0] == "Auto"

    def test_get_top_n_ascending(self, df):
        result = de.get_top_n(df, C.COL_VEHICLE_TYPE, n=1, ascending=True)
        assert result.index[0] == "Uber XL"  # smallest count


# ---------------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------------

class TestTimeSeries:
    def test_time_series_by_month_order(self, df):
        result = de.get_time_series(df, "ride_count", grain="month")
        assert list(result.index)[:3] == ["January", "February", "March"]

    def test_time_series_by_month_sums_to_total(self, df):
        result = de.get_time_series(df, "ride_count", grain="month")
        assert result.sum() == 150_000

    def test_time_series_by_day_of_week_order(self, df):
        result = de.get_time_series(df, "ride_count", grain="day_of_week")
        assert list(result.index)[0] == "Monday"
        assert list(result.index)[-1] == "Sunday"

    def test_time_series_invalid_grain_raises(self, df):
        with pytest.raises(ValueError):
            de.get_time_series(df, "ride_count", grain="not_a_grain")


# ---------------------------------------------------------------------------
# Distribution
# ---------------------------------------------------------------------------

class TestDistribution:
    def test_distribution_categorical(self, df):
        result = de.get_distribution(df, C.COL_VEHICLE_TYPE)
        assert result["Auto"] == 37_419

    def test_distribution_numeric_bins(self, df):
        result = de.get_distribution(df, C.COL_BOOKING_VALUE, bins=5)
        assert len(result) == 5
        assert result.sum() == df[C.COL_BOOKING_VALUE].notna().sum()


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

class TestComparison:
    def test_comparison_two_vehicle_types(self, df):
        result = de.get_comparison(
            df, "ride_count", C.COL_VEHICLE_TYPE, ["Auto", "Go Mini"]
        )
        assert result["Auto"] == 37_419
        assert result["Go Mini"] == 29_806
        assert list(result.index) == ["Auto", "Go Mini"]  # preserves order


# ---------------------------------------------------------------------------
# Cancellation reasons
# ---------------------------------------------------------------------------

class TestCancellationReasons:
    def test_customer_cancellation_reasons_sum(self, df):
        result = de.get_cancellation_reasons(df, by="customer")
        assert result.sum() == 10_500

    def test_driver_cancellation_reasons_sum(self, df):
        result = de.get_cancellation_reasons(df, by="driver")
        assert result.sum() == 27_000

    def test_invalid_by_raises(self, df):
        with pytest.raises(ValueError):
            de.get_cancellation_reasons(df, by="nobody")
