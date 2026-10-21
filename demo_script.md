# CampusNet: 3–5 Minute Live Demonstration Script

This script is designed for a national-level Computer Networks project competition, student viva, or academic examination. Follow these exact steps to demonstrate problem definition, live bottleneck detection, adaptive QoS optimization, and empirical before-and-after verification.

---

## ⏱️ Timeline Overview

| Time | Stage | Action | Key Talking Point |
|---|---|---|---|
| **0:00 – 0:45** | Problem Statement & Architecture | Show Overview Dashboard | Shared campus gateway bottleneck, demand contention (915 Mbps vs. 800 Mbps link). |
| **0:45 – 1:45** | Bottleneck Detection & Alerts | Inspect Segments & Alerts Panel | Heuristic threshold crossings (70% warn, 85% crit), explainable root cause, recommended actions. |
| **1:45 – 3:00** | Adaptive QoS Optimization | Open Policy Simulator | Weighted Fair Queuing with Progressive Filling (WFQ-PF); live preview and commit. |
| **3:00 – 4:15** | Controlled Experiments | Run Scenario Experiment | Side-by-side FIFO vs. WFQ-PF comparison; +10.6% high-priority gain, critical alerts prevented. |
| **4:15 – 5:00** | Data Ingestion & Lab Isolation | Show CSV & TC Script | Data provenance (`SIMULATED` vs. `IMPORTED`), safe Linux TC preview, zero production disruption. |

---

## Step-by-Step Viva Presentation Walkthrough

### 1. Introduction (0:00 – 0:45)
- **What to show:** Open `http://127.0.0.1:5000` in the browser. Display the **Operations Dashboard**.
- **What to say:**
  > *"Respected judges, campus networks frequently suffer from internet slowdowns, video buffering in lecture halls, and exam portal timeouts during peak hours. Simply upgrading physical ISP bandwidth takes months and thousands of dollars, yet unmanaged burst traffic still overwhelms queue buffers.*
  > *Our project, **CampusNet**, is an adaptive performance optimization system that monitors segment-level demand, detects congestion using explainable multi-metric heuristics, dynamically reallocates bandwidth using Weighted Fair Queuing with Progressive Filling (WFQ-PF), and validates results through repeatable before-and-after experiments."*

### 2. Live Telemetry & Congestion Detection (0:45 – 1:45)
- **What to show:** Scroll down to the **Active Bottleneck Alerts** and **Campus Network Segments** cards.
- **What to say:**
  > *"Here on the dashboard, we model 5 distinct campus divisions: Computer Lab, Smart Classrooms, Library, Administration, and Guest Wi-Fi. Notice that total requested demand is 915 Mbps, exceeding our modeled 800 Mbps gateway uplink.*
  > *Under standard unmanaged conditions, Guest Wi-Fi surges to 87.5% utilization, triggering a **CRITICAL** alert, while Smart Classrooms experience 62ms latency, jeopardizing interactive lectures.*
  > *Unlike black-box models, CampusNet provides explainable rules: for each alert, we show the exact threshold crossed, the root cause, and a practical recommended remedy."*

### 3. Policy Simulator & Bandwidth Optimization (1:45 – 3:00)
- **What to show:** Click the **QoS Policy Simulator** tab (`tab-btn-simulator`).
- **What to say:**
  > *"Now we transition to the QoS Policy Simulator. Notice the sliders for each campus segment:*
  > *- Administration is assigned **Priority 5.0** (Mission Critical).*
  > *- Smart Classrooms are assigned **Priority 4.5** (Interactive Video).*
  > *- Guest Wi-Fi is set to **Priority 1.0** (Best Effort).*
  > *Let's click **'Calculate Live Preview'**.*
  > *Our custom optimizer implements **Weighted Fair Queuing with Progressive Filling**. It strictly enforces mathematical invariants: allocations never exceed demand, total allocation never exceeds link capacity, and unused headroom from the Library is automatically reallocated to hungry academic flows without starving Guest Wi-Fi.*
  > *Now let's click **'Apply Policy to Campus Network'**."*

### 4. Controlled Experiments: Before-and-After Verification (3:00 – 4:15)
- **What to show:** Click the **Controlled Experiments** tab (`tab-btn-experiments`). Select scenario *"Peak Video Lecture & Lab Hours"* and click **"Run Controlled Experiment"**.
- **What to say:**
  > *"To scientifically validate our optimization, we run controlled benchmark scenarios. Here we compare raw unweighted FIFO contention against our adaptive QoS schedule.*
  > *Looking at our comparative results:*
  > *1. High-priority traffic satisfaction improved by **+10.65%**.*
  > *2. Critical alerts were completely prevented.*
  > *3. Video latency in Smart Classrooms dropped from 62ms to a crisp 19ms.*
  > *All experiment runs are persisted in SQLite and can be exported as audit-ready CSV logs."*

### 5. Data Provenance & Conclusion (4:15 – 5:00)
- **What to show:** Point to the **Data Source Badge** (`SIMULATED`), briefly open the **Virtual Lab & Linux TC** tab to show generated `tc` scripts, and conclude.
- **What to say:**
  > *"CampusNet enforces strict scientific integrity: simulated seeds, imported CSV historical data, and lab testbed measurements are explicitly tagged with provenance badges. Furthermore, our lab adapter translates policies directly into Linux Hierarchical Token Bucket (`tc htb`) queue disciplines for Mininet/Open vSwitch testbeds, while guaranteeing that physical network cards are never altered.*
  > *In summary, CampusNet transforms unmanaged campus bottlenecks into deterministic, prioritized, and explainable network performance. Thank you, and we welcome your questions!"*

---

## 💡 Top Viva Questions & Model Answers

**Q1: Why does your algorithm not simply allocate equal bandwidth to every segment?**
> *A: Equal sharing ignores traffic semantics. In a campus environment, a 50 Mbps drop on Guest Wi-Fi causes temporary buffer delay for video streaming, whereas a 50 Mbps drop on Administrative exam portals or medical school tele-lectures disrupts institutional operations. Priority weighting aligns network resources with campus priorities.*

**Q2: What prevents low-priority guest traffic from starving completely?**
> *A: In Phase 1 of our WFQ-PF algorithm, every segment receives a guaranteed non-zero baseline slice (e.g. 15–20 Mbps). Phase 2 then distributes only the remaining surplus proportionally to priority weights. This guarantees best-effort connectivity and eliminates silent starvation.*

**Q3: Does CampusNet actually increase internet speed?**
> *A: No. No algorithm can physically exceed the ISP bandwidth pipe. CampusNet optimizes resource allocation and queuing delay within the available channel, ensuring critical packets avoid tail-drop losses and excessive round-trip latency.*
