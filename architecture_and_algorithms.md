# CampusNet: Architecture & Algorithmic Formulation

## 1. System Architecture

```mermaid
graph TD
    Client[Web Browser / NOC Dashboard] -->|HTTP / JSON REST API| Flask[Flask Application Controller (app.py)]
    Flask --> Metrics[Metrics Engine (metrics.py)]
    Flask --> Congestion[Congestion Detector (congestion.py)]
    Flask --> Optimizer[Bandwidth Optimizer (optimizer.py)]
    Flask --> Experiments[Experiments Engine (experiments.py)]
    Flask --> DB[(SQLite Database: campusnet.db)]
    Flask --> CSVAdapter[CSV Import/Export Adapter (csv_import.py)]
    Flask --> LabAdapter[Virtual Lab / Linux TC Adapter (lab_adapter.py)]
    LabAdapter -.->|Optional Linux TC / OVS| Mininet[Mininet Virtual Campus Lab]
```

### Module Responsibilities
1. **`app.py`:** REST API router, request validation, error formatting, and static template rendering.
2. **`services/metrics.py`:** Non-zero division safe utilization calculations, demand deficit tracking, percentile aggregations.
3. **`services/congestion.py`:** Multi-metric threshold crossing detection (70% warning, 85% critical), persistent vs. transient classification, explainable natural language reasoning.
4. **`services/optimizer.py`:** Implements Weighted Fair Queuing with Progressive Filling (WFQ-PF).
5. **`services/experiments.py`:** Pre-built scenario simulations, baseline FIFO vs. QoS comparisons, history persistence.
6. **`database/db.py`:** Thread-safe SQLite connection factory, schema creation, automated baseline seeding.
7. **`adapters/csv_import.py`:** Safe CSV ingestion with row-level error reporting and provenance tracking (`IMPORTED`).
8. **`adapters/lab_adapter.py`:** Generates Linux TC HTB configuration scripts; provides safe dry-run inspection on Windows hosts.

---

## 2. Mathematical Formulation: Weighted Fair Queuing with Progressive Filling (WFQ-PF)

### Given:
- Total shared uplink bottleneck capacity: $C \in \mathbb{R}_{\ge 0}$
- For each segment $i \in \{1, 2, \dots, N\}$:
  - Requested demand: $D_i \ge 0$
  - Priority weight: $w_i > 0$
  - Minimum guaranteed reservation: $0 \le M_{\text{min}, i} \le D_i$
  - Maximum ceiling constraint: $M_{\text{max}, i} \ge M_{\text{min}, i}$

### Invariants:
1. **Non-negativity:** $\forall i, \quad A_i \ge 0$
2. **Demand Bound:** $\forall i, \quad A_i \le D_i$
3. **Ceiling Bound:** $\forall i, \quad A_i \le M_{\text{max}, i}$
4. **Capacity Invariant:** $\sum_{i=1}^{N} A_i \le C$
5. **Work Conserving:** If $\sum_{i=1}^{N} D_i > C$, then $\sum_{i=1}^{N} A_i = C$.

---

### Algorithm Pseudocode:

```text
Algorithm: Weighted-Fair-Queuing-Progressive-Filling (C, Segments)
Input: Total capacity C, Segments with (D_i, w_i, Min_i, Max_i)
Output: Final allocations A_i, Unmet demands U_i, Explanations E_i

1.  If C <= 0:
2.      Return all A_i = 0, U_i = D_i
3.  If sum(D_i) <= C:
4.      Return all A_i = D_i (Unconstrained, 100% satisfied)
5.
6.  // Phase 1: Minimum Guaranteed Reservation
7.  For each segment i:
8.      Ceil_i = min(D_i, Max_i)
9.      A_i = min(Min_i, Ceil_i)
10. If sum(A_i) > C:
11.     // Overcommitted guarantees: Scale down proportionally
12.     Scale A_i = C * (w_i * A_i) / sum(w_j * A_j)
13.     Return A_i
14.
15. Remaining_Cap = C - sum(A_i)
16. Active_Set S = { i | A_i < Ceil_i }
17.
18. // Phase 2: Progressive Filling of Remainder
19. While Remaining_Cap > 1e-6 and |S| > 0:
20.     Total_Active_Weight = sum_{j in S} w_j
21.     Saturated_Set = empty
22.
23.     For each i in S:
24.         Propose Delta_i = Remaining_Cap * (w_i / Total_Active_Weight)
25.         Needed_i = Ceil_i - A_i
26.         If Delta_i >= Needed_i:
27.             Saturated_Set.add(i)
28.
29.     If Saturated_Set is not empty:
30.         For each k in Saturated_Set:
31.             Needed_k = Ceil_k - A_k
32.             A_k = Ceil_k
33.             Remaining_Cap = Remaining_Cap - Needed_k
34.             S.remove(k)
35.     Else:
36.         For each i in S:
37.             A_i = A_i + Delta_i
38.         Remaining_Cap = 0
39.         Break
40.
41. Clamp sum(A_i) <= C to handle IEEE-754 precision rounding.
42. Generate natural language explanation E_i for each segment.
43. Return Allocations A, Unmet U, Explanations E
```

---

## 3. Database Entity-Relationship (ER) Schema

```text
+-------------------------------------------------------------+
|                          segments                           |
+-------------------------------------------------------------+
| id (PK, TEXT)                                               |
| name (TEXT, UNIQUE)                                         |
| description (TEXT)                                          |
| capacity_mbps (REAL, >= 0)                                  |
| demand_mbps (REAL, >= 0)                                    |
| allocated_mbps (REAL, >= 0)                                 |
| priority_weight (REAL, > 0)                                 |
| min_guaranteed_mbps (REAL, >= 0)                            |
| max_limit_mbps (REAL)                                       |
| latency_ms (REAL)                                           |
| packet_loss_pct (REAL, 0..100)                              |
| jitter_ms (REAL)                                            |
| throughput_mbps (REAL)                                      |
| utilization_pct (REAL, >= 0)                                |
| status (TEXT: 'NORMAL', 'WARNING', 'CRITICAL')              |
| data_source (TEXT: 'SIMULATED', 'IMPORTED', 'LAB')          |
| updated_at (TEXT, ISO-8601)                                 |
+-------------------------------------------------------------+
         | 1                                  | 1
         | N                                  | N
+---------------------------+        +---------------------------+
|       measurements        |        |          alerts           |
+---------------------------+        +---------------------------+
| id (PK, AUTOINCREMENT)    |        | id (PK, AUTOINCREMENT)    |
| segment_id (FK)           |        | segment_id (FK)           |
| throughput_mbps (REAL)    |        | metric_name (TEXT)        |
| latency_ms (REAL)         |        | observed_value (REAL)     |
| packet_loss_pct (REAL)    |        | threshold_value (REAL)    |
| jitter_ms (REAL)          |        | severity (TEXT)           |
| utilization_pct (REAL)    |        | trigger_rule (TEXT)       |
| data_source (TEXT)        |        | explanation (TEXT)        |
| timestamp (TEXT)          |        | recommended_action (TEXT) |
| notes (TEXT)              |        | is_persistent (INTEGER)   |
+---------------------------+        | timestamp (TEXT)          |
                                     | is_resolved (INTEGER)     |
                                     +---------------------------+
```
