-- CampusNet SQLite Schema
-- Designed for reliable, acid-compliant local network operations tracking

CREATE TABLE IF NOT EXISTS segments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    capacity_mbps REAL NOT NULL CHECK(capacity_mbps >= 0),
    demand_mbps REAL NOT NULL CHECK(demand_mbps >= 0),
    allocated_mbps REAL NOT NULL DEFAULT 0.0 CHECK(allocated_mbps >= 0),
    priority_weight REAL NOT NULL DEFAULT 1.0 CHECK(priority_weight > 0),
    min_guaranteed_mbps REAL DEFAULT 0.0 CHECK(min_guaranteed_mbps >= 0),
    max_limit_mbps REAL CHECK(max_limit_mbps IS NULL OR max_limit_mbps >= 0),
    latency_ms REAL CHECK(latency_ms IS NULL OR latency_ms >= 0),
    packet_loss_pct REAL CHECK(packet_loss_pct IS NULL OR (packet_loss_pct >= 0 AND packet_loss_pct <= 100)),
    jitter_ms REAL CHECK(jitter_ms IS NULL OR jitter_ms >= 0),
    throughput_mbps REAL CHECK(throughput_mbps IS NULL OR throughput_mbps >= 0),
    utilization_pct REAL NOT NULL DEFAULT 0.0 CHECK(utilization_pct >= 0),
    status TEXT NOT NULL DEFAULT 'NORMAL' CHECK(status IN ('NORMAL', 'WARNING', 'CRITICAL')),
    data_source TEXT NOT NULL DEFAULT 'SIMULATED' CHECK(data_source IN ('SIMULATED', 'IMPORTED', 'LAB')),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traffic_classes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    priority_level INTEGER NOT NULL CHECK(priority_level BETWEEN 1 AND 5),
    default_weight REAL NOT NULL CHECK(default_weight > 0),
    min_bandwidth_pct REAL DEFAULT 0.0 CHECK(min_bandwidth_pct >= 0 AND min_bandwidth_pct <= 100),
    dscp_mark TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id TEXT NOT NULL,
    throughput_mbps REAL CHECK(throughput_mbps IS NULL OR throughput_mbps >= 0),
    latency_ms REAL CHECK(latency_ms IS NULL OR latency_ms >= 0),
    packet_loss_pct REAL CHECK(packet_loss_pct IS NULL OR (packet_loss_pct >= 0 AND packet_loss_pct <= 100)),
    jitter_ms REAL CHECK(jitter_ms IS NULL OR jitter_ms >= 0),
    utilization_pct REAL NOT NULL CHECK(utilization_pct >= 0),
    data_source TEXT NOT NULL DEFAULT 'SIMULATED' CHECK(data_source IN ('SIMULATED', 'IMPORTED', 'LAB')),
    timestamp TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY(segment_id) REFERENCES segments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    parameters_json TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    scenario_name TEXT NOT NULL,
    total_capacity_mbps REAL NOT NULL CHECK(total_capacity_mbps >= 0),
    baseline_json TEXT NOT NULL,
    optimized_json TEXT NOT NULL,
    comparison_summary_json TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    segment_id TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    observed_value REAL NOT NULL,
    threshold_value REAL NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('WARNING', 'CRITICAL')),
    trigger_rule TEXT NOT NULL,
    explanation TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    is_persistent INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL,
    is_resolved INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(segment_id) REFERENCES segments(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_measurements_segment_time ON measurements(segment_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_segment_time ON alerts(segment_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_experiments_created ON experiments(created_at);

-- ============================================================================
-- AUTHORITY & ADMINISTRATION MODULE TABLES
-- ============================================================================

-- Role-Based Access Control Users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'netadmin', 'readonly')),
    full_name TEXT NOT NULL,
    email TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

-- Optimization Policy Lifecycle & Approval Workflow
CREATE TABLE IF NOT EXISTS optimization_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    proposed_by TEXT NOT NULL,
    proposed_at TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED', 'APPLIED', 'ROLLED_BACK')),
    rejection_reason TEXT,
    policy_data TEXT NOT NULL,
    target_environment TEXT NOT NULL DEFAULT 'ISOLATED_TESTBED' CHECK(target_environment IN ('ISOLATED_TESTBED', 'SIMULATION', 'PRODUCTION')),
    applied_by TEXT,
    applied_at TEXT,
    rollback_data TEXT,
    created_at TEXT NOT NULL
);

-- Immutable Operational & Administrative Audit Trail
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user_id INTEGER,
    username TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    ip_address TEXT,
    details TEXT NOT NULL
);

-- Dynamic Operational Thresholds & System Settings
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TEXT NOT NULL,
    updated_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_opt_policies_status ON optimization_policies(status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_time ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(username);

