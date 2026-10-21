"""
CampusNet: Tests for Authority and Administration Module
Validates authentication, RBAC permissions, unauthorized rejections,
policy approval lifecycle, rollback, audit logging, and production safety guards.
"""

import json
import pytest
from app import create_app
from config import TestingConfig
from database.db import get_db
from services.auth import (
    hash_password, verify_password,
    ROLE_ADMIN, ROLE_NETADMIN, ROLE_READONLY
)
from services.policies import (
    STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_APPLIED, STATUS_ROLLED_BACK
)


@pytest.fixture
def auth_app(tmp_path):
    test_db = str(tmp_path / "test_auth_admin_campusnet.db")

    class AuthTestingConfig(TestingConfig):
        DATABASE_PATH = test_db
        TESTING = True

    app = create_app(AuthTestingConfig)
    return app


@pytest.fixture
def client(auth_app):
    with auth_app.test_client() as c:
        yield c


def login(client, username, password):
    """Helper to log in a user."""
    return client.post("/api/auth/login", json={"username": username, "password": password})


# ============================================================================
# 1. Password Hashing & Verification Tests
# ============================================================================

def test_password_hashing():
    raw = "SecureP@ssw0rd123"
    hashed = hash_password(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

    with pytest.raises(ValueError):
        hash_password("123")  # Too short


# ============================================================================
# 2. Authentication & Session Tests
# ============================================================================

def test_login_success_and_session(client):
    res = login(client, "admin", "Admin@CampusNet2026")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == ROLE_ADMIN

    # Verify session via /api/auth/me
    res_me = client.get("/api/auth/me")
    assert res_me.status_code == 200
    me_data = res_me.get_json()
    assert me_data["authenticated"] is True
    assert me_data["user"]["username"] == "admin"

    # Logout
    res_logout = client.post("/api/auth/logout")
    assert res_logout.status_code == 200
    assert res_logout.get_json()["success"] is True

    # After logout, me endpoint reports unauthenticated
    res_me_after = client.get("/api/auth/me")
    assert res_me_after.get_json()["authenticated"] is False


def test_login_invalid_credentials(client):
    res = login(client, "admin", "WrongPassword!123")
    assert res.status_code == 401
    assert "Invalid username or password" in res.get_json()["error"]

    res_user = login(client, "nonexistent_user", "SomePassword")
    assert res_user.status_code == 401


def test_login_deactivated_account(client, auth_app):
    # Deactivate netadmin
    with auth_app.app_context():
        conn = get_db(auth_app.config["DATABASE_PATH"])
        conn.execute("UPDATE users SET is_active = 0 WHERE username = 'netadmin';")
        conn.commit()

    res = login(client, "netadmin", "NetAdmin@CampusNet2026")
    assert res.status_code == 403
    assert "deactivated" in res.get_json()["error"].lower()


# ============================================================================
# 3. Unauthenticated Access & Permission Rejection Tests
# ============================================================================

def test_unauthenticated_requests_rejected(client):
    # Without logging in, sensitive endpoints must return 401
    endpoints = [
        ("GET", "/api/admin/users"),
        ("POST", "/api/admin/users"),
        ("GET", "/api/admin/config"),
        ("PUT", "/api/admin/config"),
        ("POST", "/api/admin/segments"),
        ("GET", "/api/policies"),
        ("POST", "/api/policies/propose"),
        ("GET", "/api/audit-logs"),
        ("GET", "/api/reports/executive")
    ]

    for method, path in endpoints:
        if method == "GET":
            r = client.get(path)
        elif method == "PUT":
            r = client.put(path, json={})
        else:
            r = client.post(path, json={})
        assert r.status_code == 401, f"Expected 401 for unauthenticated {method} {path}, got {r.status_code}"


# ============================================================================
# 4. Role-Based Access Control (RBAC) Tests
# ============================================================================

def test_readonly_authority_permissions(client):
    # Log in as Read-Only Authority
    res_login = login(client, "authority", "Authority@CampusNet2026")
    assert res_login.status_code == 200

    # CAN view dashboards, audit logs, reports, and policies
    assert client.get("/api/audit-logs").status_code == 200
    assert client.get("/api/reports/executive").status_code == 200
    assert client.get("/api/policies").status_code == 200
    assert client.get("/api/admin/config").status_code == 200

    # CANNOT modify config or thresholds
    res_cfg = client.put("/api/admin/config", json={"threshold_warning_utilization": "75.0"})
    assert res_cfg.status_code == 403

    # CANNOT manage users
    res_users = client.get("/api/admin/users")
    assert res_users.status_code == 403

    # CANNOT propose policies or apply optimization
    res_prop = client.post("/api/policies/propose", json={"name": "Test"})
    assert res_prop.status_code == 403

    res_opt = client.post("/api/optimize", json={"apply": True})
    assert res_opt.status_code == 403


def test_network_administrator_permissions(client):
    # Log in as Network Administrator
    login(client, "netadmin", "NetAdmin@CampusNet2026")

    # CAN propose policies and run experiments
    res_scen = client.get("/api/scenarios")
    assert res_scen.status_code == 200

    # CANNOT access user account administration
    res_users = client.get("/api/admin/users")
    assert res_users.status_code == 403

    # CANNOT modify global system settings or thresholds
    res_cfg = client.put("/api/admin/config", json={"threshold_warning_utilization": "75.0"})
    assert res_cfg.status_code == 403

    # CANNOT approve policies (separation of duties)
    res_appr = client.post("/api/policies/1/approve")
    assert res_appr.status_code == 403


def test_admin_user_management(client):
    login(client, "admin", "Admin@CampusNet2026")

    # List users
    res_list = client.get("/api/admin/users")
    assert res_list.status_code == 200
    assert res_list.get_json()["count"] >= 3

    # Create new user
    new_user_payload = {
        "username": "lab_tech_1",
        "password": "LabTechSecurePassword1",
        "role": "netadmin",
        "full_name": "Lab Technician Alice",
        "email": "alice@campus.edu"
    }
    res_create = client.post("/api/admin/users", json=new_user_payload)
    assert res_create.status_code == 201
    created_id = res_create.get_json()["user"]["id"]

    # Update user role/email
    res_update = client.put(f"/api/admin/users/{created_id}", json={"role": "readonly", "email": "alice_updated@campus.edu"})
    assert res_update.status_code == 200
    assert res_update.get_json()["user"]["role"] == "readonly"

    # Reset password
    res_reset = client.post(f"/api/admin/users/{created_id}/reset-password", json={"new_password": "NewSecretPassword123"})
    assert res_reset.status_code == 200

    # Delete user
    res_del = client.delete(f"/api/admin/users/{created_id}")
    assert res_del.status_code == 200


# ============================================================================
# 5. Policy Lifecycle Approval Workflow Tests
# ============================================================================

def test_policy_approval_and_execution_lifecycle(client):
    # 1. NetAdmin proposes an optimization policy
    login(client, "netadmin", "NetAdmin@CampusNet2026")
    proposal_payload = {
        "name": "Evening Peak QoS Rebalance",
        "description": "Increases Computer Lab weight during evening programming finals",
        "target_environment": "ISOLATED_TESTBED",
        "policy_data": {
            "total_allocated_mbps": 800.0,
            "segments": [
                {"id": "seg_comp_lab", "name": "Computer Lab", "allocated_mbps": 280.0, "demand_mbps": 280.0, "priority_weight": 4.0},
                {"id": "seg_smart_class", "name": "Smart Classrooms", "allocated_mbps": 200.0, "demand_mbps": 260.0, "priority_weight": 4.0},
                {"id": "seg_library", "name": "Library", "allocated_mbps": 110.0, "demand_mbps": 110.0, "priority_weight": 2.0},
                {"id": "seg_admin", "name": "Administration", "allocated_mbps": 45.0, "demand_mbps": 45.0, "priority_weight": 5.0},
                {"id": "seg_guest_wifi", "name": "Guest Wi-Fi", "allocated_mbps": 165.0, "demand_mbps": 220.0, "priority_weight": 1.0}
            ]
        }
    }
    res_prop = client.post("/api/policies/propose", json=proposal_payload)
    assert res_prop.status_code == 201
    pol_id = res_prop.get_json()["policy"]["id"]
    assert res_prop.get_json()["policy"]["status"] == STATUS_PENDING

    # Attempting to apply a PENDING policy must fail
    res_early_apply = client.post(f"/api/policies/{pol_id}/apply")
    assert res_early_apply.status_code == 400
    assert "Policy must be in APPROVED state" in res_early_apply.get_json()["error"]

    # 2. Admin logs in and approves policy
    login(client, "admin", "Admin@CampusNet2026")
    res_appr = client.post(f"/api/policies/{pol_id}/approve")
    assert res_appr.status_code == 200
    assert res_appr.get_json()["policy"]["status"] == STATUS_APPROVED
    assert res_appr.get_json()["policy"]["reviewed_by"] == "admin"

    # 3. NetAdmin applies approved policy to isolated testbed
    login(client, "netadmin", "NetAdmin@CampusNet2026")
    res_apply = client.post(f"/api/policies/{pol_id}/apply")
    assert res_apply.status_code == 200
    applied_pol = res_apply.get_json()["policy"]
    assert applied_pol["status"] == STATUS_APPLIED
    assert applied_pol["applied_by"] == "netadmin"
    assert applied_pol["rollback_data"] is not None

    # Check that segment allocation was updated
    res_segs = client.get("/api/segments")
    segs = {s["id"]: s for s in res_segs.get_json()["segments"]}
    assert segs["seg_comp_lab"]["allocated_mbps"] == 280.0

    # 4. Rollback policy
    res_rb = client.post(f"/api/policies/{pol_id}/rollback")
    assert res_rb.status_code == 200
    rb_pol = res_rb.get_json()["policy"]
    assert rb_pol["status"] == STATUS_ROLLED_BACK

    # Check that segments were restored
    res_segs_after = client.get("/api/segments")
    segs_after = {s["id"]: s for s in res_segs_after.get_json()["segments"]}
    assert segs_after["seg_comp_lab"]["allocated_mbps"] == 240.0


def test_policy_rejection_workflow(client):
    login(client, "netadmin", "NetAdmin@CampusNet2026")
    res_prop = client.post("/api/policies/propose", json={
        "name": "Excessive Allocation Policy",
        "target_environment": "ISOLATED_TESTBED",
        "policy_data": {"segments": [{"id": "seg_guest_wifi", "allocated_mbps": 500.0, "demand_mbps": 500.0}]}
    })
    pol_id = res_prop.get_json()["policy"]["id"]

    # Admin rejects proposal
    login(client, "admin", "Admin@CampusNet2026")
    res_rej = client.post(f"/api/policies/{pol_id}/reject", json={"reason": "Excessive bandwidth assigned to non-academic Guest Wi-Fi"})
    assert res_rej.status_code == 200
    assert res_rej.get_json()["policy"]["status"] == STATUS_REJECTED
    assert res_rej.get_json()["policy"]["rejection_reason"] is not None

    # Applying a rejected policy must be blocked
    login(client, "netadmin", "NetAdmin@CampusNet2026")
    res_apply_fail = client.post(f"/api/policies/{pol_id}/apply")
    assert res_apply_fail.status_code == 400


# ============================================================================
# 6. Safety Enforcement Guard Tests (Requirement 12)
# ============================================================================

def test_production_enforcement_safety_guard(client):
    # Propose a policy targeting PRODUCTION
    login(client, "netadmin", "NetAdmin@CampusNet2026")
    res_prop = client.post("/api/policies/propose", json={
        "name": "Dangerous Production Policy",
        "target_environment": "PRODUCTION",
        "policy_data": {"segments": [{"id": "seg_admin", "allocated_mbps": 100.0, "demand_mbps": 100.0}]}
    })
    pol_id = res_prop.get_json()["policy"]["id"]

    # Admin approves
    login(client, "admin", "Admin@CampusNet2026")
    client.post(f"/api/policies/{pol_id}/approve")

    # Attempting to apply to PRODUCTION must be strictly blocked (403 Forbidden with safety violation)
    res_apply = client.post(f"/api/policies/{pol_id}/apply")
    assert res_apply.status_code == 403
    data = res_apply.get_json()
    assert data.get("safety_violation") is True
    assert "production campus network" in data["error"].lower()


# ============================================================================
# 7. Audit Trail Tests
# ============================================================================

def test_audit_logs_recorded(client):
    # Perform various actions
    login(client, "admin", "Admin@CampusNet2026")
    client.put("/api/admin/config", json={"threshold_warning_utilization": "72.0"})
    client.post("/api/auth/logout")

    # Read-only authority reviews audit trail
    login(client, "authority", "Authority@CampusNet2026")
    res_audit = client.get("/api/audit-logs?limit=50")
    assert res_audit.status_code == 200
    audit_data = res_audit.get_json()
    assert audit_data["count"] > 0

    actions = [l["action"] for l in audit_data["logs"]]
    assert "USER_LOGIN" in actions
    assert "THRESHOLD_MODIFIED" in actions
    assert "USER_LOGOUT" in actions

    # Export audit logs to CSV
    res_exp = client.get("/api/audit-logs/export")
    assert res_exp.status_code == 200
    assert res_exp.content_type.startswith("text/csv")
    csv_text = res_exp.data.decode("utf-8")
    assert "Timestamp (UTC)" in csv_text
    assert "admin" in csv_text


# ============================================================================
# 8. Report Generation Tests
# ============================================================================

def test_report_downloads(client):
    login(client, "authority", "Authority@CampusNet2026")

    # Telemetry report
    res_tel = client.get("/api/reports/telemetry")
    assert res_tel.status_code == 200
    assert res_tel.content_type.startswith("text/csv")
    assert "Computer Lab" in res_tel.data.decode("utf-8")

    # Policies history report
    res_pol = client.get("/api/reports/policies")
    assert res_pol.status_code == 200
    assert res_pol.content_type.startswith("text/csv")

    # Executive HTML summary report
    res_exec = client.get("/api/reports/executive")
    assert res_exec.status_code == 200
    html_text = res_exec.data.decode("utf-8")
    assert "CampusNet Operations" in html_text
    assert "Executive Report" in html_text
