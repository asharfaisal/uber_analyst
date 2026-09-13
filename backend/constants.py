"""
constants.py

Central source of truth for dataset vocabulary: column names, categorical
values, and derived groupings. Keeping these in one place means the rest of
the codebase never hardcodes strings that could silently drift from the
actual data.
"""

# ---------------------------------------------------------------------------
# Column names (exactly as they appear in uber.xlsx / Sheet1)
# ---------------------------------------------------------------------------
COL_DATE = "Date"
COL_TIME = "Time"
COL_BOOKING_ID = "Booking ID"
COL_BOOKING_STATUS = "Booking Status"
COL_CUSTOMER_ID = "Customer ID"
COL_VEHICLE_TYPE = "Vehicle Type"
COL_PICKUP_LOCATION = "Pickup Location"
COL_DROP_LOCATION = "Drop Location"
COL_CANCELLED_BY_CUSTOMER = "Cancelled Rides by Customer"
COL_CUSTOMER_CANCEL_REASON = "Reason for cancelling by Customer"
COL_CANCELLED_BY_DRIVER = "Cancelled Rides by Driver"
COL_DRIVER_CANCEL_REASON = "Driver Cancellation Reason"
COL_INCOMPLETE_RIDES = "Incomplete Rides"
COL_INCOMPLETE_REASON = "Incomplete Rides Reason"
COL_BOOKING_VALUE = "Booking Value"
COL_RIDE_DISTANCE = "Ride Distance"
COL_DRIVER_RATING = "Driver Ratings"
COL_CUSTOMER_RATING = "Customer Rating"
COL_PAYMENT_METHOD = "Payment Method"

ALL_COLUMNS = [
    COL_DATE, COL_TIME, COL_BOOKING_ID, COL_BOOKING_STATUS, COL_CUSTOMER_ID,
    COL_VEHICLE_TYPE, COL_PICKUP_LOCATION, COL_DROP_LOCATION,
    COL_CANCELLED_BY_CUSTOMER, COL_CUSTOMER_CANCEL_REASON,
    COL_CANCELLED_BY_DRIVER, COL_DRIVER_CANCEL_REASON,
    COL_INCOMPLETE_RIDES, COL_INCOMPLETE_REASON,
    COL_BOOKING_VALUE, COL_RIDE_DISTANCE, COL_DRIVER_RATING,
    COL_CUSTOMER_RATING, COL_PAYMENT_METHOD,
]

# ---------------------------------------------------------------------------
# Categorical values
# ---------------------------------------------------------------------------
STATUS_COMPLETED = "Completed"
STATUS_CANCELLED_BY_DRIVER = "Cancelled by Driver"
STATUS_CANCELLED_BY_CUSTOMER = "Cancelled by Customer"
STATUS_NO_DRIVER_FOUND = "No Driver Found"
STATUS_INCOMPLETE = "Incomplete"

ALL_BOOKING_STATUSES = [
    STATUS_COMPLETED,
    STATUS_CANCELLED_BY_DRIVER,
    STATUS_CANCELLED_BY_CUSTOMER,
    STATUS_NO_DRIVER_FOUND,
    STATUS_INCOMPLETE,
]

# Statuses where financial/ratings data exists
STATUSES_WITH_FINANCIALS = [STATUS_COMPLETED, STATUS_INCOMPLETE]
# Statuses where ratings exist (only fully completed rides are rated)
STATUSES_WITH_RATINGS = [STATUS_COMPLETED]
# Statuses considered "cancelled" for cancellation-rate calculations
CANCELLED_STATUSES = [STATUS_CANCELLED_BY_DRIVER, STATUS_CANCELLED_BY_CUSTOMER]

VEHICLE_TYPES = [
    "Auto",
    "Go Mini",
    "Go Sedan",
    "Bike",
    "Premier Sedan",
    "eBike",
    "Uber XL",
]

PAYMENT_METHODS = [
    "UPI",
    "Cash",
    "Uber Wallet",
    "Credit Card",
    "Debit Card",
]

CUSTOMER_CANCEL_REASONS = [
    "Wrong Address",
    "Change of plans",
    "Driver is not moving towards pickup location",
    "Driver asked to cancel",
    "AC is not working",
]

DRIVER_CANCEL_REASONS = [
    "Customer related issue",
    "The customer was coughing/sick",
    "Personal & Car related issues",
    "More than permitted people in there",
]

INCOMPLETE_RIDE_REASONS = [
    "Customer Demand",
    "Vehicle Breakdown",
    "Other Issue",
]

# ---------------------------------------------------------------------------
# Dataset facts (from discovery — used for sanity checks / tests)
# ---------------------------------------------------------------------------
EXPECTED_ROW_COUNT = 150_000
EXPECTED_COLUMN_COUNT = 19
EXPECTED_DATE_MIN = "2025-01-01"
EXPECTED_DATE_MAX = "2025-12-30"
EXPECTED_PICKUP_LOCATIONS = 176
EXPECTED_DROP_LOCATIONS = 176

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
DATA_FILE_PATH = "data/uber.xlsx"
SHEET_MAIN = "Sheet1"
SHEET_VEHICLE_IMAGES = "Veh_IMG"
SHEET_STATUS_IMAGES = "Sheet3"
