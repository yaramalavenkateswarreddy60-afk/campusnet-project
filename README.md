# CampusNet: Adaptive Campus Network Performance Optimization

> **National-Level Computer Networks Project**  
> *Adaptive Campus Network Performance Optimization Using Congestion Detection and Quality of Service (QoS)*

---

## 📌 Executive Summary

Campus networks frequently experience high latency, packet loss, video buffering, and unfair bandwidth starvation during peak hours when thousands of students, faculty, and smart devices compete for shared gateway capacity. Upgrading physical ISP lines takes months and capital expenditure, yet bursts of unmanaged non-essential traffic still cause bufferbloat and packet drops on mission-critical applications.

**CampusNet** solves this problem by providing an intelligent, self-contained network operations and optimization platform:
1. **Real-Time Telemetry & Monitoring:** Models 5 key campus segments (Computer Lab, Smart Classrooms, Library, Administration, and Guest Wi-Fi).
2. **Explainable Congestion Detection:** Uses configurable multi-metric heuristics (70% Warning, 85% Critical utilization; 50ms/100ms latency; 1%/3% packet loss) to classify transient spikes versus persistent bottlenecks and recommend remediation actions.
3. **Adaptive QoS Bandwidth Optimization:** Implements **Weighted Fair Queuing with Progressive Filling (WFQ-PF)** to reallocate shared uplink capacity dynamically while preventing flow starvation.
4. **Empirical Before-and-After Experiments:** Compares unweighted FIFO contention against adaptive QoS schedules, proving quantifiable improvements (+10.65% high-priority satisfaction gain, critical alert mitigation).
5. **Data Provenance & Safety:** Distinguishes `SIMULATED`, `IMPORTED`, and `LAB` data sources and provides Linux TC HTB queue script generation for isolated virtual testbeds.

---

## 🛠️ Technology Stack

- **Backend:** Python 3.10+, Flask 3.0+, SQLite3 (ACID-compliant relational store with automatic initialization)
- **Frontend:** HTML5, CSS3 (Modern NOC Dark Theme Design System), Vanilla JavaScript (Modular ES6), Chart.js (Bundled locally for 100% offline functionality)
- **Testing:** `pytest` (51 automated unit & integration test cases: REST API, RBAC permissions, approval lifecycle, audit trails, and QoS algorithms)
- **Optional Virtual Lab:** Mininet, Open vSwitch, Linux Traffic Control (`tc` HTB)

---

## 🚀 Quickstart Guide (Windows 10 / 11)

### 1. Prerequisites
- Windows 10 or 11
- Python 3.10 or higher installed with `pip` and added to system `PATH`.

### 2. Open Terminal
Open **Windows PowerShell** or **Command Prompt** in the project directory:
```powershell
cd "c:\Users\dasar\OneDrive\Desktop\cn 1"
```

