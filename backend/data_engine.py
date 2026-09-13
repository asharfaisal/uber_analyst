"""
data_engine.py

The single source of truth for loading and querying the Uber ride dataset.
Every function here is pure with respect to the input DataFrame (no hidden
global mutation) so results are predictable and testable.

Design principles:
- Load once, reuse the in-memory DataFrame everywhere (150k rows is trivial
  for pandas; no database needed).
- Every public function accepts a DataFrame explicitly rather than reaching
  into a global, which makes unit testing straightforward.
- Missing data is never silently dropped without a stated reason — cancelled
  rides legitimately have no Booking Value, Ride Distance, or ratings.
"""

from __future__ import annotations

import functools
from datetime import datetime
from typing import Optional

import pandas as pd

from . import constants as C


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _load_raw(path: str) -> pd.DataFrame:
    """Cached raw load from disk. Cached because Excel parsing of 150k rows
    takes noticeable time; we never want to repeat it within a process."""
    df = pd.read_excel(path, sheet_name=C.SHEET_MAIN)
    return df


def load_data(path: str = C.DATA_FILE_PATH) -> pd.DataFrame:
    """
    Load the Uber dataset and add convenience derived columns.

    Derived columns added:
        - hour: int, extracted from Time (0-23)
        - day_of_week: str, e.g. 'Monday'
        - month: int, 1-12
        - month_name: str, e.g. 'January'
        - week: int, ISO week number
        - quarter: int, 1-4
        - is_completed: bool, True only for STATUS_COMPLETED
        - is_cancelled: bool, True for either cancellation status
        - has_financials: bool, True if Booking Value is not null

    Returns a fresh copy each call (derived columns are cheap to recompute;
    the expensive Excel parse itself is cached).
    """
    df = _load_raw(path).copy()

    # --- Temporal derived fields ---
    df[C.COL_DATE] = pd.to_datetime(df[C.COL_DATE])
    df["hour"] = df[C.COL_TIME].apply(_extract_hour)
    df["day_of_week"] = df[C.COL_DATE].dt.day_name()
    df["month"] = df[C.COL_DATE].dt.month
    df["month_name"] = df[C.COL_DATE].dt.month_name()
    df["week"] = df[C.COL_DATE].dt.isocalendar().week.astype(int)
    df["quarter"] = df[C.COL_DATE].dt.quarter

    # --- Status derived flags ---
    df["is_completed"] = df[C.COL_BOOKING_STATUS] == C.STATUS_COMPLETED
    df["is_cancelled"] = df[C.COL_BOOKING_STATUS].isin(C.CANCELLED_STATUSES)
    df["has_financials"] = df[C.COL_BOOKING_VALUE].notna()

    return df


def _extract_hour(time_val) -> Optional[int]:
    """Extract hour (0-23) from a Time value that may be a string 'HH:MM:SS'
    or already a datetime.time object."""
    if pd.isna(time_val):
        return None
    if hasattr(time_val, "hour"):
        return time_val.hour
    try:
        return int(str(time_val).split(":")[0])
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Summary / overview
# ---------------------------------------------------------------------------

def get_summary(df: pd.DataFrame) -> dict:
    """High-level dataset summary: row count, date range, status breakdown,
    and headline financial metrics. This is the payload used to answer
    broad questions like 'give me an overview of the data'."""
    completed = df[df["is_completed"]]

    return {
        "total_rides": int(len(df)),
        "date_range": {
            "start": df[C.COL_DATE].min().strftime("%Y-%m-%d"),
            "end": df[C.COL_DATE].max().strftime("%Y-%m-%d"),
        },
        "status_breakdown": df[C.COL_BOOKING_STATUS].value_counts().to_dict(),
        "completion_rate": round(df["is_completed"].mean() * 100, 2),
        "total_revenue": round(completed[C.COL_BOOKING_VALUE].sum(), 2),
        "avg_booking_value": round(completed[C.COL_BOOKING_VALUE].mean(), 2),
        "avg_ride_distance": round(completed[C.COL_RIDE_DISTANCE].mean(), 2),
        "avg_driver_rating": round(completed[C.COL_DRIVER_RATING].mean(), 2),
        "avg_customer_rating": round(completed[C.COL_CUSTOMER_RATING].mean(), 2),
        "unique_customers": int(df[C.COL_CUSTOMER_ID].nunique()),
        "vehicle_types": df[C.COL_VEHICLE_TYPE].value_counts().to_dict(),
        "payment_methods": completed[C.COL_PAYMENT_METHOD].value_counts().to_dict(),
    }


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_by_date_range(
    df: pd.DataFrame, start_date: Optional[str], end_date: Optional[str]
) -> pd.DataFrame:
    """Filter rows to [start_date, end_date] inclusive. Either bound may be
    None to mean 'unbounded' on that side. Dates are ISO strings 'YYYY-MM-DD'."""
    result = df
    if start_date:
        result = result[result[C.COL_DATE] >= pd.Timestamp(start_date)]
    if end_date:
        result = result[result[C.COL_DATE] <= pd.Timestamp(end_date)]
    return result


def filter_by_status(df: pd.DataFrame, statuses: list[str]) -> pd.DataFrame:
    """Keep only rows whose Booking Status is in the given list."""
    return df[df[C.COL_BOOKING_STATUS].isin(statuses)]


def filter_by_vehicle_type(df: pd.DataFrame, vehicle_types: list[str]) -> pd.DataFrame:
    return df[df[C.COL_VEHICLE_TYPE].isin(vehicle_types)]


