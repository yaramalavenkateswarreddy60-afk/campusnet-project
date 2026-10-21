"""
CampusNet: Policy Lifecycle & Approval Workflow Module
Enforces formal approval stages (PENDING -> APPROVED -> APPLIED -> ROLLED_BACK),
rollback capability, and strict production safety constraints.
"""

import io
import csv
import json
from datetime import datetime, timezone
from database.db import get_db
from services.metrics import calculate_utilization, compute_segment_status
from services.congestion import CongestionDetector
from services.settings import get_active_thresholds, is_production_enforcement_allowed
from services.audit import record_audit, ACTION_POLICY_PROPOSED, ACTION_POLICY_APPROVED, ACTION_POLICY_REJECTED, ACTION_POLICY_APPLIED, ACTION_POLICY_ROLLBACK

STATUS_PENDING = "PENDING"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_APPLIED = "APPLIED"
STATUS_ROLLED_BACK = "ROLLED_BACK"

VALID_STATUSES = {STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_APPLIED, STATUS_ROLLED_BACK}

ENV_ISOLATED_TESTBED = "ISOLATED_TESTBED"
ENV_SIMULATION = "SIMULATION"
ENV_PRODUCTION = "PRODUCTION"

VALID_ENVIRONMENTS = {ENV_ISOLATED_TESTBED, ENV_SIMULATION, ENV_PRODUCTION}


class PolicyWorkflowError(Exception):
    """Raised when an invalid policy workflow transition or validation occurs."""
    pass


class SafetyEnforcementError(Exception):
    """Raised when a safety constraint (e.g., unauthorized production execution) is violated."""
    pass


def get_policy(policy_id: int, db_path=None):
    """Retrieves a single policy by ID with parsed JSON data."""
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM optimization_policies WHERE id = ?;", (policy_id,))
    row = cursor.fetchone()
    if not row:
        return None
    policy = dict(row)
    try:
        policy["policy_data"] = json.loads(policy["policy_data"])
    except Exception:
        pass
    if policy.get("rollback_data"):
        try:
            policy["rollback_data"] = json.loads(policy["rollback_data"])
        except Exception:
            pass
    return policy


def list_policies(status: str = None, limit: int = 50, db_path=None):
    """Lists policies with optional status filter."""
    conn = get_db(db_path)
    cursor = conn.cursor()

    if status:
        if status not in VALID_STATUSES:
            raise PolicyWorkflowError(f"Invalid status filter '{status}'.")
        cursor.execute(
            "SELECT * FROM optimization_policies WHERE status = ? ORDER BY id DESC LIMIT ?;",
            (status, limit)
        )
    else:
        cursor.execute(
            "SELECT * FROM optimization_policies ORDER BY id DESC LIMIT ?;",
            (limit,)
        )

    rows = cursor.fetchall()
    policies = []
    for r in rows:
        p = dict(r)
        try:
            p["policy_data"] = json.loads(p["policy_data"])
        except Exception:
            pass
        if p.get("rollback_data"):
            try:
                p["rollback_data"] = json.loads(p["rollback_data"])
            except Exception:
                pass
        policies.append(p)
    return policies


