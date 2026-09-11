"""Constants for the UA Alerts integration."""

from __future__ import annotations

DOMAIN = "ua_alerts"
NAME = "UA Alerts"
VERSION = "0.1.20"

SOURCE_URL = "https://ubilling.net.ua/aerialalerts/?source=aiu&raw"
DEFAULT_POLL_INTERVAL_SECONDS = 3.0
DEFAULT_STALE_AFTER_SECONDS = 15.0
MIN_POLL_INTERVAL_SECONDS = 3.0
MAX_POLL_INTERVAL_SECONDS = 60.0
MIN_STALE_AFTER_SECONDS = 6.0
MAX_STALE_AFTER_SECONDS = 600.0

# Backward-compatible names used by tests and pure runtime construction.
POLL_INTERVAL_SECONDS = DEFAULT_POLL_INTERVAL_SECONDS
STALE_AFTER_SECONDS = DEFAULT_STALE_AFTER_SECONDS

OPT_POLL_INTERVAL = "poll_interval"
OPT_STALE_AFTER = "stale_after"

CATALOG_URL = "https://docs.google.com/spreadsheets/d/1XnTOzcPHd1LZUrarR1Fk43FUyl8Ae6a6M7pcwDRjNdA/export?format=csv"
CATALOG_REQUEST_TIMEOUT_SECONDS = 10.0
REQUEST_TIMEOUT_SECONDS = 2.5
MAX_RUNTIME_ERRORS = 20

CONF_LOCATION_UID = "location_uid"
CONF_LOCATION_TITLE = "location_title"
CONF_LOCATION_TYPE = "location_type"

ALERT_TYPE_AIR_RAID = "air_raid"
ALERT_LEVEL_CLEAR = "clear"
ALERT_LEVEL_YELLOW = "yellow"
ALERT_LEVEL_RED = "red"
VALID_ALERT_LEVELS = frozenset({ALERT_LEVEL_YELLOW, ALERT_LEVEL_RED})
ALERT_LEVEL_PRIORITY = {
    ALERT_LEVEL_YELLOW: 1,
    ALERT_LEVEL_RED: 2,
}

ALERT_COVERAGE_NONE = "none"
ALERT_COVERAGE_FULL = "full"
ALERT_COVERAGE_PARTIAL = "partial"
ALERT_COVERAGE_MIXED = "mixed"
ALERT_COVERAGE_OPTIONS = (
    ALERT_COVERAGE_NONE,
    ALERT_COVERAGE_FULL,
    ALERT_COVERAGE_PARTIAL,
    ALERT_COVERAGE_MIXED,
)

THREAT_CODES_NONE = "none"

DATA_HEALTH_NORMAL = "normal"
DATA_HEALTH_DELAYED = "delayed"
DATA_HEALTH_SOURCE_ERROR = "source_error"
DATA_HEALTH_DATA_ERROR = "data_error"
DATA_HEALTH_OPTIONS = (
    DATA_HEALTH_NORMAL,
    DATA_HEALTH_DELAYED,
    DATA_HEALTH_SOURCE_ERROR,
    DATA_HEALTH_DATA_ERROR,
)

# Health sensor thresholds. End-to-end alert/threat latency is intentionally
# informational only and never makes aggregate data health "delayed".
HEALTH_SLOW_RESPONSE_SECONDS = 1.5
HEALTH_DETAILS_REFRESH_SECONDS = 30.0

LATENCY_STORAGE_VERSION = 1
LATENCY_STORAGE_KEY_FORMAT = "ua_alerts.latency.{location_uid}"

EVENT_ALERT_LEVEL_CHANGED = "ua_alert_level_changed"
EVENT_ALERT_THREATS_CHANGED = "ua_alert_threats_changed"
EVENT_SOURCE_AVAILABILITY_CHANGED = "ua_alert_source_availability_changed"

ATTR_THREATS = "threats"
ATTR_LEVEL_CODE = "level_code"
ATTR_POSSIBLE_LEVEL_CODES = "possible_level_codes"
ATTR_COVERAGE_CODE = "coverage_code"
ATTR_POSSIBLE_COVERAGE_CODES = "possible_coverage_codes"
ATTR_FULL_LEVEL_CODE = "full_level_code"
ATTR_PARTIAL_LEVEL_CODE = "partial_level_code"
ATTR_ACTIVE_FULL_ALERT_LOCATION_UIDS = "active_full_alert_location_uids"
ATTR_ACTIVE_PARTIAL_ALERT_LOCATION_UIDS = "active_partial_alert_location_uids"

ATTR_ALERT_SCOPE = "alert_scope"
ATTR_ALERT_SOURCE_LOCATION_UID = "alert_source_location_uid"
ATTR_ALERT_SOURCE_LOCATION_TITLE = "alert_source_location_title"
ATTR_ALERT_SOURCE_LOCATION_TYPE = "alert_source_location_type"
ATTR_ACTIVE_ALERT_LOCATION_UIDS = "active_alert_location_uids"
ATTR_THREAT_CODES_CSV = "threat_codes_csv"
ATTR_LOCATION_UID = "location_uid"
ATTR_OLD_LEVEL = "old_level"
ATTR_NEW_LEVEL = "new_level"
ATTR_THREAT_CODES = "threat_codes"
ATTR_POSSIBLE_THREAT_CODES = "possible_threat_codes"
ATTR_ALERT_STARTED_AT = "alert_started_at"
ATTR_ALERT_DETECTED_AT = "alert_detected_at"
ATTR_LAST_ALERT_STARTED_AT = "last_alert_started_at"
ATTR_LAST_ALERT_ENDED_AT = "last_alert_ended_at"
ATTR_LAST_ALERT_DURATION = "last_alert_duration"
ATTR_LAST_ALERT_LEVEL = "last_alert_level"
ATTR_LAST_ALERT_DELAY = "last_alert_delay"
ATTR_ALERT_LATENCY = "alert_latency"
ATTR_THREAT_CODE = "threat_code"
ATTR_THREAT_LEVEL_CODE = "threat_level_code"
ATTR_THREAT_STARTED_AT = "threat_started_at"
ATTR_THREAT_DETECTED_AT = "threat_detected_at"
ATTR_THREAT_LATENCY = "threat_latency"
ATTR_LAST_THREAT_DELAY = "last_threat_delay"
ATTR_THREAT_SOURCE_MESSAGE = "threat_source_message"
ATTR_SOURCE_UPDATED_AT = "source_updated_at"
ATTR_RECEIVED_AT = "received_at"

ATTR_HEALTH_DELAY_REASON = "delay_reason"
ATTR_SOURCE_RESPONSE_TIME = "source_response_time"
ATTR_CONSECUTIVE_ERRORS = "consecutive_errors"
ATTR_HTTP_STATUS = "http_status"
ATTR_LAST_ERROR = "last_error"

RUNTIME_STATUS_RUNNING = "running"
RUNTIME_STATUS_STOPPED = "stopped"
