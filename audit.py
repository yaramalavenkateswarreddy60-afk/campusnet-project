"""
CampusNet: Security & Operations Audit Trail Module
Maintains an immutable record of logins, administrative actions, policy transitions, and system events.
"""

import io
import csv
import json
from datetime import datetime, timezone
from flask import request, has_request_context
from database.db import get_db

ACTION_USER_LOGIN = "USER_LOGIN"
ACTION_USER_LOGOUT = "USER_LOGOUT"
ACTION_LOGIN_FAILED = "LOGIN_FAILED"
ACTION_UNAUTHORIZED_ACCESS = "UNAUTHORIZED_ACCESS_ATTEMPT"

ACTION_USER_CREATED = "USER_CREATED"
ACTION_USER_UPDATED = "USER_UPDATED"
ACTION_USER_DELETED = "USER_DELETED"
ACTION_PASSWORD_RESET = "PASSWORD_RESET"

ACTION_CONFIG_UPDATED = "CONFIG_UPDATED"
ACTION_THRESHOLD_MODIFIED = "THRESHOLD_MODIFIED"

ACTION_SEGMENT_CREATED = "SEGMENT_CREATED"
ACTION_SEGMENT_MODIFIED = "SEGMENT_MODIFIED"
ACTION_SEGMENT_DELETED = "SEGMENT_DELETED"

ACTION_POLICY_PROPOSED = "POLICY_PROPOSED"
ACTION_POLICY_APPROVED = "POLICY_APPROVED"
ACTION_POLICY_REJECTED = "POLICY_REJECTED"
ACTION_POLICY_APPLIED = "POLICY_APPLIED"
ACTION_POLICY_ROLLBACK = "POLICY_ROLLBACK"

ACTION_EXPERIMENT_RUN = "EXPERIMENT_RUN"
ACTION_DEMO_RESET = "DEMO_RESET"
ACTION_CSV_IMPORTED = "CSV_IMPORTED"
ACTION_REPORT_DOWNLOADED = "REPORT_DOWNLOADED"


def record_audit(action: str, details=None, user=None, ip_address=None, db_path=None):
    """
    Persists an audit event to the audit_logs table.
    Safely captures context when run within a Flask request.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Determine actor
    if user is None and has_request_context():
        from services.auth import get_current_user
        user = get_current_user()

    if user:
        user_id = user.get("id")
        username = user.get("username", "unknown")
        role = user.get("role", "system")
    else:
        user_id = None
        username = "anonymous"
        role = "none"

    # Determine IP address
    if ip_address is None and has_request_context():
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        else:
            ip_address = request.remote_addr or "127.0.0.1"
    elif ip_address is None:
        ip_address = "127.0.0.1"

    # Format details
    if isinstance(details, (dict, list)):
        details_str = json.dumps(details)
    elif details is None:
        details_str = f"Action '{action}' executed."
    else:
        details_str = str(details)

    try:
        conn = get_db(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_logs (timestamp, user_id, username, role, action, ip_address, details)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (now, user_id, username, role, action, ip_address, details_str)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        # Audit logging failure should not crash the primary operational transaction,
        # but print to stderr for operational visibility.
        print(f"[AUDIT_ERROR] Failed to record audit log: {str(e)}")
        return None


def query_audit_logs(limit: int = 100, offset: int = 0, action: str = None, username: str = None, search: str = None, db_path=None):
    """Queries audit trail with optional filtering."""
    conn = get_db(db_path)
    cursor = conn.cursor()

    conditions = []
    params = []

    if action:
        conditions.append("action = ?")
        params.append(action)

    if username:
        conditions.append("username = ?")
        params.append(username.strip().lower())

    if search:
        conditions.append("(details LIKE ? OR action LIKE ? OR username LIKE ?)")
        term = f"%{search.strip()}%"
        params.extend([term, term, term])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Total count
    cursor.execute(f"SELECT COUNT(*) AS total FROM audit_logs {where_clause};", params)
    total_count = cursor.fetchone()["total"]

    # Paginated results
    query = f"""
        SELECT id, timestamp, user_id, username, role, action, ip_address, details
        FROM audit_logs
        {where_clause}
        ORDER BY id DESC
        LIMIT ? OFFSET ?;
    """
    params.extend([limit, offset])
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]

    return {
        "total": total_count,
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "logs": rows
    }


def export_audit_logs_csv(logs: list) -> str:
    """Exports audit logs to CSV format string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp (UTC)", "Username", "Role", "Action", "IP Address", "Details"])

    for log in logs:
        writer.writerow([
            log.get("id"),
            log.get("timestamp"),
            log.get("username"),
            log.get("role"),
            log.get("action"),
            log.get("ip_address"),
            log.get("details")
        ])

    return output.getvalue()