def propose_policy(name: str, description: str, policy_data: dict, proposed_by: str, target_environment: str = ENV_ISOLATED_TESTBED, db_path=None):
    """
    Submits a new optimization policy proposal for administrative review.
    Initial state is strictly PENDING.
    """
    if not name or not name.strip():
        raise PolicyWorkflowError("Policy name is required.")

    if not policy_data or "segments" not in policy_data:
        raise PolicyWorkflowError("Policy data must contain computed segment allocations.")

    if target_environment not in VALID_ENVIRONMENTS:
        raise PolicyWorkflowError(f"Invalid target environment '{target_environment}'.")

    now = datetime.now(timezone.utc).isoformat()
    policy_json = json.dumps(policy_data)

    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO optimization_policies (
            name, description, proposed_by, proposed_at, reviewed_by, reviewed_at,
            status, rejection_reason, policy_data, target_environment, applied_by,
            applied_at, rollback_data, created_at
        ) VALUES (?, ?, ?, ?, NULL, NULL, 'PENDING', NULL, ?, ?, NULL, NULL, NULL, ?);
        """,
        (name.strip(), description.strip() if description else "", proposed_by, now, policy_json, target_environment, now)
    )
    conn.commit()
    new_id = cursor.lastrowid

    record_audit(
        action=ACTION_POLICY_PROPOSED,
        details={
            "policy_id": new_id,
            "policy_name": name.strip(),
            "proposed_by": proposed_by,
            "target_environment": target_environment,
            "allocated_total_mbps": policy_data.get("total_allocated_mbps")
        },
        db_path=db_path
    )

    return get_policy(new_id, db_path=db_path)


def approve_policy(policy_id: int, reviewed_by: str, db_path=None):
    """
    Approves a PENDING policy. Only administrators are authorized to execute this.
    """
    policy = get_policy(policy_id, db_path=db_path)
    if not policy:
        raise PolicyWorkflowError(f"Policy ID {policy_id} not found.")

    if policy["status"] != STATUS_PENDING:
        raise PolicyWorkflowError(f"Cannot approve policy with status '{policy['status']}'. Policy must be in PENDING state.")

    now = datetime.now(timezone.utc).isoformat()
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE optimization_policies
        SET status = 'APPROVED', reviewed_by = ?, reviewed_at = ?, rejection_reason = NULL
        WHERE id = ?;
        """,
        (reviewed_by, now, policy_id)
    )
    conn.commit()

    record_audit(
        action=ACTION_POLICY_APPROVED,
        details={
            "policy_id": policy_id,
            "policy_name": policy["name"],
            "reviewed_by": reviewed_by,
            "target_environment": policy["target_environment"]
        },
        db_path=db_path
    )

    return get_policy(policy_id, db_path=db_path)