### 3. (Optional) Create and Activate Virtual Environment
**Using Windows PowerShell:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(If PowerShell displays an execution policy error, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

**Or using Command Prompt (`cmd.exe`):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### 4. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 5. Run Automated Tests
Verify mathematical invariants, congestion boundary thresholds, CSV validation, and all API endpoints:
```powershell
python -m pytest -v
```
*(Expected: All 51 test cases pass in ~1 second).*

### 6. Launch CampusNet Operations Server
```powershell
python app.py
```

### 7. Access the Dashboard
Open your web browser and navigate to:
```text
http://127.0.0.1:5000
```

---

## 🏗️ Project Architecture & Directory Structure

```text
CampusNetworkOptimizer/
├── app.py                     # Main Flask Application & REST API Controller
├── config.py                  # Environment Configuration & Demonstration Thresholds
├── requirements.txt           # Python Package Dependencies
├── README.md                  # Comprehensive Project Guide & Documentation
├── .gitignore                 # Git ignore rules for Python, SQLite, and caches
│
├── database/                  # Database Layer
│   ├── __init__.py
│   ├── db.py                  # Thread-Safe SQLite Connection Manager & Baseline Seeder
│   └── schema.sql             # Relational Schema with Constraints & Indexes
│
├── services/                  # Core Network Logic & Algorithms
│   ├── __init__.py
│   ├── metrics.py             # Safe Utilization, Unmet Demand, & Percentiles
│   ├── congestion.py          # Heuristic Congestion Detector & Alert Generator
│   ├── optimizer.py           # Weighted Fair Queuing with Progressive Filling (WFQ-PF)
│   └── experiments.py         # Controlled Scenario Engine & Baseline/QoS Comparisons
│
├── adapters/                  # Ingestion & Infrastructure Adapters
│   ├── __init__.py
│   ├── csv_import.py          # Validated CSV Ingestion with Provenance Tracking
│   └── lab_adapter.py         # Virtual Testbed & Linux TC Script Generator
│
├── templates/                 # UI Presentation
│   └── index.html             # Responsive Single-Page NOC Operations Center
│
├── static/                    # Frontend Static Assets
│   ├── css/
│   │   └── style.css          # NOC Dark Theme Design System
│   └── js/
│       ├── chart.min.js       # Bundled Offline Chart.js Engine
│       └── dashboard.js       # Interactive Dashboard Controller & Real-Time Logic
│
├── tests/                     # Automated Test Suite (38 Tests)
│   ├── __init__.py
│   ├── test_metrics.py        # Numerical Safety & Zero Capacity Edge Cases
│   ├── test_congestion.py     # Warning (70%) and Critical (85%) Threshold Boundaries
│   ├── test_optimizer.py      # Capacity Invariant, Demand Bound, & Work-Conserving
│   ├── test_csv_import.py     # File Validation & Malformed Input Handling
│   └── test_api.py            # Integration Tests for all 12 REST Endpoints
│
├── sample_data/               # Sample Test Datasets
│   ├── sample_measurements.csv
│   └── sample_heavy_congestion.csv
│
├── lab/                       # Optional Linux / Mininet Testbed Component
│   └── mininet_campus_topo.py # Mininet 5-Segment Virtual Topology Script
│
└── docs/                      # Presentation & Defense Documentation
    ├── demo_script.md         # 3–5 Minute Presentation & Live Viva Script
    ├── experiment_protocol.md # Scientific Methodology & Scenario Benchmarks
    └── architecture_and_algorithms.md # Math Formulation & ER Schema Diagrams
```

---

## 📐 Mathematical Algorithm: WFQ-PF

The optimization core implements **Weighted Fair Queuing with Progressive Filling (WFQ-PF)**:

### 1. Invariants Strictly Guaranteed
1. **Non-Negativity:** $\forall i, \quad \text{Allocation}_i \ge 0$
2. **Demand Bounded:** $\forall i, \quad \text{Allocation}_i \le \text{Demand}_i$
3. **Capacity Invariant:** $\sum_{i=1}^N \text{Allocation}_i \le C_{\text{gateway}}$
4. **Work-Conserving:** Any bandwidth left unconsumed by low-demand divisions (e.g. Library) is dynamically redistributed to congested high-priority divisions (e.g. Smart Classrooms).
5. **Starvation Avoidance:** Best-effort segments (Guest Wi-Fi) retain a guaranteed non-zero baseline slice even under severe congestion.

### 2. Traffic Classes & Priority Weights

| Traffic Class | Priority Weight | Minimum Reservation | DSCP Mark | Campus Segment |
|---|---|---|---|---|
| **Mission-Critical Admin** | 5.0x | 40.0 Mbps | CS6 (48) | Administration (ERP, exams) |
| **Academic Interactive** | 4.0x – 4.5x | 100.0 Mbps | EF (46) / AF41 | Smart Classrooms (HD Lectures) |
| **Research & Computing** | 3.0x | 50.0 Mbps | AF31 (26) | Computer Lab (Cloud, CAD) |
| **General Educational** | 2.0x | 20.0 Mbps | AF11 (10) | Library (e-Journals, search) |
| **Guest & Bulk Best-Effort** | 1.0x | 10.0 Mbps | BE (0) | Guest Wi-Fi (Public browsing) |

---

## 📡 REST API Documentation

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the main NOC operations center web dashboard. |
| `GET` | `/api/health` | System health, database connectivity status, and environment inspection. |
| `GET` | `/api/summary` | High-level aggregate metrics, utilization, and active alert counts. |
| `GET` | `/api/segments` | Details, allocations, and telemetry for all 5 campus divisions. |
| `GET` | `/api/alerts` | List of active threshold violations with explainable root causes. |
| `GET` | `/api/measurements` | Chronological telemetry series for live latency and packet loss charts. |
| `POST` | `/api/optimize` | Runs the WFQ-PF optimizer. Accepts `apply: true` to commit changes. |
| `GET` | `/api/scenarios` | Lists pre-built benchmark scenarios (Peak, Exam Day, Evening, Normal). |
| `POST` | `/api/experiments/run` | Executes a before-and-after benchmark experiment and stores in SQLite. |
| `GET` | `/api/history` | Retrieves recent experiment records and comparative metrics. |
| `GET` | `/api/experiments/<id>/compare` | Retrieves segment-by-segment deltas for an experiment run. |
| `POST` | `/api/import/csv` | Ingests aggregate telemetry CSV with line-by-line validation. |
| `GET` | `/api/export.csv` | Exports current network status to a downloadable CSV log. |
| `POST` | `/api/demo/reset` | Restores clean calibrated demonstration baseline state. |
| `GET` | `/api/lab/preview` | Generates Linux TC HTB queue configuration commands. |

---

## 🧪 Automated Testing Suite

CampusNet includes 38 automated test cases covering edge cases, math invariants, and fault injection:

```powershell
python -m pytest -v
```

### Coverage Highlights:
- **`test_metrics.py`:** Zero link capacity handled safely without `ZeroDivisionError` or `NaN`; percentile calculations verified.
- **`test_congestion.py`:** Boundary checks at exactly 70.0% (Warning) and 85.0% (Critical); persistent vs. single-sample alert separation.
- **`test_optimizer.py`:** Capacity invariant ($\sum A_i \le C$); demand bound ($A_i \le D_i$); work-conserving redistribution; negative input rejection.
- **`test_csv_import.py`:** Valid CSV parsing; missing headers detection; unknown segment rejection; physical impossibilities (loss > 100%) safely caught.
- **`test_api.py`:** End-to-end HTTP integration tests for all core dashboard and telemetry endpoints.
- **`test_auth_admin.py`:** RBAC role permissions, unauthenticated rejections, policy approval lifecycle (PENDING -> APPROVED -> APPLIED -> ROLLED_BACK), rollback validation, audit log persistence, and production safety invariant guards.

---

## 🛡️ Authority & Administration Module

CampusNet features an enterprise-grade **Authority & Network Administrator Control Center** providing strict separation of duties, cryptographically secured role-based access control, two-person policy approval workflows, and an immutable operational audit trail.

### 1. Role-Based Access Control (RBAC) Architecture

| Role | Identifier | Responsibilities & Permissions |
| :--- | :--- | :--- |
| **Administrator** | `admin` | Full system authority: user account management, dynamic congestion threshold tuning, network segment configuration, policy approval/rejection, testbed execution, and rollback. |
| **Network Administrator** | `netadmin` | Operational authority: telemetry monitoring, congestion investigation, WFQ-PF policy proposals, execution of approved policies *only* in isolated testbeds, experiment runs, and rollbacks. |
| **Read-Only Authority** | `readonly` | Executive & Compliance authority: real-time dashboard monitoring, alert reviews, audit trail inspection, experiment history, and one-click report downloads. Cannot mutate configuration. |

### 2. Default Demonstration Accounts

The platform automatically seeds 3 calibrated demonstration accounts with PBKDF2/scrypt hashed passwords:

| Username | Password | Role | Description |
| :--- | :--- | :--- | :--- |
| `admin` | `Admin@CampusNet2026` | `admin` | Campus IT Director (Full Administrative Authority) |
| `netadmin` | `NetAdmin@CampusNet2026` | `netadmin` | Senior NOC Network Engineer (Operations & Optimization) |
| `authority` | `Authority@CampusNet2026` | `readonly` | Institutional Compliance Officer (Read-Only Auditor) |

*(The web interface provides 1-click preset buttons on the Sign In dialog for fast presentation demonstrations).*

### 3. Policy Approval & Rollback Lifecycle Workflow

To prevent accidental misconfigurations and enforce organizational governance, optimization schedules follow a strict finite-state approval lifecycle:

```
[NetAdmin/Admin Proposes] ──> PENDING
                                │
               ┌────────────────┴────────────────┐
               ▼                                 ▼
      [Admin Approves]                  [Admin Rejects]
               ▼                                 ▼
           APPROVED                           REJECTED
               │
      [NetAdmin/Admin Executes]
               ▼
            APPLIED ──[Rollback Triggered]──> ROLLED_BACK
```

1. **`PENDING`**: Initial proposal submitted by Network Administrator with computed megabit allocations and operational rationale. Cannot be executed directly.
2. **`APPROVED`**: Reviewed and authorized by an Administrator. Ready for isolated testbed execution.
3. **`REJECTED`**: Denied by an Administrator with explicit justification recorded in the audit trail.
4. **`APPLIED`**: Executed in the test network. Prior to state application, the system takes an atomic snapshot of current segment allocations and stores it in `rollback_data`.
5. **`ROLLED_BACK`**: Restores the previous network allocations with full telemetry recalculation and audit logging.

### 4. Operational Safety Invariant (Production Network Lock)

> [!IMPORTANT]
> **Strict Safety Constraint:** CampusNet enforces by default that optimization policies can **only** be executed in the `ISOLATED_TESTBED` or `SIMULATION` environments. Direct execution on production campus gateways is permanently locked (`ALLOW_PRODUCTION_ENFORCEMENT = False`) and rejected by backend API validation unless explicitly authorized with multi-level credentials.

### 5. Audit Trail & Compliance Reporting

- **Immutable Audit Trail:** All logins, logouts, user creations, configuration updates, threshold modifications, policy approvals, executions, and rollbacks are permanently recorded in the `audit_logs` SQLite table with UTC timestamps, user roles, and client IP addresses.
- **Export Center:** Authorized users can download CSV and printable executive reports:
  - **Live Campus Telemetry Report** (`/api/reports/telemetry`)
  - **Policy Governance History Report** (`/api/reports/policies`)
  - **Security & Operations Audit Trail** (`/api/reports/audit`)
  - **Executive Summary Report** (`/api/reports/executive`)

---

## 📊 CSV Import Specification

To import custom telemetry into CampusNet via the dashboard or `/api/import/csv`:

```csv
timestamp,segment_name,demand_mbps,throughput_mbps,capacity_mbps,latency_ms,packet_loss_pct,jitter_ms,notes
2026-10-21T10:00:00Z,Computer Lab,250.0,240.0,300.0,30.5,0.8,4.0,Morning programming session
2026-10-21T10:00:00Z,Smart Classrooms,220.0,215.0,250.0,25.0,0.3,2.5,Video conference
```

- **Required Fields:** `timestamp`, `segment_name`, `demand_mbps`
- **Allowed Segments:** `Computer Lab`, `Smart Classrooms`, `Library`, `Administration`, `Guest Wi-Fi`
- **Data Provenance:** Ingested entries are automatically tagged with `data_source = 'IMPORTED'`.

---

## 🔍 Troubleshooting & FAQs

### 1. Port 5000 Already in Use
If port 5000 is occupied by another application, specify an alternative port:
```powershell
python -c "from app import app; app.run(port=5050)"
```

### 2. Resetting the Database
If you wish to return the database to its pristine demo state, click the **"Reset Demo"** button on the dashboard or run:
```powershell
curl -X POST http://127.0.0.1:5000/api/demo/reset
```

### 3. Mininet / Linux Virtual Lab Support
The core application runs natively on Windows without Linux or Mininet. If you wish to demonstrate the optional virtual lab, install WSL2 with Ubuntu (`wsl --install -d Ubuntu`), install Mininet (`sudo apt install mininet openvswitch-switch iproute2`), and execute `sudo python3 lab/mininet_campus_topo.py`.

---

## 🏆 National Competition Deliverables Included

- **Presentation Script:** [`docs/demo_script.md`](file:///c:/Users/dasar/OneDrive/Desktop/cn%201/docs/demo_script.md)
- **Experiment Protocol:** [`docs/experiment_protocol.md`](file:///c:/Users/dasar/OneDrive/Desktop/cn%201/docs/experiment_protocol.md)
- **Architecture & Math:** [`docs/architecture_and_algorithms.md`](file:///c:/Users/dasar/OneDrive/Desktop/cn%201/docs/architecture_and_algorithms.md)
- **Sample Datasets:** [`sample_data/sample_measurements.csv`](file:///c:/Users/dasar/OneDrive/Desktop/cn%201/sample_data/sample_measurements.csv)
- **Mininet Lab Script:** [`lab/mininet_campus_topo.py`](file:///c:/Users/dasar/OneDrive/Desktop/cn%201/lab/mininet_campus_topo.py)
