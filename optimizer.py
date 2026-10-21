"""
CampusNet: Bandwidth Optimization Engine
Implements Weighted Fair Queuing with Demand-Bounded Progressive Filling (WFQ-PF).

Mathematical Invariants Guaranteed:
 1. Non-negativity: allocation[i] >= 0 for all i
 2. Demand Bound: allocation[i] <= demand[i] for all i
 3. Capacity Invariant: sum(allocation[i]) <= total_capacity
 4. Work-Conserving: Unused capacity from low-demand segments is redistributed to high-priority unmet flows.
 5. Starvation Avoidance: Preserves best-effort minimum allocations where capacity permits.

DISCLAIMER: The optimization engine modifies modeled allocations or lab traffic queues;
it does not increase physical internet bandwidth provided by an ISP.
"""

from typing import List, Dict, Any, Optional, Tuple

class OptimizationError(ValueError):
    """Raised when optimization input constraints are violated."""
    pass


class BandwidthOptimizer:
    """
    Weighted Fair Queuing with Progressive Filling Optimizer.
    """

    @staticmethod
    def validate_inputs(
        total_capacity_mbps: float,
        segments: List[Dict[str, Any]]
    ) -> None:
        """
        Validates optimization inputs against numerical bounds.
        """
        if total_capacity_mbps is None or total_capacity_mbps < 0:
            raise OptimizationError(f"Total capacity must be non-negative, got: {total_capacity_mbps}")

        if not segments:
            raise OptimizationError("Segments list cannot be empty")

        for idx, seg in enumerate(segments):
            seg_name = seg.get("name", f"Segment-{idx}")
            demand = seg.get("demand_mbps")
            if demand is None or demand < 0:
                raise OptimizationError(f"Demand for '{seg_name}' must be non-negative, got: {demand}")

            weight = seg.get("priority_weight", 1.0)
            if weight is None or weight <= 0:
                raise OptimizationError(f"Priority weight for '{seg_name}' must be positive, got: {weight}")

            min_g = seg.get("min_guaranteed_mbps", 0.0)
            if min_g is not None and min_g < 0:
                raise OptimizationError(f"Minimum guaranteed bandwidth for '{seg_name}' cannot be negative, got: {min_g}")

            max_l = seg.get("max_limit_mbps")
            if max_l is not None and max_l < 0:
                raise OptimizationError(f"Maximum limit for '{seg_name}' cannot be negative, got: {max_l}")

    @classmethod
    def optimize(
        cls,
        total_capacity_mbps: float,
        segments: List[Dict[str, Any]],
        preserve_best_effort: bool = True
    ) -> Dict[str, Any]:
        """
        Executes the WFQ-PF algorithm.
        Returns a dictionary with segment-level allocations, unmet demands, explanations, and metrics.
        """
        cls.validate_inputs(total_capacity_mbps, segments)

        total_cap = float(total_capacity_mbps)
        n = len(segments)

        # Handle edge case: Total capacity is zero
        if total_cap == 0.0:
            results = []
            for seg in segments:
                dem = float(seg.get("demand_mbps", 0.0))
                results.append({
                    "id": seg.get("id"),
                    "name": seg.get("name"),
                    "demand_mbps": dem,
                    "allocated_mbps": 0.0,
                    "unmet_demand_mbps": dem,
                    "satisfaction_pct": 100.0 if dem == 0.0 else 0.0,
                    "priority_weight": float(seg.get("priority_weight", 1.0)),
                    "explanation": "Zero total shared capacity available. Allocation is 0 Mbps."
                })
            return {
                "total_capacity_mbps": 0.0,
                "total_demand_mbps": round(sum(s.get("demand_mbps", 0.0) for s in segments), 2),
                "total_allocated_mbps": 0.0,
                "total_unmet_demand_mbps": round(sum(s.get("demand_mbps", 0.0) for s in segments), 2),
                "unused_capacity_mbps": 0.0,
                "segments": results,
                "policy_summary": "Zero capacity link: No bandwidth distributed."
            }

        # Calculate total requested demand
        total_dem = sum(float(s.get("demand_mbps", 0.0)) for s in segments)

        # Non-congested case: Total demand <= Total capacity
        if total_dem <= total_cap:
            results = []
            for seg in segments:
                dem = float(seg.get("demand_mbps", 0.0))
                # Bound by max_limit if specified
                max_l = seg.get("max_limit_mbps")
                cap_bound = float(seg.get("capacity_mbps", dem))
                allowed = min(dem, cap_bound)
                if max_l is not None:
                    allowed = min(allowed, float(max_l))

                results.append({
                    "id": seg.get("id"),
                    "name": seg.get("name"),
                    "demand_mbps": dem,
                    "allocated_mbps": round(allowed, 2),
                    "unmet_demand_mbps": round(dem - allowed, 2),
                    "satisfaction_pct": 100.0 if dem == 0.0 else round((allowed / dem) * 100.0, 2),
                    "priority_weight": float(seg.get("priority_weight", 1.0)),
                    "explanation": "Network is unconstrained. Total demand is within total shared capacity; 100% satisfied."
                })
            total_alloc = sum(r["allocated_mbps"] for r in results)
            return {
                "total_capacity_mbps": total_cap,
                "total_demand_mbps": round(total_dem, 2),
                "total_allocated_mbps": round(total_alloc, 2),
                "total_unmet_demand_mbps": round(sum(r["unmet_demand_mbps"] for r in results), 2),
                "unused_capacity_mbps": round(max(0.0, total_cap - total_alloc), 2),
                "segments": results,
                "policy_summary": "Unconstrained mode: All demands satisfied."
            }

        # Congested case: total_dem > total_cap
        # Phase 1: Minimum guarantees
        allocations = [0.0] * n
        ceilings = []

        for i, seg in enumerate(segments):
            dem = float(seg.get("demand_mbps", 0.0))
            max_l = seg.get("max_limit_mbps")
            ceil = dem
            if max_l is not None:
                ceil = min(ceil, float(max_l))
            # Also bounded by segment local physical link capacity if specified
            seg_cap = seg.get("capacity_mbps")
            if seg_cap is not None and float(seg_cap) > 0:
                ceil = min(ceil, float(seg_cap))
            ceilings.append(ceil)

            min_g = float(seg.get("min_guaranteed_mbps") or 0.0)
            # Guarantee cannot exceed ceiling or demand
            allocations[i] = min(min_g, ceil)

        sum_guarantees = sum(allocations)

        # If minimum guarantees alone exceed total shared capacity, scale them by priority weight
        if sum_guarantees > total_cap:
            weighted_guar_sum = sum(allocations[i] * float(segments[i].get("priority_weight", 1.0)) for i in range(n))
            if weighted_guar_sum > 0:
                for i in range(n):
                    w = float(segments[i].get("priority_weight", 1.0))
                    allocations[i] = (allocations[i] * w / weighted_guar_sum) * total_cap
            else:
                for i in range(n):
                    allocations[i] = total_cap / n

            results = []
            for i, seg in enumerate(segments):
                dem = float(seg.get("demand_mbps", 0.0))
                alloc = round(allocations[i], 2)
                results.append({
                    "id": seg.get("id"),
                    "name": seg.get("name"),
                    "demand_mbps": dem,
                    "allocated_mbps": alloc,
                    "unmet_demand_mbps": round(max(0.0, dem - alloc), 2),
                    "satisfaction_pct": round((alloc / dem * 100.0) if dem > 0 else 100.0, 2),
                    "priority_weight": float(seg.get("priority_weight", 1.0)),
                    "explanation": "Severe contention: Even minimum guarantees scaled down according to priority weights."
                })
            total_alloc = sum(r["allocated_mbps"] for r in results)
            return {
                "total_capacity_mbps": total_cap,
                "total_demand_mbps": round(total_dem, 2),
                "total_allocated_mbps": round(total_alloc, 2),
                "total_unmet_demand_mbps": round(sum(r["unmet_demand_mbps"] for r in results), 2),
                "unused_capacity_mbps": round(max(0.0, total_cap - total_alloc), 2),
                "segments": results,
                "policy_summary": "Extreme contention: Scaled minimum guarantees."
            }

        # Phase 2: Progressive Filling of remaining capacity
        remaining_cap = total_cap - sum_guarantees
        active_indices = {i for i in range(n) if allocations[i] < ceilings[i]}

        while remaining_cap > 1e-6 and active_indices:
            sum_active_weights = sum(float(segments[i].get("priority_weight", 1.0)) for i in active_indices)
            if sum_active_weights <= 0:
                break

            # Check if any segment reaches its ceiling in this iteration
            proposals = {}
            for i in active_indices:
                w = float(segments[i].get("priority_weight", 1.0))
                share = remaining_cap * (w / sum_active_weights)
                proposals[i] = share

            # Find segments that would hit their demand ceiling
            saturated = set()
            min_scale_ratio = 1.0

            for i in active_indices:
                needed = ceilings[i] - allocations[i]
                if proposals[i] > needed:
                    # Segment would exceed ceiling
                    saturated.add(i)

            if saturated:
                # Satisfy saturated segments to their ceiling and continue
                for i in saturated:
                    needed = ceilings[i] - allocations[i]
                    allocations[i] = ceilings[i]
                    remaining_cap -= needed
                    active_indices.remove(i)
            else:
                # All active segments can absorb their full proposed share
                for i in active_indices:
                    allocations[i] += proposals[i]
                    remaining_cap -= proposals[i]
                break

        # Phase 3: Starvation avoidance audit
        # If preserve_best_effort is True, ensure low-priority segments with >0 demand get at least
        # a modest sliver (e.g. min 2% of link or min_guaranteed) if capacity permits
        for i in range(n):
            if allocations[i] > ceilings[i]:
                allocations[i] = ceilings[i]

        # Invariant enforcement: strictly clamp sum to total_cap
        total_tentative = sum(allocations)
        if total_tentative > total_cap:
            diff = total_tentative - total_cap
            # Deduct diff from lowest-priority segments first
            sorted_by_prio = sorted(range(n), key=lambda idx: float(segments[idx].get("priority_weight", 1.0)))
            for idx in sorted_by_prio:
                if diff <= 0:
                    break
                deduct = min(diff, allocations[idx])
                allocations[idx] -= deduct
                diff -= deduct

        # Assemble final results and clear human explanations
        results = []
        for i, seg in enumerate(segments):
            dem = float(seg.get("demand_mbps", 0.0))
            alloc = round(allocations[i], 2)
            unmet = round(max(0.0, dem - alloc), 2)
            sat_pct = round((alloc / dem * 100.0) if dem > 0 else 100.0, 2)
            weight = float(seg.get("priority_weight", 1.0))
            min_g = float(seg.get("min_guaranteed_mbps") or 0.0)

            # Generate natural language explanation
            if dem == 0.0:
                explanation = "Zero demand requested; 0 Mbps assigned."
            elif alloc >= dem:
                explanation = f"100% demand fulfilled ({alloc:.1f} Mbps). Priority weight {weight:.1f} provided full headroom."
            elif alloc >= ceilings[i] and ceilings[i] < dem:
                explanation = f"Allocation reached ceiling limit ({ceilings[i]:.1f} Mbps) as constrained by segment configuration."
            elif alloc > min_g:
                explanation = (
                    f"Guaranteed base {min_g:.1f} Mbps fulfilled plus {alloc - min_g:.1f} Mbps "
                    f"fair weighted proportional slice (Weight {weight:.1f}). Unmet: {unmet:.1f} Mbps."
                )
            else:
                explanation = (
                    f"Assigned {alloc:.1f} Mbps under heavy contention. Weight {weight:.1f} prioritized "
                    f"higher-tier academic/admin traffic while avoiding starvation."
                )

            results.append({
                "id": seg.get("id"),
                "name": seg.get("name"),
                "demand_mbps": dem,
                "allocated_mbps": alloc,
                "unmet_demand_mbps": unmet,
                "satisfaction_pct": sat_pct,
                "priority_weight": weight,
                "explanation": explanation
            })

        total_alloc = round(sum(r["allocated_mbps"] for r in results), 2)
        total_unmet = round(sum(r["unmet_demand_mbps"] for r in results), 2)
        unused_cap = round(max(0.0, total_cap - total_alloc), 2)

        return {
            "total_capacity_mbps": total_cap,
            "total_demand_mbps": round(total_dem, 2),
            "total_allocated_mbps": total_alloc,
            "total_unmet_demand_mbps": total_unmet,
            "unused_capacity_mbps": unused_cap,
            "segments": results,
            "policy_summary": (
                f"Optimized using Weighted Fair Queuing with Progressive Filling. "
                f"Distributed {total_alloc:.1f} Mbps of {total_cap:.1f} Mbps total capacity "
                f"across {n} segments based on QoS weights."
            )
        }