def filter_by_location(
    df: pd.DataFrame,
    pickup: Optional[list[str]] = None,
    drop: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Filter by pickup and/or drop location lists. Either may be None to
    skip that filter. If both given, rows must match both (AND)."""
    result = df
    if pickup:
        result = result[result[C.COL_PICKUP_LOCATION].isin(pickup)]
    if drop:
        result = result[result[C.COL_DROP_LOCATION].isin(drop)]
    return result


def filter_by_payment_method(df: pd.DataFrame, methods: list[str]) -> pd.DataFrame:
    return df[df[C.COL_PAYMENT_METHOD].isin(methods)]


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

_VALID_METRICS = {
    "ride_count": lambda g: g.size(),
    "total_revenue": lambda g: g[C.COL_BOOKING_VALUE].sum(),
    "avg_booking_value": lambda g: g[C.COL_BOOKING_VALUE].mean(),
    "avg_ride_distance": lambda g: g[C.COL_RIDE_DISTANCE].mean(),
    "avg_driver_rating": lambda g: g[C.COL_DRIVER_RATING].mean(),
    "avg_customer_rating": lambda g: g[C.COL_CUSTOMER_RATING].mean(),
    "total_distance": lambda g: g[C.COL_RIDE_DISTANCE].sum(),
}


def aggregate_by_metric(
    df: pd.DataFrame,
    metric: str,
    group_by: str | list[str],
    sort: bool = True,
) -> pd.Series:
    """
    Compute a metric grouped by one or more dimensions.

    Args:
        df: source DataFrame (already filtered as needed by the caller)
        metric: one of _VALID_METRICS keys (e.g. 'ride_count', 'total_revenue')
        group_by: column name or list of column names to group by
        sort: if True, sort descending by the metric value

    Returns:
        pd.Series indexed by group_by value(s), values are the metric.

    Raises:
        ValueError: if metric is not recognized.
    """
    if metric not in _VALID_METRICS:
        raise ValueError(
            f"Unknown metric '{metric}'. Valid options: {list(_VALID_METRICS)}"
        )
    grouped = df.groupby(group_by)
    result = _VALID_METRICS[metric](grouped)
    if sort:
        result = result.sort_values(ascending=False)
    return result


def get_top_n(
    df: pd.DataFrame,
    dimension: str,
    metric: str = "ride_count",
    n: int = 10,
    ascending: bool = False,
) -> pd.Series:
    """Return the top (or bottom) N values of `dimension` ranked by `metric`."""
    result = aggregate_by_metric(df, metric, dimension, sort=True)
    if ascending:
        result = result.sort_values(ascending=True)
    return result.head(n)


def get_time_series(
    df: pd.DataFrame,
    metric: str = "ride_count",
    grain: str = "month",
) -> pd.Series:
    """
    Compute a metric over time at the given granularity.

    Args:
        grain: one of 'day', 'week', 'month', 'quarter', 'day_of_week', 'hour'
    """
    grain_column_map = {
        "day": df[C.COL_DATE].dt.date,
        "week": df["week"],
        "month": df["month_name"],
        "quarter": df["quarter"],
        "day_of_week": df["day_of_week"],
        "hour": df["hour"],
    }
    if grain not in grain_column_map:
        raise ValueError(f"Unknown grain '{grain}'. Valid: {list(grain_column_map)}")

    grouped = df.groupby(grain_column_map[grain])
    result = _VALID_METRICS[metric](grouped)

    # For calendar-ordered grains, preserve natural order rather than sorting
    # by value — a revenue-over-months chart should read Jan -> Dec.
    if grain == "month":
        month_order = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        result = result.reindex([m for m in month_order if m in result.index])
    elif grain == "day_of_week":
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday",
                     "Friday", "Saturday", "Sunday"]
        result = result.reindex([d for d in day_order if d in result.index])
    else:
        result = result.sort_index()

    return result


def get_distribution(df: pd.DataFrame, field: str, bins: int = 10) -> pd.Series:
    """
    Get the distribution of a numeric field.
    - For categorical fields: value_counts.
    - For numeric fields: binned histogram counts.
    """
    if pd.api.types.is_numeric_dtype(df[field]):
        return pd.cut(df[field].dropna(), bins=bins).value_counts().sort_index()
    return df[field].value_counts()


def get_comparison(
    df: pd.DataFrame,
    metric: str,
    dimension: str,
    values: list[str],
) -> pd.Series:
    """Compare a metric across a specific, caller-chosen set of dimension
    values (e.g. compare 'Auto' vs 'Go Sedan' on avg_booking_value)."""
    subset = df[df[dimension].isin(values)]
    return aggregate_by_metric(subset, metric, dimension, sort=False).reindex(values)


def get_cancellation_reasons(df: pd.DataFrame, by: str = "customer") -> pd.Series:
    """
    Breakdown of cancellation reasons.
    Args:
        by: 'customer' or 'driver'
    """
    if by == "customer":
        subset = df[df[C.COL_BOOKING_STATUS] == C.STATUS_CANCELLED_BY_CUSTOMER]
        return subset[C.COL_CUSTOMER_CANCEL_REASON].value_counts()
    elif by == "driver":
        subset = df[df[C.COL_BOOKING_STATUS] == C.STATUS_CANCELLED_BY_DRIVER]
        return subset[C.COL_DRIVER_CANCEL_REASON].value_counts()
    else:
        raise ValueError("`by` must be 'customer' or 'driver'")