def reject_policy(policy_id: int, reviewed_by: str, reason: str, db_path=None):
    """
    Rejects a PENDING policy with an explicit justification.
    """
    if not reason or not reason.strip():
        raise PolicyWorkflowError("A valid rejection reason is required.")

    policy = get_policy(policy_id, db_path=db_path)
    if not policy:
        raise PolicyWorkflowError(f"Policy ID {policy_id} not found.")

    if policy["status"] != STATUS_PENDING:
        raise PolicyWorkflowError(f"Cannot reject policy with status '{policy['status']}'. Policy must be in PENDING state.")

    now = datetime.now(timezone.utc).isoformat()
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE optimization_policies
        SET status = 'REJECTED', reviewed_by = ?, reviewed_at = ?, rejection_reason = ?
        WHERE id = ?;
        """,
        (reviewed_by, now, reason.strip(), policy_id)
    )
    conn.commit()

    record_audit(
        action=ACTION_POLICY_REJECTED,
        details={
            "policy_id": policy_id,
            "policy_name": policy["name"],
            "reviewed_by": reviewed_by,
            "reason": reason.strip()
        },
        db_path=db_path
    )

    return get_policy(policy_id, db_path=db_path)


def apply_policy(policy_id: int, applied_by: str, db_path=None):
    """
    Applies an APPROVED policy.
    Enforces that:
    1. Status is strictly APPROVED.
    2. Target is ISOLATED_TESTBED or SIMULATION.
       If target is PRODUCTION, raises SafetyEnforcementError unless explicitly authorized.
    3. Captures rollback snapshot before updating database state.
    """
    policy = get_policy(policy_id, db_path=db_path)
    if not policy:
        raise PolicyWorkflowError(f"Policy ID {policy_id} not found.")

    if policy["status"] != STATUS_APPROVED:
        raise PolicyWorkflowError(f"Cannot apply policy with status '{policy['status']}'. Policy must be in APPROVED state.")

    # Strict Production Safety Constraint (Requirement 12)
    if policy["target_environment"] == ENV_PRODUCTION:
        if not is_production_enforcement_allowed(db_path=db_path):
            raise SafetyEnforcementError(
                "Safety Violation: Direct execution of optimization policies on the production campus network "
                "is strictly blocked. Network enforcement is restricted to the isolated test network."
            )

    conn = get_db(db_path)
    cursor = conn.cursor()

    # 1. Capture snapshot of current segment states for deterministic rollback
    cursor.execute("SELECT * FROM segments;")
    current_segments = [dict(r) for r in cursor.fetchall()]
    rollback_snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "applied_policy_id": policy_id,
        "segments": current_segments
    }
    rollback_json = json.dumps(rollback_snapshot)

    # 2. Extract proposed allocations from policy data
    policy_data = policy["policy_data"]
    segments_to_apply = policy_data.get("segments", [])

    thresholds = get_active_thresholds(db_path=db_path)
    detector = CongestionDetector(
        warn_util=thresholds["warn_util"],
        crit_util=thresholds["crit_util"],
        warn_lat=thresholds["warn_lat"],
        crit_lat=thresholds["crit_lat"],
        warn_loss=thresholds["warn_loss"],
        crit_loss=thresholds["crit_loss"]
    )

    now = datetime.now(timezone.utc).isoformat()

    # Clear old unresolved alerts before applying fresh evaluation
    cursor.execute("DELETE FROM alerts;")

    for seg_res in segments_to_apply:
        sid = seg_res["id"]
        new_alloc = float(seg_res["allocated_mbps"])
        new_demand = float(seg_res.get("demand_mbps", new_alloc))
        new_weight = float(seg_res.get("priority_weight", 1.0))

        cursor.execute("SELECT capacity_mbps FROM segments WHERE id = ?;", (sid,))
        srow = cursor.fetchone()
        seg_cap = srow["capacity_mbps"] if srow else 100.0

        new_util = calculate_utilization(new_alloc, seg_cap)

        # Simulated dynamic latency and loss improvements post-QoS
        post_loss = round(max(0.0, (1.0 - (new_alloc / new_demand)) * 3.0 / new_weight), 2) if new_demand > 0 else 0.0
        post_lat = round(15.0 + (post_loss * 10.0), 1)
        new_status = compute_segment_status(new_util, latency_ms=post_lat, packet_loss_pct=post_loss)

        cursor.execute(
            """
            UPDATE segments
            SET allocated_mbps = ?, demand_mbps = ?, priority_weight = ?,
                utilization_pct = ?, latency_ms = ?, packet_loss_pct = ?,
                status = ?, updated_at = ?
            WHERE id = ?;
            """,
            (new_alloc, new_demand, new_weight, new_util, post_lat, post_loss, new_status, now, sid)
        )

        cursor.execute(
            """
            INSERT INTO measurements (
                segment_id, throughput_mbps, latency_ms, packet_loss_pct, jitter_ms,
                utilization_pct, data_source, timestamp, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (sid, round(new_alloc * 0.98, 2), post_lat, post_loss, 3.0, new_util, "SIMULATED", now, f"Applied Policy #{policy_id}")
        )

        eval_seg = {
            "id": sid,
            "name": seg_res.get("name", sid),
            "utilization_pct": new_util,
            "latency_ms": post_lat,
            "packet_loss_pct": post_loss,
            "data_source": "SIMULATED"
        }
        for alert in detector.evaluate_segment(eval_seg):
            cursor.execute(
                """
                INSERT INTO alerts (
                    segment_id, metric_name, observed_value, threshold_value,
                    severity, trigger_rule, explanation, recommended_action,
                    is_persistent, timestamp, is_resolved
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0);
                """,
                (
                    alert["segment_id"], alert["metric_name"], alert["observed_value"],
                    alert["threshold_value"], alert["severity"], alert["trigger_rule"],
                    alert["explanation"], alert["recommended_action"], alert["is_persistent"],
                    alert["timestamp"]
                )
            )

    # 3. Mark policy as APPLIED and store rollback data
    cursor.execute(
        """
        UPDATE optimization_policies
        SET status = 'APPLIED', applied_by = ?, applied_at = ?, rollback_data = ?
        WHERE id = ?;
        """,
        (applied_by, now, rollback_json, policy_id)
    )
    conn.commit()

    record_audit(
        action=ACTION_POLICY_APPLIED,
        details={
            "policy_id": policy_id,
            "policy_name": policy["name"],
            "applied_by": applied_by,
            "target_environment": policy["target_environment"],
            "segments_updated": len(segments_to_apply)
        },
        db_path=db_path
    )

    return get_policy(policy_id, db_path=db_path)


