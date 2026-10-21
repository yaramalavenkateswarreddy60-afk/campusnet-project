"""
Unit Tests for services/congestion.py
Validates configurable demonstration threshold boundaries, severity levels,
multi-metric evaluations, persistent vs single-sample alerts, and recommendations.
"""

import pytest
from services.congestion import CongestionDetector

@pytest.fixture
def detector():
    return CongestionDetector(
        warn_util=70.0,
        crit_util=85.0,
        warn_lat=50.0,
        crit_lat=100.0,
        warn_loss=1.0,
        crit_loss=3.0
    )


def test_detector_below_warning_normal(detector):
    seg = {
        "id": "seg_test",
        "name": "Test Segment",
        "utilization_pct": 69.9,
        "latency_ms": 45.0,
        "packet_loss_pct": 0.5,
        "data_source": "SIMULATED"
    }
    alerts = detector.evaluate_segment(seg)
    assert len(alerts) == 0


def test_detector_threshold_boundaries_warning(detector):
    # Exactly on boundary 70.0%
    seg = {
        "id": "seg_test",
        "name": "Test Segment",
        "utilization_pct": 70.0,
        "data_source": "SIMULATED"
    }
    alerts = detector.evaluate_segment(seg)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "WARNING"
    assert alerts[0]["metric_name"] == "utilization"
    assert alerts[0]["observed_value"] == 70.0
    assert alerts[0]["threshold_value"] == 70.0
    assert "Utilization >= 70.0%" in alerts[0]["trigger_rule"]
    assert "reallocate" in alerts[0]["recommended_action"].lower() or "monitor" in alerts[0]["recommended_action"].lower()


def test_detector_threshold_boundaries_critical(detector):
    # Exactly on boundary 85.0%
    seg = {
        "id": "seg_test",
        "name": "Test Segment",
        "utilization_pct": 85.0,
        "data_source": "SIMULATED"
    }
    alerts = detector.evaluate_segment(seg)
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "CRITICAL"
    assert alerts[0]["observed_value"] == 85.0
    assert alerts[0]["threshold_value"] == 85.0
    assert alerts[0]["is_persistent"] == 0


def test_detector_latency_and_loss_thresholds(detector):
    seg = {
        "id": "seg_test",
        "name": "Test Segment",
        "utilization_pct": 50.0,
        "latency_ms": 110.0,       # Critical latency (>100ms)
        "packet_loss_pct": 1.5,    # Warning loss (>1.0%)
        "data_source": "SIMULATED"
    }
    alerts = detector.evaluate_segment(seg)
    assert len(alerts) == 2

    metrics_triggered = {a["metric_name"]: a["severity"] for a in alerts}
    assert metrics_triggered["latency"] == "CRITICAL"
    assert metrics_triggered["packet_loss"] == "WARNING"


def test_detector_handles_missing_fields(detector):
    # Only utilization present, latency and loss are None
    seg = {
        "id": "seg_test",
        "name": "Test Segment",
        "utilization_pct": 75.0,
        "latency_ms": None,
        "packet_loss_pct": None
    }
    alerts = detector.evaluate_segment(seg)
    assert len(alerts) == 1
    assert alerts[0]["metric_name"] == "utilization"


def test_detector_distinguishes_persistent_vs_transient(detector):
    seg = {
        "id": "seg_test",
        "name": "Test Segment",
        "utilization_pct": 90.0
    }
    # Single sample
    single_alerts = detector.evaluate_segment(seg, historical_consecutive_triggers=0)
    assert single_alerts[0]["is_persistent"] == 0

    # Persistent (historical >= 1)
    persistent_alerts = detector.evaluate_segment(seg, historical_consecutive_triggers=2)
    assert persistent_alerts[0]["is_persistent"] == 1
