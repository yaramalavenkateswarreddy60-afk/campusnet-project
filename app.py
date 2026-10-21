"""
CampusNet: Adaptive Campus Network Performance Optimization
Main Flask Application and REST API Controller with Authority & Administration Module.
"""

import os
import io
import csv
import json
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template, send_file, g, session

from config import Config, DevelopmentConfig, TestingConfig
from database.db import get_db, init_db, reset_db, close_db
from services.metrics import (
    calculate_utilization,
    calculate_unmet_demand,
    calculate_satisfaction_rate,
    compute_segment_status,
    aggregate_network_summary
)
from services.congestion import CongestionDetector
from services.optimizer import BandwidthOptimizer, OptimizationError
from services.experiments import (
    run_experiment,
    get_experiment_by_id,
    list_experiments,
    SCENARIOS
)
from adapters.csv_import import validate_and_import_csv, CSVValidationError
from adapters.lab_adapter import LabAdapter

from services.auth import (
    ROLE_ADMIN, ROLE_NETADMIN, ROLE_READONLY, VALID_ROLES,
    hash_password, verify_password, get_user_by_id, get_user_by_username,
    list_users, create_user, update_user, reset_password, delete_user,
    login_user, logout_user, get_current_user, login_required, roles_required, admin_required,
    record_login
)
from services.audit import (
    record_audit, query_audit_logs, export_audit_logs_csv,
    ACTION_USER_LOGIN, ACTION_USER_LOGOUT, ACTION_LOGIN_FAILED,
    ACTION_USER_CREATED, ACTION_USER_UPDATED, ACTION_USER_DELETED, ACTION_PASSWORD_RESET,
    ACTION_CONFIG_UPDATED, ACTION_THRESHOLD_MODIFIED,
    ACTION_SEGMENT_CREATED, ACTION_SEGMENT_MODIFIED, ACTION_SEGMENT_DELETED,
    ACTION_POLICY_PROPOSED, ACTION_POLICY_APPROVED, ACTION_POLICY_REJECTED,
    ACTION_POLICY_APPLIED, ACTION_POLICY_ROLLBACK,
    ACTION_EXPERIMENT_RUN, ACTION_DEMO_RESET, ACTION_CSV_IMPORTED, ACTION_REPORT_DOWNLOADED,
    ACTION_UNAUTHORIZED_ACCESS
)
from services.settings import (
    get_setting, get_all_settings, update_setting, get_active_thresholds,
    is_enforcement_enabled, is_production_enforcement_allowed
)
from services.policies import (
    propose_policy, approve_policy, reject_policy, apply_policy, rollback_policy,
    get_policy, list_policies, export_policies_csv, PolicyWorkflowError, SafetyEnforcementError,
    STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_APPLIED, STATUS_ROLLED_BACK
)
from services.reports import (
    generate_telemetry_csv, generate_audit_csv, generate_policies_csv, generate_executive_html_report
)


