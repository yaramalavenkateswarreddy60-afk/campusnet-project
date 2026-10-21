"""
CampusNet: Database Manager Module
Manages SQLite lifecycle, connections, schema creation, and deterministic demo seeds.
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from flask import g, current_app
from werkzeug.security import generate_password_hash

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

def get_db(db_path=None):
    """
    Returns a SQLite database connection with row factory configured.
    Uses Flask 'g' object if inside an application context, otherwise creates a standalone connection.
    """
    if db_path is None:
        try:
            if current_app:
                db_path = current_app.config.get("DATABASE_PATH")
        except RuntimeError:
            # Outside application context
            db_path = None

    if db_path is None:
        from config import Config
        db_path = Config.DATABASE_PATH

    # If within request context, bind to g
    try:
        if "db" not in g:
            g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON;")
        return g.db
    except (RuntimeError, AttributeError):
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn


def close_db(e=None):
    """Closes the current database connection if open."""
    try:
        db = g.pop("db", None)
        if db is not None:
            db.close()
    except (RuntimeError, AttributeError):
        pass


def init_db(db_path=None, seed_if_empty=True):
    """
    Initializes the SQLite database with tables from schema.sql.
    Optionally seeds baseline campus segments and traffic classes.
    """
    conn = get_db(db_path)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()

    if seed_if_empty:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM segments;")
        row = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) AS user_cnt FROM users;")
        user_row = cursor.fetchone()
        if (row and row["cnt"] == 0) or (user_row and user_row["user_cnt"] == 0):
            seed_baseline_data(conn)


def seed_baseline_data(conn):
    """
    Seeds reproducible illustrative campus network data.
    Clearly labeled with data_source = 'SIMULATED'.
    """
    now = datetime.now(timezone.utc).isoformat()

    # 1. Standard Campus Segments
    # Total link capacity modeled: 1000 Mbps sum of segment limits; shared uplink capacity modeled at 800 Mbps
    # Computer Lab: high demand
    # Smart Classrooms: demand exceeds capacity -> critical congestion candidate
    # Library: moderate demand
    # Administration: low demand, critical priority
    # Guest Wi-Fi: demand exceeds capacity -> low priority congestion
    segments_data = [
        (
            "seg_comp_lab",
            "Computer Lab",
            "Student computing terminals, CAD workstations, and cloud lab instances",
            300.0,  # capacity
            280.0,  # demand (93.3% load)
            240.0,  # initial modeled baseline allocation
            3.0,    # priority weight (Medium-High)
            100.0,  # min guaranteed
            300.0,  # max limit
            38.5,   # latency ms
            1.2,    # packet loss pct
            5.2,    # jitter ms
            238.0,  # simulated throughput
            80.0,   # utilization pct (initial warning)
            "WARNING",
            "SIMULATED",
            now
        ),
        (
            "seg_smart_class",
            "Smart Classrooms",
            "High-definition video lectures, digital whiteboards, and interactive quiz sessions",
            250.0,  # capacity
            260.0,  # demand (exceeds capacity: 104%)
            195.0,  # baseline allocation
            4.0,    # priority weight (High)
            120.0,  # min guaranteed
            250.0,  # max limit
            62.0,   # latency ms
            3.4,    # packet loss pct
            11.5,   # jitter ms
            190.5,  # throughput
            78.0,   # utilization pct
            "WARNING",
            "SIMULATED",
            now
        ),
        (
            "seg_library",
            "Library",
            "Digital repository, e-journal access, research papers, and study desk terminals",
            150.0,  # capacity
            110.0,  # demand (73.3% load)
            105.0,  # baseline allocation
            2.0,    # priority weight (Normal)
            30.0,   # min guaranteed
            150.0,  # max limit
            22.4,   # latency ms
            0.2,    # packet loss pct
            2.1,    # jitter ms
            104.2,  # throughput
            70.0,   # utilization pct
            "NORMAL",
            "SIMULATED",
            now
        ),
        (
            "seg_admin",
            "Administration",
            "Student registration, ERP servers, exam processing, payroll, and dean's office",
            100.0,  # capacity
            45.0,   # demand (45% load)
            45.0,   # baseline allocation (100% satisfied)
            5.0,    # priority weight (Mission Critical)
            40.0,   # min guaranteed
            100.0,  # max limit
            14.2,   # latency ms
            0.0,    # packet loss pct
            1.0,    # jitter ms
            44.8,   # throughput
            45.0,   # utilization pct
            "NORMAL",
            "SIMULATED",
            now
        ),
        (
            "seg_guest_wifi",
            "Guest Wi-Fi",
            "Open campus public access, visitor smartphones, and social media traffic",
            200.0,  # capacity
            220.0,  # demand (exceeds capacity: 110%)
            175.0,  # baseline unoptimized allocation
            1.0,    # priority weight (Best Effort / Low)
            15.0,   # min guaranteed
            200.0,  # max limit
            88.6,   # latency ms
            4.8,    # packet loss pct
            18.0,   # jitter ms
            171.0,  # throughput
            87.5,   # utilization pct (critical!)
            "CRITICAL",
            "SIMULATED",
            now
        )
    ]

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS cnt FROM segments;")
    if cursor.fetchone()["cnt"] == 0:
        conn.executemany(
            """
            INSERT INTO segments (
                id, name, description, capacity_mbps, demand_mbps, allocated_mbps,
                priority_weight, min_guaranteed_mbps, max_limit_mbps, latency_ms,
                packet_loss_pct, jitter_ms, throughput_mbps, utilization_pct,
                status, data_source, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            segments_data
        )

    # 2. Standard Traffic Classes
    cursor.execute("SELECT COUNT(*) AS cnt FROM traffic_classes;")
    if cursor.fetchone()["cnt"] == 0:
        traffic_classes = [
            ("tc_interactive", "Interactive Academic & Video-Class", 4, 4.0, 25.0, "DSCP EF (46) / AF41", "Real-time bidirectional video, Zoom/Teams lectures, online exams"),
            ("tc_admin", "Essential Administrative Traffic", 5, 5.0, 15.0, "DSCP CS6 (48)", "Mission-critical campus ERP, registrar portal, financial databases"),
            ("tc_learning", "Learning Resources & Laboratory Traffic", 3, 3.0, 20.0, "DSCP AF31 (26)", "Moodle LMS, digital library, Git repos, research datasets"),
            ("tc_browsing", "General Browsing", 2, 2.0, 15.0, "DSCP AF11 (10)", "HTTP/HTTPS general web browsing, search engines, intranet portals"),
            ("tc_guest", "Guest & Bulk-Download Traffic", 1, 1.0, 5.0, "DSCP BE (0)", "Public Wi-Fi, P2P, media streaming, non-academic bulk transfers")
        ]
        conn.executemany(
            """
            INSERT INTO traffic_classes (
                id, name, priority_level, default_weight, min_bandwidth_pct, dscp_mark, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            traffic_classes
        )

    # 3. Seed illustrative baseline measurements for charting trends
    cursor.execute("SELECT COUNT(*) AS cnt FROM measurements;")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute("SELECT id, allocated_mbps, latency_ms, packet_loss_pct, jitter_ms, utilization_pct FROM segments;")
        segments = cursor.fetchall()
        for seg in segments:
            conn.execute(
                """
                INSERT INTO measurements (
                    segment_id, throughput_mbps, latency_ms, packet_loss_pct, jitter_ms,
                    utilization_pct, data_source, timestamp, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    seg["id"],
                    round(seg["allocated_mbps"] * 0.98, 2),
                    seg["latency_ms"],
                    seg["packet_loss_pct"],
                    seg["jitter_ms"],
                    seg["utilization_pct"],
                    "SIMULATED",
                    now,
                    "Deterministic baseline measurement for demo initialization"
                )
            )

    # 4. Seed initial alerts for baseline state
    cursor.execute("SELECT COUNT(*) AS cnt FROM alerts;")
    if cursor.fetchone()["cnt"] == 0:
        initial_alerts = [
            (
                "seg_guest_wifi",
                "utilization",
                87.5,
                85.0,
            "CRITICAL",
            "Utilization >= 85%",
            "Guest Wi-Fi demand (220 Mbps) exceeds local link capacity with heavy video/bulk traffic.",
            "Throttle Guest Wi-Fi priority weight to 1.0 and enforce a 100 Mbps ceiling to protect academic classes.",
            1,
            now,
            0
        ),
        (
            "seg_comp_lab",
            "utilization",
            80.0,
            70.0,
            "WARNING",
            "Utilization >= 70%",
            "Computer Lab terminals consuming 240 Mbps of modeled capacity during afternoon lab sessions.",
            "Schedule non-essential software package updates to off-peak hours.",
            0,
            now,
            0
        ),
        (
            "seg_smart_class",
            "latency",
            62.0,
            50.0,
            "WARNING",
            "Latency >= 50ms",
            "Classroom video stream buffers approaching interactive latency threshold.",
            "Prioritize DSCP EF packets on gateway queue and guarantee at least 200 Mbps allocation.",
            0,
            now,
            0
        )
    ]

        conn.executemany(
            """
            INSERT INTO alerts (
                segment_id, metric_name, observed_value, threshold_value, severity,
                trigger_rule, explanation, recommended_action, is_persistent, timestamp, is_resolved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            initial_alerts
        )

    # 5. Seed Default Role-Based Access Control Users
    cursor.execute("SELECT COUNT(*) AS cnt FROM users;")
    user_cnt = cursor.fetchone()["cnt"]
    if user_cnt == 0:
        default_users = [
            (
                "admin",
                generate_password_hash("Admin@CampusNet2026"),
                "admin",
                "Campus IT Director",
                "admin@campus.edu",
                1,
                now,
                now
            ),
            (
                "netadmin",
                generate_password_hash("NetAdmin@CampusNet2026"),
                "netadmin",
                "Senior NOC Network Engineer",
                "netadmin@campus.edu",
                1,
                now,
                None
            ),
            (
                "authority",
                generate_password_hash("Authority@CampusNet2026"),
                "readonly",
                "Institutional Compliance Officer",
                "compliance@campus.edu",
                1,
                now,
                None
            )
        ]
        conn.executemany(
            """
            INSERT INTO users (
                username, password_hash, role, full_name, email, is_active, created_at, last_login_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            default_users
        )

    # 6. Seed Dynamic Operational Settings & Thresholds
    cursor.execute("SELECT COUNT(*) AS cnt FROM system_settings;")
    settings_cnt = cursor.fetchone()["cnt"]
    if settings_cnt == 0:
        default_settings = [
            ("threshold_warning_utilization", "70.0", "Warning utilization threshold percentage", now, "admin"),
            ("threshold_critical_utilization", "85.0", "Critical utilization threshold percentage", now, "admin"),
            ("threshold_warning_latency_ms", "50.0", "Warning round-trip latency in milliseconds", now, "admin"),
            ("threshold_critical_latency_ms", "100.0", "Critical round-trip latency in milliseconds", now, "admin"),
            ("threshold_warning_packet_loss", "1.0", "Warning packet drop percentage", now, "admin"),
            ("threshold_critical_packet_loss", "3.0", "Critical packet drop percentage", now, "admin"),
            ("network_enforcement_enabled", "false", "Network enforcement gate switch (disabled by default for safety)", now, "admin"),
            ("allow_production_enforcement", "false", "Safety Lock: Direct enforcement on production campus gateway", now, "admin"),
            ("active_environment_target", "ISOLATED_TESTBED", "Target enforcement environment (ISOLATED_TESTBED / SIMULATION)", now, "admin")
        ]
        conn.executemany(
            """
            INSERT INTO system_settings (key, value, description, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?);
            """,
            default_settings
        )

    # 7. Seed Initial Baseline Optimization Policy in Lifecycle Workflow
    cursor.execute("SELECT COUNT(*) AS cnt FROM optimization_policies;")
    policy_cnt = cursor.fetchone()["cnt"]
    if policy_cnt == 0:
        sample_policy_data = json.dumps({
            "total_capacity_mbps": 800.0,
            "segments": [
                {"id": "seg_comp_lab", "name": "Computer Lab", "allocated_mbps": 240.0, "demand_mbps": 280.0, "priority_weight": 3.0},
                {"id": "seg_smart_class", "name": "Smart Classrooms", "allocated_mbps": 195.0, "demand_mbps": 260.0, "priority_weight": 4.0},
                {"id": "seg_library", "name": "Library", "allocated_mbps": 105.0, "demand_mbps": 110.0, "priority_weight": 2.0},
                {"id": "seg_admin", "name": "Administration", "allocated_mbps": 45.0, "demand_mbps": 45.0, "priority_weight": 5.0},
                {"id": "seg_guest_wifi", "name": "Guest Wi-Fi", "allocated_mbps": 175.0, "demand_mbps": 220.0, "priority_weight": 1.0}
            ],
            "algorithm": "WFQ-PF",
            "policy_summary": "Initial baseline campus bandwidth distribution plan"
        })
        conn.execute(
            """
            INSERT INTO optimization_policies (
                name, description, proposed_by, proposed_at, reviewed_by, reviewed_at,
                status, rejection_reason, policy_data, target_environment, applied_by,
                applied_at, rollback_data, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "Baseline Balanced Campus QoS",
                "Calibrated baseline bandwidth allocation schedule for peak academic operational hours",
                "netadmin",
                now,
                "admin",
                now,
                "APPLIED",
                None,
                sample_policy_data,
                "ISOLATED_TESTBED",
                "netadmin",
                now,
                None,
                now
            )
        )

    # 8. Seed Initial Operational Audit Log
    cursor.execute("SELECT COUNT(*) AS cnt FROM audit_logs;")
    audit_cnt = cursor.fetchone()["cnt"]
    if audit_cnt == 0:
        conn.execute(
            """
            INSERT INTO audit_logs (
                timestamp, user_id, username, role, action, ip_address, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                now,
                1,
                "admin",
                "admin",
                "SYSTEM_INIT",
                "127.0.0.1",
                "System initialized with calibrated baseline campus topology and default RBAC accounts."
            )
        )

    conn.commit()


def reset_db(db_path=None):
    """
    Clears runtime tables and restores the clean calibrated baseline dataset and users.
    """
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alerts;")
    cursor.execute("DELETE FROM measurements;")
    cursor.execute("DELETE FROM experiments;")
    cursor.execute("DELETE FROM policies;")
    cursor.execute("DELETE FROM optimization_policies;")
    cursor.execute("DELETE FROM audit_logs;")
    cursor.execute("DELETE FROM system_settings;")
    cursor.execute("DELETE FROM users;")
    cursor.execute("DELETE FROM segments;")
    cursor.execute("DELETE FROM traffic_classes;")
    conn.commit()
    seed_baseline_data(conn)

