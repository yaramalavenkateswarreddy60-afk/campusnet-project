"""
Unit Tests for services/metrics.py
Validates numeric safety, zero capacity handling, bounds, percentiles, and summary calculations.
"""

import math
import pytest
from services.metrics import (
    calculate_utilization,
    calculate_unmet_demand,
    calculate_satisfaction_rate,
    calculate_percentiles,
    compute_segment_status,
    aggregate_network_summary
)

def test_calculate_utilization_normal():
    # 200 allocated on 250 capacity = 80.0%
    assert calculate_utilization(200.0, 250.0) == 80.0
    # 50 allocated on 100 capacity = 50.0%
    assert calculate_utilization(50.0, 100.0) == 50.0


def test_calculate_utilization_zero_capacity():
    # Must safely return 0.0, never raise ZeroDivisionError, NaN, or Infinity
    assert calculate_utilization(100.0, 0.0) == 0.0
    assert calculate_utilization(0.0, 0.0) == 0.0
    assert calculate_utilization(100.0, -50.0) == 0.0
    assert not math.isnan(calculate_utilization(100.0, 0.0))
    assert not math.isinf(calculate_utilization(100.0, 0.0))


def test_calculate_utilization_negative_or_none():
    assert calculate_utilization(-10.0, 100.0) == 0.0
    assert calculate_utilization(None, 100.0) == 0.0
    assert calculate_utilization(50.0, None) == 0.0


def test_calculate_unmet_demand():
    # Demand 200, alloc 150 -> 50 unmet
    assert calculate_unmet_demand(200.0, 150.0) == 50.0
    # Demand 100, alloc 120 -> 0 unmet
    assert calculate_unmet_demand(100.0, 120.0) == 0.0
    # Demand 0, alloc 0 -> 0 unmet
    assert calculate_unmet_demand(0.0, 0.0) == 0.0
    # Negative demand or None
    assert calculate_unmet_demand(-10.0, 50.0) == 0.0
    assert calculate_unmet_demand(None, 50.0) == 0.0


def test_calculate_satisfaction_rate():
    # 150 / 200 = 75.0%
    assert calculate_satisfaction_rate(150.0, 200.0) == 75.0
    # 200 / 200 = 100.0%
    assert calculate_satisfaction_rate(200.0, 200.0) == 100.0
    # Over-satisfaction clamped to 100.0%
    assert calculate_satisfaction_rate(250.0, 200.0) == 100.0
    # Zero demand = 100.0% satisfied
    assert calculate_satisfaction_rate(0.0, 0.0) == 100.0
    assert calculate_satisfaction_rate(0.0, 100.0) == 0.0


def test_calculate_percentiles():
    samples = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    stats = calculate_percentiles(samples)
    assert stats["median"] == 55.0
    assert stats["p95"] == 100.0

    # Empty list
    empty_stats = calculate_percentiles([])
    assert empty_stats["median"] is None
    assert empty_stats["p95"] is None


def test_compute_segment_status():
    # Normal
    assert compute_segment_status(65.0, latency_ms=30.0, packet_loss_pct=0.2) == "NORMAL"
    # Warning on utilization threshold (exact boundary 70.0%)
    assert compute_segment_status(70.0, latency_ms=30.0, packet_loss_pct=0.2) == "WARNING"
    # Critical on utilization threshold (exact boundary 85.0%)
    assert compute_segment_status(85.0, latency_ms=30.0, packet_loss_pct=0.2) == "CRITICAL"
    # Critical on packet loss
    assert compute_segment_status(60.0, latency_ms=30.0, packet_loss_pct=3.5) == "CRITICAL"
    # Critical on latency
    assert compute_segment_status(60.0, latency_ms=120.0, packet_loss_pct=0.1) == "CRITICAL"


def test_aggregate_network_summary():
    segments = [
        {"capacity_mbps": 300.0, "demand_mbps": 280.0, "allocated_mbps": 240.0, "status": "WARNING", "latency_ms": 30.0, "packet_loss_pct": 1.2},
        {"capacity_mbps": 200.0, "demand_mbps": 100.0, "allocated_mbps": 100.0, "status": "NORMAL", "latency_ms": 15.0, "packet_loss_pct": 0.0}
    ]
    summary = aggregate_network_summary(segments, shared_capacity_mbps=500.0)
    assert summary["total_modeled_capacity_mbps"] == 500.0
    assert summary["total_demand_mbps"] == 380.0
    assert summary["total_allocated_mbps"] == 340.0
    assert summary["aggregate_utilization_pct"] == 68.0  # 340 / 500 * 100
    assert summary["total_unmet_demand_mbps"] == 40.0
    assert summary["status_counts"]["warning"] == 1
    assert summary["status_counts"]["normal"] == 1
