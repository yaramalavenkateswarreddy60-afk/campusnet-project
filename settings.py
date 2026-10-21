"""
CampusNet: System Configuration & Dynamic Thresholds Module
Manages runtime settings, multi-metric congestion thresholds, and network enforcement gates.
"""

from datetime import datetime, timezone
from database.db import get_db

DEFAULT_SETTINGS = {
    "threshold_warning_utilization": "70.0",
    "threshold_critical_utilization": "85.0",
    "threshold_warning_latency_ms": "50.0",
    "threshold_critical_latency_ms": "100.0",
    "threshold_warning_packet_loss": "1.0",
    "threshold_critical_packet_loss": "3.0",
    "network_enforcement_enabled": "false",
    "allow_production_enforcement": "false",
    "active_environment_target": "ISOLATED_TESTBED"
}


def get_setting(key: str, default=None, db_path=None):
    """Retrieves a single system setting value."""
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_settings WHERE key = ?;", (key,))
    row = cursor.fetchone()
    if row:
        return row["value"]
    return DEFAULT_SETTINGS.get(key, default)


def get_all_settings(db_path=None) -> dict:
    """Returns all system settings as a dictionary with metadata."""
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value, description, updated_at, updated_by FROM system_settings;")
    rows = cursor.fetchall()

    settings_dict = {}
    for r in rows:
        settings_dict[r["key"]] = {
            "value": r["value"],
            "description": r["description"],
            "updated_at": r["updated_at"],
            "updated_by": r["updated_by"]
        }

    # Ensure defaults are present if any are missing
    for k, v in DEFAULT_SETTINGS.items():
        if k not in settings_dict:
            settings_dict[k] = {
                "value": v,
                "description": "Default configuration parameter",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": "system"
            }

    return settings_dict


def update_setting(key: str, value: str, updated_by: str = "admin", db_path=None):
    """Updates or inserts a system setting value."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO system_settings (key, value, description, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by;
        """,
        (key, str(value), DEFAULT_SETTINGS.get(key, "Custom configuration setting"), now, updated_by)
    )
    conn.commit()
    return True


def get_active_thresholds(db_path=None) -> dict:
    """Returns parsed numeric multi-metric congestion thresholds."""
    return {
        "warn_util": float(get_setting("threshold_warning_utilization", "70.0", db_path)),
        "crit_util": float(get_setting("threshold_critical_utilization", "85.0", db_path)),
        "warn_lat": float(get_setting("threshold_warning_latency_ms", "50.0", db_path)),
        "crit_lat": float(get_setting("threshold_critical_latency_ms", "100.0", db_path)),
        "warn_loss": float(get_setting("threshold_warning_packet_loss", "1.0", db_path)),
        "crit_loss": float(get_setting("threshold_critical_packet_loss", "3.0", db_path)),
    }


def is_enforcement_enabled(db_path=None) -> bool:
    """Returns True if the network enforcement gate switch is active."""
    val = get_setting("network_enforcement_enabled", "false", db_path)
    return str(val).lower() in ("true", "1", "yes")


def is_production_enforcement_allowed(db_path=None) -> bool:
    """Safety check: Returns True only if explicit authorization for production enforcement exists."""
    val = get_setting("allow_production_enforcement", "false", db_path)
    return str(val).lower() in ("true", "1", "yes")
