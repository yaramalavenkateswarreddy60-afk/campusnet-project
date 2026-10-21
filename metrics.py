"""
CampusNet: Network Metrics Service
Provides mathematically sound, safe metric computations for network operations.
Enforces strict distinction between:
 - Capacity: configured maximum rate
 - Demand: requested rate
 - Allocation: rate assigned by the model or QoS policy
 - Throughput: rate actually delivered and measured
"""

import math
from typing import List, Dict, Any, Optional

def calculate_utilization(allocated_mbps: float, capacity_mbps: float) -> float:
    """
    Calculates utilization percentage: (allocated_mbps / capacity_mbps) * 100.
    Handles zero capacity safely. Never outputs NaN or Infinity.
    """
    if capacity_mbps is None or capacity_mbps <= 0.0:
        return 0.0
    
    if allocated_mbps is None or allocated_mbps <= 0.0:
        return 0.0

    util = (allocated_mbps / capacity_mbps) * 100.0
    if math.isnan(util) or math.isinf(util):
        return 0.0
    return round(util, 2)


def calculate_unmet_demand(demand_mbps: float, allocated_mbps: float) -> float:
    """
    Calculates unmet demand: max(0.0, demand - allocation).
    """
    if demand_mbps is None or demand_mbps <= 0.0:
        return 0.0
    alloc = allocated_mbps if (allocated_mbps is not None and allocated_mbps >= 0.0) else 0.0
    return round(max(0.0, demand_mbps - alloc), 2)


def calculate_satisfaction_rate(allocated_mbps: float, demand_mbps: float) -> float:
    """
    Calculates percentage of demand satisfied: (allocation / demand) * 100.
    Returns 100.0 if demand is 0.
    """
    if demand_mbps is None or demand_mbps <= 0.0:
        return 100.0
    if allocated_mbps is None or allocated_mbps <= 0.0:
        return 0.0
    return round(min(100.0, (allocated_mbps / demand_mbps) * 100.0), 2)


def calculate_percentiles(values: List[float]) -> Dict[str, Optional[float]]:
    """
    Calculates median (50th percentile) and 95th percentile from a list of numerical samples.
    Returns None values if the input list is empty.
    """
    valid_nums = [v for v in values if v is not None and not math.isnan(v)]
    if not valid_nums:
        return {"median": None, "p95": None}

    sorted_vals = sorted(valid_nums)
    n = len(sorted_vals)

    # Median
    mid = n // 2
    if n % 2 == 1:
        median_val = sorted_vals[mid]
    else:
        median_val = (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0

    # 95th percentile (nearest rank method)
    p95_idx = int(math.ceil(0.95 * n)) - 1
    p95_idx = max(0, min(n - 1, p95_idx))
    p95_val = sorted_vals[p95_idx]

    return {
        "median": round(median_val, 2),
        "p95": round(p95_val, 2)
    }


def compute_segment_status(
    utilization_pct: float,
    latency_ms: Optional[float] = None,
    packet_loss_pct: Optional[float] = None,
    warn_util: float = 70.0,
    crit_util: float = 85.0,
    warn_lat: float = 50.0,
    crit_lat: float = 100.0,
    warn_loss: float = 1.0,
    crit_loss: float = 3.0
) -> str:
    """
    Determines segment health status: 'NORMAL', 'WARNING', or 'CRITICAL'.
    Evaluates utilization, and optionally latency and packet loss when available.
    """
    # Check critical triggers first
    if utilization_pct >= crit_util:
        return "CRITICAL"
    if packet_loss_pct is not None and packet_loss_pct >= crit_loss:
        return "CRITICAL"
    if latency_ms is not None and latency_ms >= crit_lat:
        return "CRITICAL"

    # Check warning triggers
    if utilization_pct >= warn_util:
        return "WARNING"
    if packet_loss_pct is not None and packet_loss_pct >= warn_loss:
        return "WARNING"
    if latency_ms is not None and latency_ms >= warn_lat:
        return "WARNING"

    return "NORMAL"


def aggregate_network_summary(segments: List[Dict[str, Any]], shared_capacity_mbps: Optional[float] = None) -> Dict[str, Any]:
    """
    Aggregates overall campus network metrics across all segments.
    Distinguishes configured capacity, total demand, total allocated, and measured throughput.
    """
    total_capacity = 0.0
    total_demand = 0.0
    total_allocated = 0.0
    total_measured_throughput = 0.0
    has_throughput_measurements = False

    normal_count = 0
    warning_count = 0
    critical_count = 0

    latencies = []
    packet_losses = []

    for seg in segments:
        cap = float(seg.get("capacity_mbps") or 0.0)
        dem = float(seg.get("demand_mbps") or 0.0)
        alloc = float(seg.get("allocated_mbps") or 0.0)
        status = seg.get("status", "NORMAL")

        total_capacity += cap
        total_demand += dem
        total_allocated += alloc

        tp = seg.get("throughput_mbps")
        if tp is not None:
            total_measured_throughput += float(tp)
            has_throughput_measurements = True

        lat = seg.get("latency_ms")
        if lat is not None:
            latencies.append(float(lat))

        loss = seg.get("packet_loss_pct")
        if loss is not None:
            packet_losses.append(float(loss))

        if status == "CRITICAL":
            critical_count += 1
        elif status == "WARNING":
            warning_count += 1
        else:
            normal_count += 1

    effective_capacity = shared_capacity_mbps if (shared_capacity_mbps is not None and shared_capacity_mbps > 0) else total_capacity
    aggregate_utilization = calculate_utilization(total_allocated, effective_capacity)
    total_unmet = calculate_unmet_demand(total_demand, total_allocated)
    satisfaction = calculate_satisfaction_rate(total_allocated, total_demand)

    latency_stats = calculate_percentiles(latencies)
    loss_stats = calculate_percentiles(packet_losses)

    return {
        "total_modeled_capacity_mbps": round(effective_capacity, 2),
        "total_segment_capacity_sum_mbps": round(total_capacity, 2),
        "total_demand_mbps": round(total_demand, 2),
        "total_allocated_mbps": round(total_allocated, 2),
        "total_measured_throughput_mbps": round(total_measured_throughput, 2) if has_throughput_measurements else None,
        "aggregate_utilization_pct": aggregate_utilization,
        "total_unmet_demand_mbps": total_unmet,
        "satisfaction_rate_pct": satisfaction,
        "status_counts": {
            "normal": normal_count,
            "warning": warning_count,
            "critical": critical_count,
            "total_alerts": warning_count + critical_count
        },
        "latency_summary_ms": latency_stats,
        "packet_loss_summary_pct": loss_stats
    }
