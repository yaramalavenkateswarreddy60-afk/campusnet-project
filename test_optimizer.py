"""
Unit Tests for services/optimizer.py
Verifies mathematical invariants:
 1. Non-negativity: allocation >= 0
 2. Demand bound: allocation <= demand
 3. Capacity invariant: sum(allocations) <= total_capacity
 4. Progressive filling & unused capacity redistribution
 5. Input validation & exception safety
"""

import pytest
from services.optimizer import BandwidthOptimizer, OptimizationError

@pytest.fixture
def standard_segments():
    return [
        {"id": "seg_lab", "name": "Computer Lab", "demand_mbps": 280.0, "priority_weight": 3.0, "min_guaranteed_mbps": 50.0},
        {"id": "seg_class", "name": "Smart Classrooms", "demand_mbps": 260.0, "priority_weight": 4.0, "min_guaranteed_mbps": 100.0},
        {"id": "seg_lib", "name": "Library", "demand_mbps": 110.0, "priority_weight": 2.0, "min_guaranteed_mbps": 20.0},
        {"id": "seg_admin", "name": "Administration", "demand_mbps": 45.0, "priority_weight": 5.0, "min_guaranteed_mbps": 40.0},
        {"id": "seg_guest", "name": "Guest Wi-Fi", "demand_mbps": 220.0, "priority_weight": 1.0, "min_guaranteed_mbps": 10.0}
    ]


def test_capacity_invariant_strictly_obeyed(standard_segments):
    total_cap = 800.0
    result = BandwidthOptimizer.optimize(total_cap, standard_segments)
    
    alloc_sum = sum(s["allocated_mbps"] for s in result["segments"])
    assert alloc_sum <= total_cap + 1e-4
    assert result["total_allocated_mbps"] <= total_cap + 1e-4


def test_demand_bound_invariant(standard_segments):
    total_cap = 800.0
    result = BandwidthOptimizer.optimize(total_cap, standard_segments)

    for seg in result["segments"]:
        assert seg["allocated_mbps"] <= seg["demand_mbps"] + 1e-4
        assert seg["allocated_mbps"] >= 0.0


def test_demand_below_total_capacity(standard_segments):
    # Total demand is 280 + 260 + 110 + 45 + 220 = 915.
    # Set capacity to 1000.0 (unconstrained)
    result = BandwidthOptimizer.optimize(1000.0, standard_segments)
    assert result["total_allocated_mbps"] == 915.0
    assert result["total_unmet_demand_mbps"] == 0.0

    for seg in result["segments"]:
        assert seg["allocated_mbps"] == seg["demand_mbps"]
        assert seg["satisfaction_pct"] == 100.0


def test_priority_weight_proportionality(standard_segments):
    # Under heavy congestion (total_cap = 500.0), Admin (weight 5) and Smart Class (weight 4)
    # should receive a significantly higher satisfaction percentage than Guest Wi-Fi (weight 1)
    result = BandwidthOptimizer.optimize(500.0, standard_segments)

    seg_by_id = {s["id"]: s for s in result["segments"]}
    admin_sat = seg_by_id["seg_admin"]["satisfaction_pct"]
    class_sat = seg_by_id["seg_class"]["satisfaction_pct"]
    guest_sat = seg_by_id["seg_guest"]["satisfaction_pct"]

    assert admin_sat > guest_sat
    assert class_sat > guest_sat
    # Guest Wi-Fi still receives some non-zero allocation to avoid silent starvation
    assert seg_by_id["seg_guest"]["allocated_mbps"] > 0.0


def test_zero_total_capacity(standard_segments):
    result = BandwidthOptimizer.optimize(0.0, standard_segments)
    assert result["total_allocated_mbps"] == 0.0
    for s in result["segments"]:
        assert s["allocated_mbps"] == 0.0
        assert s["unmet_demand_mbps"] == s["demand_mbps"]


def test_zero_demand():
    segments = [
        {"id": "s1", "name": "Active Seg", "demand_mbps": 100.0, "priority_weight": 2.0},
        {"id": "s2", "name": "Idle Seg", "demand_mbps": 0.0, "priority_weight": 3.0}
    ]
    result = BandwidthOptimizer.optimize(200.0, segments)
    s2 = next(s for s in result["segments"] if s["id"] == "s2")
    assert s2["allocated_mbps"] == 0.0
    assert s2["satisfaction_pct"] == 100.0


def test_unused_capacity_redistribution_work_conserving():
    # If one segment has low demand (e.g. 10 Mbps), its excess fair share should be absorbed
    # by another segment that has large unmet demand (e.g. 500 Mbps), rather than wasted.
    segments = [
        {"id": "low", "name": "Low Demand", "demand_mbps": 10.0, "priority_weight": 5.0},
        {"id": "high", "name": "High Demand", "demand_mbps": 500.0, "priority_weight": 1.0}
    ]
    # Total cap = 200.0.
    result = BandwidthOptimizer.optimize(200.0, segments)
    low_res = next(s for s in result["segments"] if s["id"] == "low")
    high_res = next(s for s in result["segments"] if s["id"] == "high")

    # Low demand gets 10 Mbps (capped at demand)
    assert low_res["allocated_mbps"] == 10.0
    # High demand absorbs remaining 190 Mbps!
    assert high_res["allocated_mbps"] == 190.0
    assert result["total_allocated_mbps"] == 200.0


def test_input_validation_errors(standard_segments):
    # Negative capacity
    with pytest.raises(OptimizationError):
        BandwidthOptimizer.optimize(-50.0, standard_segments)

    # Empty segments
    with pytest.raises(OptimizationError):
        BandwidthOptimizer.optimize(500.0, [])

    # Negative demand
    bad_segments = [{"id": "bad", "name": "Bad", "demand_mbps": -10.0, "priority_weight": 1.0}]
    with pytest.raises(OptimizationError):
        BandwidthOptimizer.optimize(500.0, bad_segments)

    # Non-positive weight
    bad_weight_segments = [{"id": "bad", "name": "Bad", "demand_mbps": 50.0, "priority_weight": 0.0}]
    with pytest.raises(OptimizationError):
        BandwidthOptimizer.optimize(500.0, bad_weight_segments)