def rollback_policy(policy_id: int, rolled_back_by: str, db_path=None):
    """
    Rolls back an APPLIED policy to its pre-application snapshot state.
    """
    policy = get_policy(policy_id, db_path=db_path)
    if not policy:
        raise PolicyWorkflowError(f"Policy ID {policy_id} not found.")

    if policy["status"] != STATUS_APPLIED:
        raise PolicyWorkflowError(f"Cannot rollback policy with status '{policy['status']}'. Policy must be in APPLIED state.")

    rollback_snapshot = policy.get("rollback_data")
    if not rollback_snapshot or "segments" not in rollback_snapshot:
        raise PolicyWorkflowError("Rollback snapshot data is missing or corrupted.")

    conn = get_db(db_path)
    cursor = conn.cursor()

    now = datetime.now(timezone.utc).isoformat()
    restored_segments = rollback_snapshot["segments"]

    # Clear old alerts before restoring previous state
    cursor.execute("DELETE FROM alerts;")

    for seg in restored_segments:
        cursor.execute(
            """
            UPDATE segments
            SET allocated_mbps = ?, demand_mbps = ?, priority_weight = ?,
                capacity_mbps = ?, min_guaranteed_mbps = ?, max_limit_mbps = ?,
                latency_ms = ?, packet_loss_pct = ?, jitter_ms = ?, throughput_mbps = ?,
                utilization_pct = ?, status = ?, updated_at = ?
            WHERE id = ?;
            """,
            (
                seg["allocated_mbps"], seg["demand_mbps"], seg["priority_weight"],
                seg["capacity_mbps"], seg.get("min_guaranteed_mbps", 0.0), seg.get("max_limit_mbps"),
                seg.get("latency_ms", 20.0), seg.get("packet_loss_pct", 0.0), seg.get("jitter_ms", 2.0),
                seg.get("throughput_mbps", seg["allocated_mbps"]), seg["utilization_pct"],
                seg["status"], now, seg["id"]
            )
        )

        cursor.execute(
            """
            INSERT INTO measurements (
                segment_id, throughput_mbps, latency_ms, packet_loss_pct, jitter_ms,
                utilization_pct, data_source, timestamp, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                seg["id"], seg.get("throughput_mbps", seg["allocated_mbps"]), seg.get("latency_ms", 20.0),
                seg.get("packet_loss_pct", 0.0), seg.get("jitter_ms", 2.0), seg["utilization_pct"],
                "SIMULATED", now, f"State restored via Rollback of Policy #{policy_id}"
            )
        )

    # Mark policy as ROLLED_BACK
    cursor.execute(
        """
        UPDATE optimization_policies
        SET status = 'ROLLED_BACK'
        WHERE id = ?;
        """,
        (policy_id,)
    )
    conn.commit()

    record_audit(
        action=ACTION_POLICY_ROLLBACK,
        details={
            "policy_id": policy_id,
            "policy_name": policy["name"],
            "rolled_back_by": rolled_back_by,
            "segments_restored": len(restored_segments)
        },
        db_path=db_path
    )

    return get_policy(policy_id, db_path=db_path)


def export_policies_csv(policies: list) -> str:
    """Exports optimization policies list to CSV format string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Policy ID", "Name", "Status", "Target Environment",
        "Proposed By", "Proposed At", "Reviewed By", "Reviewed At",
        "Applied By", "Applied At", "Rejection Reason", "Description"
    ])

    for p in policies:
        writer.writerow([
            p.get("id"),
            p.get("name"),
            p.get("status"),
            p.get("target_environment"),
            p.get("proposed_by"),
            p.get("proposed_at"),
            p.get("reviewed_by"),
            p.get("reviewed_at"),
            p.get("applied_by"),
            p.get("applied_at"),
            p.get("rejection_reason"),
            p.get("description")
        ])

    return output.getvalue()
