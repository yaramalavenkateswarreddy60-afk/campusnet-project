"""
Integration Tests for app.py REST API Endpoints
Verifies response structures, status codes, query filters, and data consistency.
"""

import os
import json
import io
import pytest
from app import create_app
from config import TestingConfig
from database.db import init_db

@pytest.fixture
def client(tmp_path):
    test_db = str(tmp_path / "test_api_campusnet.db")
    
    class RuntimeTestingConfig(TestingConfig):
        DATABASE_PATH = test_db
        TESTING = True

    app = create_app(RuntimeTestingConfig)
    with app.test_client() as client:
        # Authenticate client as admin for baseline API suite
        client.post("/api/auth/login", json={"username": "admin", "password": "Admin@CampusNet2026"})
        yield client


def test_index_route(client):
    res = client.get("/")
    assert res.status_code == 200
    # HTML response
    assert b"<!DOCTYPE html>" in res.data or b"<html" in res.data


def test_api_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "UP"
    assert data["database_status"] == "HEALTHY"
    assert data["segments_configured"] == 5


def test_api_summary(client):
    res = client.get("/api/summary")
    assert res.status_code == 200
    data = res.get_json()
    assert "total_modeled_capacity_mbps" in data
    assert "total_demand_mbps" in data
    assert "total_allocated_mbps" in data
    assert "aggregate_utilization_pct" in data
    assert "active_alerts" in data
    assert data["data_source_badge"] in ["SIMULATED", "IMPORTED"]


def test_api_segments(client):
    res = client.get("/api/segments")
    assert res.status_code == 200
    data = res.get_json()
    assert data["count"] == 5
    segment_names = [s["name"] for s in data["segments"]]
    assert "Computer Lab" in segment_names
    assert "Smart Classrooms" in segment_names
    assert "Library" in segment_names
    assert "Administration" in segment_names
    assert "Guest Wi-Fi" in segment_names


def test_api_alerts(client):
    res = client.get("/api/alerts")
    assert res.status_code == 200
    data = res.get_json()
    assert "count" in data
    assert isinstance(data["alerts"], list)
    if data["count"] > 0:
        alert = data["alerts"][0]
        assert "metric_name" in alert
        assert "severity" in alert
        assert "trigger_rule" in alert
        assert "explanation" in alert


def test_api_measurements(client):
    res = client.get("/api/measurements?limit=10")
    assert res.status_code == 200
    data = res.get_json()
    assert "measurements" in data
    assert len(data["measurements"]) <= 10


def test_api_optimize_preview_and_apply(client):
    # Preview mode
    payload = {
        "apply": False,
        "total_capacity_mbps": 800.0,
        "segments": [
            {"id": "seg_comp_lab", "demand_mbps": 250.0, "priority_weight": 3.0},
            {"id": "seg_smart_class", "demand_mbps": 220.0, "priority_weight": 4.0}
        ]
    }
    res = client.post("/api/optimize", json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data["applied"] is False
    assert "segments" in data
    assert data["total_allocated_mbps"] <= 800.0

    # Apply mode
    payload["apply"] = True
    res_apply = client.post("/api/optimize", json=payload)
    assert res_apply.status_code == 200
    data_apply = res_apply.get_json()
    assert data_apply["applied"] is True


def test_api_scenarios_and_experiment_run(client):
    res_scenarios = client.get("/api/scenarios")
    assert res_scenarios.status_code == 200
    scenarios = res_scenarios.get_json()["scenarios"]
    assert len(scenarios) >= 4

    # Run experiment
    exp_payload = {
        "scenario_id": "peak_classes",
        "notes": "Automated API verification run"
    }
    res_run = client.post("/api/experiments/run", json=exp_payload)
    assert res_run.status_code == 200
    exp_data = res_run.get_json()
    assert "experiment_id" in exp_data
    assert "baseline_segments" in exp_data
    assert "optimized_segments" in exp_data
    assert "comparison_summary" in exp_data

    # Check history endpoint
    res_hist = client.get("/api/history")
    assert res_hist.status_code == 200
    hist = res_hist.get_json()
    assert hist["count"] >= 1

    # Compare endpoint
    exp_id = exp_data["experiment_id"]
    res_comp = client.get(f"/api/experiments/{exp_id}/compare")
    assert res_comp.status_code == 200
    assert res_comp.get_json()["id"] == exp_id


def test_api_demo_reset(client):
    res = client.post("/api/demo/reset")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True

    # Segments should be reset to 5
    res_seg = client.get("/api/segments")
    assert res_seg.get_json()["count"] == 5


def test_api_export_csv(client):
    res = client.get("/api/export.csv")
    assert res.status_code == 200
    assert res.content_type.startswith("text/csv")
    csv_text = res.data.decode("utf-8")
    assert "Segment ID" in csv_text
    assert "Computer Lab" in csv_text
    assert "Smart Classrooms" in csv_text


def test_api_lab_preview(client):
    res = client.get("/api/lab/preview")
    assert res.status_code == 200
    data = res.get_json()
    assert "environment" in data
    assert "generated_commands" in data
    assert "tc qdisc" in data["generated_commands"]
