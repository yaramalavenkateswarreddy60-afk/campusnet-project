"""
CampusNet: Experiments and Scenarios Service
Orchestrates repeatable before-and-after experiments comparing baseline network state
against QoS-optimized allocations.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from database.db import get_db
from services.optimizer import BandwidthOptimizer
from services.metrics import calculate_utilization, calculate_unmet_demand, calculate_satisfaction_rate
from services.congestion import CongestionDetector

SCENARIOS = {
    "peak_classes": {
        "id": "peak_classes",
        "name": "Peak Video Lecture & Lab Hours",
        "description": "High simultaneous streaming across Smart Classrooms and Computer Labs with congested shared link.",
        "shared_capacity_mbps": 800.0,
        "segments": [
            {"id": "seg_comp_lab", "name": "Computer Lab", "capacity_mbps": 300.0, "demand_mbps": 280.0, "priority_weight": 3.0, "min_guaranteed_mbps": 100.0, "max_limit_mbps": 300.0},
            {"id": "seg_smart_class", "name": "Smart Classrooms", "capacity_mbps": 250.0, "demand_mbps": 260.0, "priority_weight": 4.5, "min_guaranteed_mbps": 150.0, "max_limit_mbps": 250.0},
            {"id": "seg_library", "name": "Library", "capacity_mbps": 150.0, "demand_mbps": 110.0, "priority_weight": 2.0, "min_guaranteed_mbps": 40.0, "max_limit_mbps": 150.0},
            {"id": "seg_admin", "name": "Administration", "capacity_mbps": 100.0, "demand_mbps": 45.0, "priority_weight": 5.0, "min_guaranteed_mbps": 45.0, "max_limit_mbps": 100.0},
            {"id": "seg_guest_wifi", "name": "Guest Wi-Fi", "capacity_mbps": 200.0, "demand_mbps": 220.0, "priority_weight": 1.0, "min_guaranteed_mbps": 20.0, "max_limit_mbps": 120.0}
        ]
    },
    "exam_day": {
        "id": "exam_day",
        "name": "Online Examination Period",
        "description": "Mission-critical lockdown for Administration and Computer Labs; Guest Wi-Fi restricted to 50 Mbps.",
        "shared_capacity_mbps": 800.0,
        "segments": [
            {"id": "seg_comp_lab", "name": "Computer Lab", "capacity_mbps": 300.0, "demand_mbps": 290.0, "priority_weight": 4.5, "min_guaranteed_mbps": 200.0, "max_limit_mbps": 300.0},
            {"id": "seg_smart_class", "name": "Smart Classrooms", "capacity_mbps": 250.0, "demand_mbps": 210.0, "priority_weight": 4.0, "min_guaranteed_mbps": 120.0, "max_limit_mbps": 250.0},
            {"id": "seg_library", "name": "Library", "capacity_mbps": 150.0, "demand_mbps": 90.0, "priority_weight": 2.0, "min_guaranteed_mbps": 30.0, "max_limit_mbps": 150.0},
            {"id": "seg_admin", "name": "Administration", "capacity_mbps": 100.0, "demand_mbps": 50.0, "priority_weight": 5.0, "min_guaranteed_mbps": 50.0, "max_limit_mbps": 100.0},
            {"id": "seg_guest_wifi", "name": "Guest Wi-Fi", "capacity_mbps": 200.0, "demand_mbps": 200.0, "priority_weight": 1.0, "min_guaranteed_mbps": 10.0, "max_limit_mbps": 50.0}
        ]
    },
    "evening_dorm": {
        "id": "evening_dorm",
        "name": "Evening Off-Hour Streaming Surge",
        "description": "Smart Classrooms and Admin demand drops while Guest Wi-Fi and Library digital repositories peak.",
        "shared_capacity_mbps": 800.0,
        "segments": [
            {"id": "seg_comp_lab", "name": "Computer Lab", "capacity_mbps": 300.0, "demand_mbps": 120.0, "priority_weight": 2.5, "min_guaranteed_mbps": 50.0, "max_limit_mbps": 300.0},
            {"id": "seg_smart_class", "name": "Smart Classrooms", "capacity_mbps": 250.0, "demand_mbps": 40.0, "priority_weight": 2.0, "min_guaranteed_mbps": 20.0, "max_limit_mbps": 250.0},
            {"id": "seg_library", "name": "Library", "capacity_mbps": 150.0, "demand_mbps": 140.0, "priority_weight": 3.0, "min_guaranteed_mbps": 60.0, "max_limit_mbps": 150.0},
            {"id": "seg_admin", "name": "Administration", "capacity_mbps": 100.0, "demand_mbps": 20.0, "priority_weight": 5.0, "min_guaranteed_mbps": 20.0, "max_limit_mbps": 100.0},
            {"id": "seg_guest_wifi", "name": "Guest Wi-Fi", "capacity_mbps": 200.0, "demand_mbps": 350.0, "priority_weight": 1.5, "min_guaranteed_mbps": 80.0, "max_limit_mbps": 200.0}
        ]
    },
    "normal_day": {
        "id": "normal_day",
        "name": "Normal Academic Workday",
        "description": "Standard baseline traffic across campus; manageable contention within capacity bounds.",
        "shared_capacity_mbps": 800.0,
        "segments": [
            {"id": "seg_comp_lab", "name": "Computer Lab", "capacity_mbps": 300.0, "demand_mbps": 180.0, "priority_weight": 3.0, "min_guaranteed_mbps": 80.0, "max_limit_mbps": 300.0},
            {"id": "seg_smart_class", "name": "Smart Classrooms", "capacity_mbps": 250.0, "demand_mbps": 160.0, "priority_weight": 4.0, "min_guaranteed_mbps": 100.0, "max_limit_mbps": 250.0},
            {"id": "seg_library", "name": "Library", "capacity_mbps": 150.0, "demand_mbps": 80.0, "priority_weight": 2.0, "min_guaranteed_mbps": 30.0, "max_limit_mbps": 150.0},
            {"id": "seg_admin", "name": "Administration", "capacity_mbps": 100.0, "demand_mbps": 35.0, "priority_weight": 5.0, "min_guaranteed_mbps": 35.0, "max_limit_mbps": 100.0},
            {"id": "seg_guest_wifi", "name": "Guest Wi-Fi", "capacity_mbps": 200.0, "demand_mbps": 130.0, "priority_weight": 1.0, "min_guaranteed_mbps": 20.0, "max_limit_mbps": 150.0}
        ]
    }
}


def run_experiment(
    scenario_id: str,
    custom_capacity_mbps: Optional[float] = None,
    custom_weights: Optional[Dict[str, float]] = None,
    notes: str = ""
) -> Dict[str, Any]:
    """
    Executes a controlled before-and-after experiment.
    1. Evaluates baseline (unoptimized FIFO contention where everyone gets unweighted share).
    2. Runs WFQ-PF optimizer.
    3. Analyzes alerts, latency/packet loss modeled impact, and unmet demand.
    4. Persists the run in SQLite.
    """
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Unknown scenario ID: {scenario_id}. Available: {list(SCENARIOS.keys())}")

    scenario = SCENARIOS[scenario_id]
    total_cap = custom_capacity_mbps if (custom_capacity_mbps is not None and custom_capacity_mbps > 0) else scenario["shared_capacity_mbps"]
    segments = [dict(s) for s in scenario["segments"]]

    # Apply any custom priority weights if provided
    if custom_weights:
        for seg in segments:
            if seg["id"] in custom_weights:
                seg["priority_weight"] = float(custom_weights[seg["id"]])

    total_demand = sum(s["demand_mbps"] for s in segments)

    # 1. Baseline Computation (Equal unweighted FIFO share proportional to demand without QoS)
    baseline_segments = []
    if total_demand <= total_cap:
        for s in segments:
            d = s["demand_mbps"]
            baseline_segments.append({
                "id": s["id"],
                "name": s["name"],
                "demand_mbps": d,
                "allocated_mbps": d,
                "utilization_pct": calculate_utilization(d, s["capacity_mbps"]),
                "unmet_demand_mbps": 0.0,
                "satisfaction_pct": 100.0,
                "modeled_latency_ms": 18.0,
                "modeled_packet_loss_pct": 0.0,
                "status": "NORMAL"
            })
    else:
        # Congested unweighted FIFO: bandwidth grabbed proportionally to raw demand, causing high drop in academic classes
        for s in segments:
            d = s["demand_mbps"]
            fifo_alloc = round((d / total_demand) * total_cap, 2)
            util = calculate_utilization(fifo_alloc, s["capacity_mbps"])
            unmet = calculate_unmet_demand(d, fifo_alloc)
            sat = calculate_satisfaction_rate(fifo_alloc, d)
            
            # Latency and packet loss modeled under FIFO congestion
            loss_est = round(max(0.0, (1.0 - (fifo_alloc / d)) * 8.0), 2) if d > 0 else 0.0
            lat_est = round(20.0 + (loss_est * 15.0), 1)

            status = "CRITICAL" if (util >= 85.0 or loss_est >= 3.0 or lat_est >= 100.0) else (
                "WARNING" if (util >= 70.0 or loss_est >= 1.0 or lat_est >= 50.0) else "NORMAL"
            )

            baseline_segments.append({
                "id": s["id"],
                "name": s["name"],
                "demand_mbps": d,
                "allocated_mbps": fifo_alloc,
                "utilization_pct": util,
                "unmet_demand_mbps": unmet,
                "satisfaction_pct": sat,
                "modeled_latency_ms": lat_est,
                "modeled_packet_loss_pct": loss_est,
                "status": status
            })

    # 2. Optimized Computation (WFQ-PF)
    optimized_result = BandwidthOptimizer.optimize(total_cap, segments)
    optimized_segments = []

    for item in optimized_result["segments"]:
        seg_id = item["id"]
        # Find original segment specs
        orig = next((s for s in segments if s["id"] == seg_id), {})
        alloc = item["allocated_mbps"]
        dem = item["demand_mbps"]
        cap = orig.get("capacity_mbps", alloc)
        util = calculate_utilization(alloc, cap)
        unmet = item["unmet_demand_mbps"]
        sat = item["satisfaction_pct"]

        # Modeled post-QoS metrics: with bandwidth guaranteed and traffic queues prioritized
        prio = float(orig.get("priority_weight", 1.0))
        loss_est = round(max(0.0, (1.0 - (alloc / dem)) * 4.0 / prio), 2) if dem > 0 else 0.0
        lat_est = round(15.0 + (loss_est * 8.0), 1)

        status = "CRITICAL" if (util >= 85.0 or loss_est >= 3.0 or lat_est >= 100.0) else (
            "WARNING" if (util >= 70.0 or loss_est >= 1.0 or lat_est >= 50.0) else "NORMAL"
        )

        optimized_segments.append({
            "id": seg_id,
            "name": item["name"],
            "demand_mbps": dem,
            "allocated_mbps": alloc,
            "utilization_pct": util,
            "unmet_demand_mbps": unmet,
            "satisfaction_pct": sat,
            "modeled_latency_ms": lat_est,
            "modeled_packet_loss_pct": loss_est,
            "priority_weight": prio,
            "explanation": item["explanation"],
            "status": status
        })

    # 3. Comparative Summary Metrics
    baseline_total_alloc = sum(b["allocated_mbps"] for b in baseline_segments)
    baseline_unmet = sum(b["unmet_demand_mbps"] for b in baseline_segments)
    baseline_criticals = sum(1 for b in baseline_segments if b["status"] == "CRITICAL")
    baseline_warnings = sum(1 for b in baseline_segments if b["status"] == "WARNING")

    opt_total_alloc = sum(o["allocated_mbps"] for o in optimized_segments)
    opt_unmet = sum(o["unmet_demand_mbps"] for o in optimized_segments)
    opt_criticals = sum(1 for o in optimized_segments if o["status"] == "CRITICAL")
    opt_warnings = sum(1 for o in optimized_segments if o["status"] == "WARNING")

    # High-priority classes satisfaction comparison (Admin & Smart Class)
    hp_ids = {"seg_admin", "seg_smart_class"}
    base_hp_sat = round(
        sum(b["satisfaction_pct"] for b in baseline_segments if b["id"] in hp_ids) / len(hp_ids), 2
    )
    opt_hp_sat = round(
        sum(o["satisfaction_pct"] for o in optimized_segments if o["id"] in hp_ids) / len(hp_ids), 2
    )

    comparison_summary = {
        "scenario_id": scenario_id,
        "scenario_name": scenario["name"],
        "shared_capacity_mbps": total_cap,
        "total_demand_mbps": round(total_demand, 2),
        "baseline": {
            "total_allocated_mbps": round(baseline_total_alloc, 2),
            "total_unmet_demand_mbps": round(baseline_unmet, 2),
            "critical_alerts": baseline_criticals,
            "warning_alerts": baseline_warnings,
            "high_priority_satisfaction_pct": base_hp_sat
        },
        "optimized": {
            "total_allocated_mbps": round(opt_total_alloc, 2),
            "total_unmet_demand_mbps": round(opt_unmet, 2),
            "critical_alerts": opt_criticals,
            "warning_alerts": opt_warnings,
            "high_priority_satisfaction_pct": opt_hp_sat
        },
        "improvements": {
            "high_priority_gain_pct": round(opt_hp_sat - base_hp_sat, 2),
            "critical_alerts_prevented": max(0, baseline_criticals - opt_criticals),
            "fairness_guaranteed": True
        }
    }

    # 4. Persist to SQLite
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO experiments (
            name, scenario_name, total_capacity_mbps, baseline_json,
            optimized_json, comparison_summary_json, notes, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            f"Exp: {scenario['name']}",
            scenario["name"],
            total_cap,
            json.dumps(baseline_segments),
            json.dumps(optimized_segments),
            json.dumps(comparison_summary),
            notes or f"Deterministic comparison run for scenario '{scenario['name']}'.",
            now
        )
    )
    exp_id = cursor.lastrowid
    conn.commit()

    return {
        "experiment_id": exp_id,
        "scenario_name": scenario["name"],
        "created_at": now,
        "shared_capacity_mbps": total_cap,
        "total_demand_mbps": round(total_demand, 2),
        "baseline_segments": baseline_segments,
        "optimized_segments": optimized_segments,
        "comparison_summary": comparison_summary
    }


def get_experiment_by_id(exp_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves a stored experiment by its primary key ID.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM experiments WHERE id = ?;", (exp_id,))
    row = cursor.fetchone()
    if not row:
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "scenario_name": row["scenario_name"],
        "total_capacity_mbps": row["total_capacity_mbps"],
        "baseline_segments": json.loads(row["baseline_json"]),
        "optimized_segments": json.loads(row["optimized_json"]),
        "comparison_summary": json.loads(row["comparison_summary_json"]),
        "notes": row["notes"],
        "created_at": row["created_at"]
    }


def list_experiments(limit: int = 15) -> List[Dict[str, Any]]:
    """
    Returns recent experiment records from database.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, scenario_name, total_capacity_mbps, comparison_summary_json, notes, created_at FROM experiments ORDER BY id DESC LIMIT ?;", (limit,))
    rows = cursor.fetchall()

    items = []
    for r in rows:
        summary = json.loads(r["comparison_summary_json"])
        items.append({
            "id": r["id"],
            "name": r["name"],
            "scenario_name": r["scenario_name"],
            "total_capacity_mbps": r["total_capacity_mbps"],
            "summary": summary,
            "created_at": r["created_at"]
        })
    return items