def create_app(config_class=DevelopmentConfig):
    """Application factory for CampusNet."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_class)

    # Register teardown
    app.teardown_appcontext(close_db)

    # Initialize database tables & baseline seed on start
    with app.app_context():
        init_db(app.config["DATABASE_PATH"])

    @app.before_request
    def load_authenticated_user():
        g.user = get_current_user()

    # -------------------------------------------------------------
    # Frontend Page Routes
    # -------------------------------------------------------------
    @app.route("/")
    def index():
        """Serves the main CampusNet NOC dashboard."""
        return render_template("index.html")

    # -------------------------------------------------------------
    # Core Health & System APIs
    # -------------------------------------------------------------
    @app.route("/api/health", methods=["GET"])
    def api_health():
        """Returns application status, DB connection, and runtime environment."""
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS seg_cnt FROM segments;")
            seg_cnt = cursor.fetchone()["seg_cnt"]
            db_status = "HEALTHY"
        except Exception as e:
            db_status = f"ERROR: {str(e)}"
            seg_cnt = 0

        lab_env = LabAdapter.inspect_environment()
        db_path = app.config["DATABASE_PATH"]

        return jsonify({
            "status": "UP",
            "service": "CampusNet Network Operations & Optimization",
            "database_status": db_status,
            "segments_configured": seg_cnt,
            "environment_mode": lab_env["status_label"],
            "lab_details": lab_env,
            "enforcement_gate": {
                "enabled": is_enforcement_enabled(db_path),
                "production_allowed": is_production_enforcement_allowed(db_path),
                "target_environment": get_setting("active_environment_target", "ISOLATED_TESTBED", db_path)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200

    # -------------------------------------------------------------
    # Authentication & Session APIs
    # -------------------------------------------------------------
    @app.route("/api/auth/login", methods=["POST"])
    def api_auth_login():
        """Authenticates user credentials and establishes a protected session."""
        data = request.get_json(silent=True) or {}
        username = (data.get("username") or "").strip().lower()
        password = data.get("password") or ""

        db_path = app.config["DATABASE_PATH"]

        if not username or not password:
            return jsonify({"error": "Username and password are required.", "status": 400}), 400

        user = get_user_by_username(username, include_hash=True, db_path=db_path)
        if not user or not verify_password(password, user["password_hash"]):
            record_audit(
                action=ACTION_LOGIN_FAILED,
                details=f"Failed login attempt for username '{username}'.",
                db_path=db_path
            )
            return jsonify({"error": "Invalid username or password.", "status": 401}), 401

        if not user["is_active"]:
            record_audit(
                action=ACTION_LOGIN_FAILED,
                details=f"Login attempt for deactivated account '{username}'.",
                db_path=db_path
            )
            return jsonify({"error": "Account is deactivated. Contact an administrator.", "status": 403}), 403

        # Success: establish session
        clean_user = {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "full_name": user["full_name"],
            "email": user["email"]
        }
        login_user(clean_user)
        record_login(user["id"], db_path=db_path)

        record_audit(
            action=ACTION_USER_LOGIN,
            details=f"User '{user['username']}' ({user['role']}) logged in successfully.",
            user=clean_user,
            db_path=db_path
        )

        return jsonify({
            "success": True,
            "message": f"Welcome, {user['full_name']}!",
            "user": clean_user
        }), 200

    @app.route("/api/auth/logout", methods=["POST"])
    def api_auth_logout():
        """Terminates authenticated session."""
        db_path = app.config["DATABASE_PATH"]
        user = get_current_user()
        if user:
            record_audit(
                action=ACTION_USER_LOGOUT,
                details=f"User '{user['username']}' logged out.",
                user=user,
                db_path=db_path
            )
        logout_user()
        return jsonify({"success": True, "message": "Successfully logged out."}), 200

    @app.route("/api/auth/me", methods=["GET"])
    def api_auth_me():
        """Returns currently authenticated user profile and permissions."""
        user = get_current_user()
        if not user:
            return jsonify({"authenticated": False, "user": None}), 200

        return jsonify({
            "authenticated": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "full_name": user.get("full_name", user["username"]),
                "email": user.get("email"),
                "is_active": user.get("is_active", 1),
                "last_login_at": user.get("last_login_at")
            }
        }), 200

    # -------------------------------------------------------------
    # User Account Administration APIs (Admin Only)
    # -------------------------------------------------------------
    @app.route("/api/admin/users", methods=["GET"])
    @admin_required
    def api_admin_list_users():
        """Lists all user accounts."""
        db_path = app.config["DATABASE_PATH"]
        users = list_users(db_path=db_path)
        return jsonify({"count": len(users), "users": users}), 200

    @app.route("/api/admin/users", methods=["POST"])
    @admin_required
    def api_admin_create_user():
        """Creates a new authorized user account."""
        db_path = app.config["DATABASE_PATH"]
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        role = data.get("role")
        full_name = data.get("full_name")
        email = data.get("email")

        try:
            new_user = create_user(
                username=username,
                raw_password=password,
                role=role,
                full_name=full_name,
                email=email,
                db_path=db_path
            )
            record_audit(
                action=ACTION_USER_CREATED,
                details={"created_user": username, "role": role, "full_name": full_name},
                db_path=db_path
            )
            return jsonify({"success": True, "user": new_user}), 201
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to create user: {str(e)}"}), 500

    @app.route("/api/admin/users/<int:user_id>", methods=["PUT"])
    @admin_required
    def api_admin_update_user(user_id):
        """Updates user account details or active status."""
        db_path = app.config["DATABASE_PATH"]
        data = request.get_json(silent=True) or {}

        try:
            updated = update_user(
                user_id=user_id,
                role=data.get("role"),
                full_name=data.get("full_name"),
                email=data.get("email"),
                is_active=data.get("is_active"),
                db_path=db_path
            )
            record_audit(
                action=ACTION_USER_UPDATED,
                details={"user_id": user_id, "updated_fields": list(data.keys())},
                db_path=db_path
            )
            return jsonify({"success": True, "user": updated}), 200
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to update user: {str(e)}"}), 500

    @app.route("/api/admin/users/<int:user_id>/reset-password", methods=["POST"])
    @admin_required
    def api_admin_reset_password(user_id):
        """Resets user password."""
        db_path = app.config["DATABASE_PATH"]
        data = request.get_json(silent=True) or {}
        new_password = data.get("new_password")

        if not new_password or len(new_password) < 6:
            return jsonify({"error": "Password must be at least 6 characters long."}), 400

        try:
            reset_password(user_id, new_password, db_path=db_path)
            record_audit(
                action=ACTION_PASSWORD_RESET,
                details={"user_id": user_id, "action": "Password reset by administrator"},
                db_path=db_path
            )
            return jsonify({"success": True, "message": "Password successfully reset."}), 200
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to reset password: {str(e)}"}), 500

    @app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
    @admin_required
    def api_admin_delete_user(user_id):
        """Deletes user account."""
        db_path = app.config["DATABASE_PATH"]
        try:
            delete_user(user_id, db_path=db_path)
            record_audit(
                action=ACTION_USER_DELETED,
                details={"user_id": user_id, "action": "User deleted by administrator"},
                db_path=db_path
            )
            return jsonify({"success": True, "message": "User successfully deleted."}), 200
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to delete user: {str(e)}"}), 500

    # -------------------------------------------------------------
    # System Configuration & Thresholds APIs
    # -------------------------------------------------------------
    @app.route("/api/admin/config", methods=["GET"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN, ROLE_READONLY)
    def api_admin_get_config():
        """Returns dynamic system settings and congestion thresholds."""
        db_path = app.config["DATABASE_PATH"]
        settings = get_all_settings(db_path=db_path)
        thresholds = get_active_thresholds(db_path=db_path)
        return jsonify({
            "settings": settings,
            "thresholds": thresholds,
            "enforcement_safety": {
                "enforcement_enabled": is_enforcement_enabled(db_path=db_path),
                "production_allowed": is_production_enforcement_allowed(db_path=db_path),
                "target_environment": get_setting("active_environment_target", "ISOLATED_TESTBED", db_path=db_path)
            }
        }), 200

    @app.route("/api/admin/config", methods=["PUT"])
    @admin_required
    def api_admin_update_config():
        """Updates dynamic system settings or congestion thresholds."""
        db_path = app.config["DATABASE_PATH"]
        data = request.get_json(silent=True) or {}
        user = get_current_user()
        updated_by = user["username"] if user else "admin"

        if not data:
            return jsonify({"error": "No configuration parameters provided."}), 400

        updated_keys = []
        for k, v in data.items():
            update_setting(k, str(v), updated_by=updated_by, db_path=db_path)
            updated_keys.append(k)

        # Record audit log
        action = ACTION_THRESHOLD_MODIFIED if any("threshold" in k for k in updated_keys) else ACTION_CONFIG_UPDATED
        record_audit(
            action=action,
            details={"updated_keys": updated_keys, "values": data},
            user=user,
            db_path=db_path
        )

        return jsonify({
            "success": True,
            "message": f"Successfully updated {len(updated_keys)} configuration setting(s).",
            "updated_settings": get_all_settings(db_path=db_path)
        }), 200

    # -------------------------------------------------------------
    # Segment Administration APIs (Admin Only)
    # -------------------------------------------------------------
    @app.route("/api/admin/segments", methods=["POST"])
    @admin_required
    def api_admin_create_segment():
        """Creates a new campus network segment."""
        db_path = app.config["DATABASE_PATH"]
        data = request.get_json(silent=True) or {}

        sid = data.get("id") or f"seg_{data.get('name', 'new').lower().replace(' ', '_')}"
        name = data.get("name")
        description = data.get("description", "")
        capacity_mbps = float(data.get("capacity_mbps", 100.0))
        demand_mbps = float(data.get("demand_mbps", 50.0))
        priority_weight = float(data.get("priority_weight", 1.0))
        min_guaranteed = float(data.get("min_guaranteed_mbps", 0.0))
        max_limit = float(data.get("max_limit_mbps")) if data.get("max_limit_mbps") is not None else None

        if not name:
            return jsonify({"error": "Segment name is required."}), 400

        now = datetime.now(timezone.utc).isoformat()
        util = calculate_utilization(demand_mbps, capacity_mbps)
        status = compute_segment_status(util)

        conn = get_db(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO segments (
                    id, name, description, capacity_mbps, demand_mbps, allocated_mbps,
                    priority_weight, min_guaranteed_mbps, max_limit_mbps, latency_ms,
                    packet_loss_pct, jitter_ms, throughput_mbps, utilization_pct,
                    status, data_source, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 20.0, 0.0, 2.0, ?, ?, ?, 'SIMULATED', ?);
                """,
                (sid, name, description, capacity_mbps, demand_mbps, demand_mbps, priority_weight, min_guaranteed, max_limit, demand_mbps, util, status, now)
            )
            conn.commit()

            record_audit(
                action=ACTION_SEGMENT_CREATED,
                details={"segment_id": sid, "name": name, "capacity_mbps": capacity_mbps, "priority_weight": priority_weight},
                db_path=db_path
            )
            return jsonify({"success": True, "segment_id": sid, "message": f"Segment '{name}' created."}), 201
        except Exception as e:
            conn.rollback()
            return jsonify({"error": f"Failed to create segment: {str(e)}"}), 400

    @app.route("/api/admin/segments/<seg_id>", methods=["PUT"])
    @admin_required
    def api_admin_update_segment(seg_id):
        """Updates segment capacity, priority weight, and guarantees."""
        db_path = app.config["DATABASE_PATH"]
        data = request.get_json(silent=True) or {}
        conn = get_db(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM segments WHERE id = ?;", (seg_id,))
        seg = cursor.fetchone()
        if not seg:
            return jsonify({"error": f"Segment '{seg_id}' not found."}), 404

        now = datetime.now(timezone.utc).isoformat()
        cap = float(data.get("capacity_mbps", seg["capacity_mbps"]))
        dem = float(data.get("demand_mbps", seg["demand_mbps"]))
        alloc = float(data.get("allocated_mbps", seg["allocated_mbps"]))
        weight = float(data.get("priority_weight", seg["priority_weight"]))
        min_g = float(data.get("min_guaranteed_mbps", seg["min_guaranteed_mbps"]))
        max_l = float(data.get("max_limit_mbps")) if data.get("max_limit_mbps") is not None else seg["max_limit_mbps"]

        util = calculate_utilization(alloc, cap)
        status = compute_segment_status(util, latency_ms=seg["latency_ms"], packet_loss_pct=seg["packet_loss_pct"])

        cursor.execute(
            """
            UPDATE segments
            SET capacity_mbps = ?, demand_mbps = ?, allocated_mbps = ?,
                priority_weight = ?, min_guaranteed_mbps = ?, max_limit_mbps = ?,
                utilization_pct = ?, status = ?, updated_at = ?
            WHERE id = ?;
            """,
            (cap, dem, alloc, weight, min_g, max_l, util, status, now, seg_id)
        )
        conn.commit()

        record_audit(
            action=ACTION_SEGMENT_MODIFIED,
            details={"segment_id": seg_id, "capacity_mbps": cap, "priority_weight": weight, "demand_mbps": dem},
            db_path=db_path
        )
        return jsonify({"success": True, "message": f"Segment '{seg_id}' updated."}), 200

    @app.route("/api/admin/segments/<seg_id>", methods=["DELETE"])
    @admin_required
    def api_admin_delete_segment(seg_id):
        """Deletes segment from the network topology."""
        db_path = app.config["DATABASE_PATH"]
        conn = get_db(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM segments WHERE id = ?;", (seg_id,))
        seg = cursor.fetchone()
        if not seg:
            return jsonify({"error": f"Segment '{seg_id}' not found."}), 404

        cursor.execute("DELETE FROM segments WHERE id = ?;", (seg_id,))
        conn.commit()

        record_audit(
            action=ACTION_SEGMENT_DELETED,
            details={"segment_id": seg_id, "name": seg["name"]},
            db_path=db_path
        )
        return jsonify({"success": True, "message": f"Segment '{seg_id}' deleted."}), 200

    # -------------------------------------------------------------
    # Optimization Policy Approval Workflow APIs
    # -------------------------------------------------------------
    @app.route("/api/policies", methods=["GET"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN, ROLE_READONLY)
    def api_list_policies():
        """Lists optimization policies with optional status filtering."""
        status_filter = request.args.get("status")
        limit = request.args.get("limit", default=50, type=int)
        db_path = app.config["DATABASE_PATH"]

        try:
            policies = list_policies(status=status_filter, limit=limit, db_path=db_path)
            return jsonify({"count": len(policies), "policies": policies}), 200
        except PolicyWorkflowError as pwe:
            return jsonify({"error": str(pwe)}), 400

    @app.route("/api/policies/<int:policy_id>", methods=["GET"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN, ROLE_READONLY)
    def api_get_policy(policy_id):
        """Retrieves details and allocation breakdown for a single policy."""
        db_path = app.config["DATABASE_PATH"]
        policy = get_policy(policy_id, db_path=db_path)
        if not policy:
            return jsonify({"error": f"Policy #{policy_id} not found."}), 404
        return jsonify(policy), 200

    @app.route("/api/policies/propose", methods=["POST"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN)
    def api_propose_policy():
        """Submits an optimization policy for administrative review (PENDING state)."""
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        description = data.get("description", "")
        policy_data = data.get("policy_data")
        target_env = data.get("target_environment", "ISOLATED_TESTBED")

        user = get_current_user()
        proposed_by = user["username"] if user else "netadmin"
        db_path = app.config["DATABASE_PATH"]

        try:
            policy = propose_policy(
                name=name,
                description=description,
                policy_data=policy_data,
                proposed_by=proposed_by,
                target_environment=target_env,
                db_path=db_path
            )
            return jsonify({
                "success": True,
                "message": f"Policy '{name}' submitted for review. Current status: PENDING.",
                "policy": policy
            }), 201
        except PolicyWorkflowError as pwe:
            return jsonify({"error": str(pwe)}), 400
        except Exception as e:
            return jsonify({"error": f"Failed to propose policy: {str(e)}"}), 500

    @app.route("/api/policies/<int:policy_id>/approve", methods=["POST"])
    @admin_required
    def api_approve_policy(policy_id):
        """Approves a PENDING policy. (Administrator only)."""
        user = get_current_user()
        reviewed_by = user["username"] if user else "admin"
        db_path = app.config["DATABASE_PATH"]

        try:
            policy = approve_policy(policy_id, reviewed_by=reviewed_by, db_path=db_path)
            return jsonify({
                "success": True,
                "message": f"Policy #{policy_id} approved. Ready for execution in isolated test network.",
                "policy": policy
            }), 200
        except PolicyWorkflowError as pwe:
            return jsonify({"error": str(pwe)}), 400
        except Exception as e:
            return jsonify({"error": f"Approval error: {str(e)}"}), 500

    @app.route("/api/policies/<int:policy_id>/reject", methods=["POST"])
    @admin_required
    def api_reject_policy(policy_id):
        """Rejects a PENDING policy with explicit justification. (Administrator only)."""
        data = request.get_json(silent=True) or {}
        reason = data.get("reason", "")
        user = get_current_user()
        reviewed_by = user["username"] if user else "admin"
        db_path = app.config["DATABASE_PATH"]

        try:
            policy = reject_policy(policy_id, reviewed_by=reviewed_by, reason=reason, db_path=db_path)
            return jsonify({
                "success": True,
                "message": f"Policy #{policy_id} rejected.",
                "policy": policy
            }), 200
        except PolicyWorkflowError as pwe:
            return jsonify({"error": str(pwe)}), 400
        except Exception as e:
            return jsonify({"error": f"Rejection error: {str(e)}"}), 500

    @app.route("/api/policies/<int:policy_id>/apply", methods=["POST"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN)
    def api_apply_policy(policy_id):
        """
        Executes an APPROVED policy in the isolated test network.
        Production network application is strictly disabled by default.
        """
        user = get_current_user()
        applied_by = user["username"] if user else "netadmin"
        db_path = app.config["DATABASE_PATH"]

        try:
            policy = apply_policy(policy_id, applied_by=applied_by, db_path=db_path)
            return jsonify({
                "success": True,
                "message": f"Policy #{policy_id} successfully executed in {policy['target_environment']}.",
                "policy": policy
            }), 200
        except SafetyEnforcementError as see:
            record_audit(
                action=ACTION_UNAUTHORIZED_ACCESS,
                details={"policy_id": policy_id, "violation": str(see)},
                user=user,
                db_path=db_path
            )
            return jsonify({"error": str(see), "safety_violation": True}), 403
        except PolicyWorkflowError as pwe:
            return jsonify({"error": str(pwe)}), 400
        except Exception as e:
            return jsonify({"error": f"Execution error: {str(e)}"}), 500

    @app.route("/api/policies/<int:policy_id>/rollback", methods=["POST"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN)
    def api_rollback_policy(policy_id):
        """Restores segment allocations to pre-application state."""
        user = get_current_user()
        rolled_back_by = user["username"] if user else "netadmin"
        db_path = app.config["DATABASE_PATH"]

        try:
            policy = rollback_policy(policy_id, rolled_back_by=rolled_back_by, db_path=db_path)
            return jsonify({
                "success": True,
                "message": f"Policy #{policy_id} rolled back. Previous network allocations restored.",
                "policy": policy
            }), 200
        except PolicyWorkflowError as pwe:
            return jsonify({"error": str(pwe)}), 400
        except Exception as e:
            return jsonify({"error": f"Rollback error: {str(e)}"}), 500

    # -------------------------------------------------------------
    # Audit Trail APIs
    # -------------------------------------------------------------
    @app.route("/api/audit-logs", methods=["GET"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN, ROLE_READONLY)
    def api_get_audit_logs():
        """Returns paginated and filtered security and operational audit logs."""
        limit = request.args.get("limit", default=100, type=int)
        offset = request.args.get("offset", default=0, type=int)
        action = request.args.get("action")
        username = request.args.get("username")
        search = request.args.get("search")
        db_path = app.config["DATABASE_PATH"]

        results = query_audit_logs(
            limit=limit,
            offset=offset,
            action=action,
            username=username,
            search=search,
            db_path=db_path
        )
        return jsonify(results), 200

    @app.route("/api/audit-logs/export", methods=["GET"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN, ROLE_READONLY)
    def api_export_audit_logs_csv():
        """Downloads full audit trail as CSV."""
        db_path = app.config["DATABASE_PATH"]
        user = get_current_user()
        record_audit(
            action=ACTION_REPORT_DOWNLOADED,
            details="Security & Operations Audit Trail CSV exported",
            user=user,
            db_path=db_path
        )
        csv_data = generate_audit_csv(limit=1000, db_path=db_path)
        return send_file(
            io.BytesIO(csv_data.encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"campusnet_audit_trail_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        )

    # -------------------------------------------------------------
    # Report Generation & Download Center APIs
    # -------------------------------------------------------------
    @app.route("/api/reports/telemetry", methods=["GET"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN, ROLE_READONLY)
    def api_report_telemetry_csv():
        """Downloads full telemetry & QoS allocations report as CSV."""
        db_path = app.config["DATABASE_PATH"]
        csv_data = generate_telemetry_csv(db_path=db_path)
        return send_file(
            io.BytesIO(csv_data.encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"campusnet_telemetry_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        )

    @app.route("/api/reports/policies", methods=["GET"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN, ROLE_READONLY)
    def api_report_policies_csv():
        """Downloads complete optimization policy lifecycle report as CSV."""
        db_path = app.config["DATABASE_PATH"]
        csv_data = generate_policies_csv(limit=200, db_path=db_path)
        return send_file(
            io.BytesIO(csv_data.encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"campusnet_policies_history_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        )

    @app.route("/api/reports/executive", methods=["GET"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN, ROLE_READONLY)
    def api_report_executive():
        """Generates executive printable summary compliance report."""
        db_path = app.config["DATABASE_PATH"]
        html_report = generate_executive_html_report(db_path=db_path)
        return html_report, 200, {"Content-Type": "text/html; charset=utf-8"}

    # -------------------------------------------------------------
    # Summary & Segment Telemetry APIs
    # -------------------------------------------------------------
    @app.route("/api/summary", methods=["GET"])
    def api_summary():
        """Provides high-level campus summary metrics and alert totals."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM segments;")
        segments = [dict(row) for row in cursor.fetchall()]

        cap_param = request.args.get("capacity", type=float)
        shared_cap = cap_param if cap_param else app.config["DEFAULT_CAMPUS_CAPACITY_MBPS"]

        summary = aggregate_network_summary(segments, shared_capacity_mbps=shared_cap)

        cursor.execute("SELECT COUNT(*) AS total, SUM(CASE WHEN severity = 'CRITICAL' THEN 1 ELSE 0 END) AS criticals FROM alerts WHERE is_resolved = 0;")
        alert_row = cursor.fetchone()
        active_total = alert_row["total"] if alert_row else 0
        active_crit = alert_row["criticals"] if alert_row and alert_row["criticals"] else 0

        summary["active_alerts"] = {
            "total": active_total,
            "critical": active_crit,
            "warning": active_total - active_crit
        }
        summary["data_source_badge"] = "SIMULATED" if any(s["data_source"] == "SIMULATED" for s in segments) else "IMPORTED"

        db_path = app.config["DATABASE_PATH"]
        summary["enforcement_status"] = {
            "enabled": is_enforcement_enabled(db_path),
            "production_allowed": is_production_enforcement_allowed(db_path),
            "target_environment": get_setting("active_environment_target", "ISOLATED_TESTBED", db_path)
        }

        return jsonify(summary), 200

    @app.route("/api/segments", methods=["GET"])
    def api_segments():
        """Returns details for all 5 campus segments."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM segments ORDER BY priority_weight DESC;")
        segments = [dict(row) for row in cursor.fetchall()]

        for seg in segments:
            seg["utilization_pct"] = calculate_utilization(seg["allocated_mbps"], seg["capacity_mbps"])
            seg["unmet_demand_mbps"] = calculate_unmet_demand(seg["demand_mbps"], seg["allocated_mbps"])
            seg["satisfaction_pct"] = calculate_satisfaction_rate(seg["allocated_mbps"], seg["demand_mbps"])

        return jsonify({
            "count": len(segments),
            "segments": segments
        }), 200

    # -------------------------------------------------------------
    # Alert APIs
    # -------------------------------------------------------------
    @app.route("/api/alerts", methods=["GET"])
    def api_alerts():
        """Returns active congestion and threshold alerts."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT a.*, s.name AS segment_name
            FROM alerts a
            JOIN segments s ON a.segment_id = s.id
            WHERE a.is_resolved = 0
            ORDER BY a.severity DESC, a.id DESC;
            """
        )
        alerts = [dict(row) for row in cursor.fetchall()]
        return jsonify({
            "count": len(alerts),
            "alerts": alerts
        }), 200

    # -------------------------------------------------------------
    # Measurements APIs (for charting)
    # -------------------------------------------------------------
    @app.route("/api/measurements", methods=["GET"])
    def api_measurements():
        """Returns timeseries measurements for dashboard charts."""
        conn = get_db()
        cursor = conn.cursor()
        limit = request.args.get("limit", default=50, type=int)
        cursor.execute(
            """
            SELECT m.*, s.name AS segment_name
            FROM measurements m
            JOIN segments s ON m.segment_id = s.id
            ORDER BY m.id DESC LIMIT ?;
            """,
            (limit,)
        )
        measurements = [dict(row) for row in cursor.fetchall()]
        measurements.reverse()
        return jsonify({
            "count": len(measurements),
            "measurements": measurements
        }), 200

    # -------------------------------------------------------------
    # Optimization Engine API (WFQ-PF)
    # -------------------------------------------------------------
    @app.route("/api/optimize", methods=["POST"])
    def api_optimize():
        """
        Executes the WFQ-PF bandwidth optimization algorithm.
        Supports preview mode or applying directly to database (requires authorization).
        """
        data = request.get_json(silent=True) or {}
        apply_changes = data.get("apply", False)
        custom_cap = data.get("total_capacity_mbps", app.config["DEFAULT_CAMPUS_CAPACITY_MBPS"])
        db_path = app.config["DATABASE_PATH"]

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM segments;")
        segments = [dict(row) for row in cursor.fetchall()]

        # Apply any custom overrides submitted in the request
        custom_segments = data.get("segments")
        if custom_segments:
            seg_map = {s["id"]: s for s in segments}
            for cs in custom_segments:
                sid = cs.get("id")
                if sid in seg_map:
                    if "demand_mbps" in cs:
                        seg_map[sid]["demand_mbps"] = float(cs["demand_mbps"])
                    if "priority_weight" in cs:
                        seg_map[sid]["priority_weight"] = float(cs["priority_weight"])
                    if "min_guaranteed_mbps" in cs:
                        seg_map[sid]["min_guaranteed_mbps"] = float(cs["min_guaranteed_mbps"])
                    if "max_limit_mbps" in cs:
                        seg_map[sid]["max_limit_mbps"] = float(cs["max_limit_mbps"]) if cs["max_limit_mbps"] is not None else None
            segments = list(seg_map.values())

        try:
            result = BandwidthOptimizer.optimize(custom_cap, segments)
        except OptimizationError as oe:
            return jsonify({"error": str(oe)}), 400
        except Exception as e:
            return jsonify({"error": f"Optimization failed: {str(e)}"}), 500

        # If user confirmed applying to database: verify permission
        if apply_changes:
            user = get_current_user()
            if not user:
                record_audit(
                    action=ACTION_UNAUTHORIZED_ACCESS,
                    details={"endpoint": "/api/optimize", "reason": "Unauthenticated apply attempt"},
                    db_path=db_path
                )
                return jsonify({"error": "Authentication required to apply optimization policies.", "status": 401}), 401

            if user["role"] not in (ROLE_ADMIN, ROLE_NETADMIN):
                record_audit(
                    action=ACTION_UNAUTHORIZED_ACCESS,
                    details={"endpoint": "/api/optimize", "user": user["username"], "role": user["role"]},
                    user=user,
                    db_path=db_path
                )
                return jsonify({"error": "Forbidden: Read-only authorities cannot apply changes.", "status": 403}), 403

            now = datetime.now(timezone.utc).isoformat()
            thresholds = get_active_thresholds(db_path=db_path)
            detector = CongestionDetector(
                warn_util=thresholds["warn_util"],
                crit_util=thresholds["crit_util"],
                warn_lat=thresholds["warn_lat"],
                crit_lat=thresholds["crit_lat"],
                warn_loss=thresholds["warn_loss"],
                crit_loss=thresholds["crit_loss"]
            )

            # Clear old un-resolved alerts before re-evaluating
            cursor.execute("DELETE FROM alerts;")

            for seg_res in result["segments"]:
                sid = seg_res["id"]
                new_alloc = seg_res["allocated_mbps"]
                new_demand = seg_res["demand_mbps"]
                new_weight = seg_res["priority_weight"]

                cursor.execute("SELECT capacity_mbps FROM segments WHERE id = ?;", (sid,))
                srow = cursor.fetchone()
                seg_cap = srow["capacity_mbps"] if srow else 100.0

                new_util = calculate_utilization(new_alloc, seg_cap)
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
                    (sid, round(new_alloc * 0.98, 2), post_lat, post_loss, 3.0, new_util, "SIMULATED", now, "Post-optimization QoS schedule")
                )

                eval_seg = {
                    "id": sid,
                    "name": seg_res["name"],
                    "utilization_pct": new_util,
                    "latency_ms": post_lat,
                    "packet_loss_pct": post_loss,
                    "data_source": "SIMULATED"
                }
                new_alerts = detector.evaluate_segment(eval_seg)
                for alert in new_alerts:
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

            # Record policy in history
            cursor.execute(
                """
                INSERT INTO policies (name, description, parameters_json, is_active, created_at)
                VALUES (?, ?, ?, 1, ?);
                """,
                (
                    f"QoS Policy - {now[:19]}",
                    result["policy_summary"],
                    json.dumps({"total_capacity_mbps": custom_cap, "results": result["segments"]}),
                    now
                )
            )
            conn.commit()

            record_audit(
                action=ACTION_POLICY_APPLIED,
                details={
                    "policy_summary": result["policy_summary"],
                    "total_allocated_mbps": result["total_allocated_mbps"],
                    "applied_by": user["username"]
                },
                user=user,
                db_path=db_path
            )
            result["applied"] = True
        else:
            result["applied"] = False

        return jsonify(result), 200

    # -------------------------------------------------------------
    # Scenarios & Experiments APIs
    # -------------------------------------------------------------
    @app.route("/api/scenarios", methods=["GET"])
    def api_scenarios():
        """Returns available pre-built demonstration scenarios."""
        return jsonify({
            "scenarios": [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "description": s["description"],
                    "shared_capacity_mbps": s["shared_capacity_mbps"]
                }
                for s in SCENARIOS.values()
            ]
        }), 200

    @app.route("/api/experiments/run", methods=["POST"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN)
    def api_run_experiment():
        """Executes a controlled before-and-after experiment."""
        data = request.get_json(silent=True) or {}
        scenario_id = data.get("scenario_id", "peak_classes")
        custom_cap = data.get("shared_capacity_mbps")
        custom_weights = data.get("weights")
        notes = data.get("notes", "")
        db_path = app.config["DATABASE_PATH"]
        user = get_current_user()

        try:
            exp_result = run_experiment(
                scenario_id=scenario_id,
                custom_capacity_mbps=custom_cap,
                custom_weights=custom_weights,
                notes=notes
            )
            record_audit(
                action=ACTION_EXPERIMENT_RUN,
                details={"scenario_id": scenario_id, "notes": notes, "experiment_id": exp_result.get("experiment_id")},
                user=user,
                db_path=db_path
            )
            return jsonify(exp_result), 200
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400
        except Exception as e:
            return jsonify({"error": f"Experiment failed: {str(e)}"}), 500

    @app.route("/api/history", methods=["GET"])
    def api_history():
        """Returns list of past experiments and comparison summaries."""
        limit = request.args.get("limit", default=10, type=int)
        items = list_experiments(limit=limit)
        return jsonify({
            "count": len(items),
            "experiments": items
        }), 200

    @app.route("/api/experiments/<int:exp_id>/compare", methods=["GET"])
    def api_experiment_compare(exp_id):
        """Retrieves detailed comparison for a specific experiment ID."""
        exp = get_experiment_by_id(exp_id)
        if not exp:
            return jsonify({"error": f"Experiment ID {exp_id} not found."}), 404
        return jsonify(exp), 200

    # -------------------------------------------------------------
    # CSV Import & Export APIs
    # -------------------------------------------------------------
    @app.route("/api/import/csv", methods=["POST"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN)
    def api_import_csv():
        """Uploads and validates aggregate network measurements CSV."""
        db_path = app.config["DATABASE_PATH"]
        user = get_current_user()

        if "file" not in request.files:
            return jsonify({"error": "No file uploaded. Please upload a file with field name 'file'."}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected."}), 400

        if not file.filename.lower().endswith(".csv"):
            return jsonify({"error": "Only .csv files are supported."}), 400

        try:
            result = validate_and_import_csv(file, db_path=db_path)
            record_audit(
                action=ACTION_CSV_IMPORTED,
                details={"filename": file.filename, "rows_imported": result.get("imported_count", 0)},
                user=user,
                db_path=db_path
            )
            return jsonify(result), 200
        except CSVValidationError as cve:
            return jsonify({"error": str(cve)}), 400
        except Exception as e:
            return jsonify({"error": f"CSV import error: {str(e)}"}), 500

    @app.route("/api/export.csv", methods=["GET"])
    def api_export_csv():
        """Exports current segment status, demand, and allocations to CSV."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM segments ORDER BY name ASC;")
        segments = cursor.fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Segment ID", "Segment Name", "Modeled Capacity (Mbps)", "Requested Demand (Mbps)",
            "Allocated Bandwidth (Mbps)", "Priority Weight", "Utilization (%)",
            "Latency (ms)", "Packet Loss (%)", "Status", "Data Source", "Last Updated"
        ])

        for s in segments:
            writer.writerow([
                s["id"], s["name"], s["capacity_mbps"], s["demand_mbps"],
                s["allocated_mbps"], s["priority_weight"], s["utilization_pct"],
                s["latency_ms"], s["packet_loss_pct"], s["status"],
                s["data_source"], s["updated_at"]
            ])

        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode("utf-8")),
            mimetype="text/csv",
            as_attachment=True,
            download_name=f"campusnet_status_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        )

    # -------------------------------------------------------------
    # Demo Reset API
    # -------------------------------------------------------------
    @app.route("/api/demo/reset", methods=["POST"])
    @roles_required(ROLE_ADMIN, ROLE_NETADMIN)
    def api_demo_reset():
        """Restores calibrated baseline demonstration dataset."""
        db_path = app.config["DATABASE_PATH"]
        user = get_current_user()
        try:
            reset_db(db_path)
            record_audit(
                action=ACTION_DEMO_RESET,
                details="Calibrated baseline dataset reset executed",
                user=user,
                db_path=db_path
            )
            return jsonify({
                "success": True,
                "message": "Demo state successfully reset to calibrated baseline.",
                "data_source": "SIMULATED",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }), 200
        except Exception as e:
            return jsonify({"error": f"Failed to reset demo: {str(e)}"}), 500

    # -------------------------------------------------------------
    # Lab Enforcement Preview API
    # -------------------------------------------------------------
    @app.route("/api/lab/preview", methods=["GET"])
    def api_lab_preview():
        """Returns Linux TC / Mininet QoS configuration script for current allocations."""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM segments;")
        segments = [dict(row) for row in cursor.fetchall()]

        preview = LabAdapter.apply_policy_preview(
            segments,
            shared_capacity_mbps=app.config["DEFAULT_CAMPUS_CAPACITY_MBPS"]
        )
        return jsonify(preview), 200

    # -------------------------------------------------------------
    # Generic Error Handlers
    # -------------------------------------------------------------
    @app.errorhandler(404)
    def handle_404(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Resource or endpoint not found", "status": 404}), 404
        return render_template("index.html"), 404

    @app.errorhandler(500)
    def handle_500(e):
        return jsonify({"error": "Internal server error occurred", "status": 500}), 500

    return app


# CLI / Main entry point
app = create_app(DevelopmentConfig)

if __name__ == "__main__":
    print("=" * 70)
    print("   CampusNet: Adaptive Campus Network Performance Optimization")
    print("   Authority & Administration Module Active")
    print("   Dashboard URL: http://127.0.0.1:5000")
    print("   Also accessible via: http://localhost:5000")
    print("=" * 70)
    app.run(host="0.0.0.0", port=5000, debug=False)
