/**
 * CampusNet: Network Operations Center & QoS Optimization Engine
 * Interactive Dashboard Controller (Vanilla JavaScript & Chart.js)
 */

(function () {
  "use strict";

  // Application State
  const state = {
    segments: [],
    summary: {},
    alerts: [],
    measurements: [],
    scenarios: [],
    history: [],
    previewResult: null,
    autoRefreshInterval: null,
    isPaused: false,
    charts: {
      alloc: null,
      util: null,
      telemetry: null
    }
  };

  // DOM Elements Cache
  const el = {};

  function init() {
    cacheDom();
    initTheme();
    bindEvents();
    loadAllData();
    startAutoRefresh();
  }

  function cacheDom() {
    el.navTabs = document.querySelectorAll(".tab-btn");
    el.tabPanes = document.querySelectorAll(".tab-pane");

    // Header Controls & Theme Switcher
    el.refreshBtn = document.getElementById("btn-refresh");
    el.resetDemoBtn = document.getElementById("btn-reset-demo");
    el.exportCsvBtn = document.getElementById("btn-export-csv");
    el.importCsvBtn = document.getElementById("btn-open-import-modal");
    el.lastUpdated = document.getElementById("last-updated-text");
    el.dataSourceBadge = document.getElementById("data-source-badge");
    el.healthPill = document.getElementById("health-pill");
    el.themeToggleBtn = document.getElementById("theme-toggle-btn");
    el.themeToggleLabel = document.getElementById("theme-toggle-label");

    // KPI Cards
    el.kpiCapacity = document.getElementById("kpi-capacity");
    el.kpiDemand = document.getElementById("kpi-demand");
    el.kpiAllocated = document.getElementById("kpi-allocated");
    el.kpiUtilization = document.getElementById("kpi-utilization");
    el.kpiAlerts = document.getElementById("kpi-alerts");
    el.kpiSatisfaction = document.getElementById("kpi-satisfaction");

    // Grids & Panels
    el.segmentsGrid = document.getElementById("segments-grid");
    el.alertsList = document.getElementById("alerts-list");
    el.alertsBadgeCount = document.getElementById("alerts-badge-count");

    // Simulator Tab
    el.simCapacityInput = document.getElementById("sim-capacity-input");
    el.simSegmentsContainer = document.getElementById("sim-segments-container");
    el.btnPreviewPolicy = document.getElementById("btn-preview-policy");
    el.btnApplyPolicy = document.getElementById("btn-apply-policy");
    el.simExplanationBox = document.getElementById("sim-explanation-box");
    el.simExplanationList = document.getElementById("sim-explanation-list");
    el.simSummaryText = document.getElementById("sim-summary-text");

    // Experiments Tab
    el.scenarioSelect = document.getElementById("scenario-select");
    el.btnRunExperiment = document.getElementById("btn-run-experiment");
    el.expComparisonWrap = document.getElementById("exp-comparison-wrap");
    el.expTableBody = document.getElementById("exp-table-body");
    el.expDeltaHpGain = document.getElementById("exp-delta-hp-gain");
    el.expDeltaAlertsPrevented = document.getElementById("exp-delta-alerts-prevented");
    el.expDeltaUnmetRed = document.getElementById("exp-delta-unmet-red");
    el.expHistoryTableBody = document.getElementById("exp-history-table-body");

    // Modals
    el.importModal = document.getElementById("import-modal");
    el.btnCloseImportModal = document.getElementById("btn-close-import-modal");
    el.btnCancelImport = document.getElementById("btn-cancel-import");
    el.csvFileInput = document.getElementById("csv-file-input");
    el.btnUploadCsv = document.getElementById("btn-upload-csv");
    el.importStatusMsg = document.getElementById("import-status-msg");
    el.toastContainer = document.getElementById("toast-container");

    // Virtual Lab Tab
    el.labStatusBanner = document.getElementById("lab-status-banner");
    el.labTcCodeBlock = document.getElementById("lab-tc-code-block");
  }

  function bindEvents() {
    // Navigation Tabs
    el.navTabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const targetTab = tab.dataset.tab;
        switchTab(targetTab);
      });
    });

    // Header Actions
    if (el.refreshBtn) {
      el.refreshBtn.addEventListener("click", () => {
        loadAllData();
        showToast("Dashboard refreshed", "info");
      });
    }

    if (el.resetDemoBtn) {
      el.resetDemoBtn.addEventListener("click", resetDemo);
    }

    if (el.exportCsvBtn) {
      el.exportCsvBtn.addEventListener("click", () => {
        window.location.href = "/api/export.csv";
        showToast("Exporting campus network CSV...", "info");
      });
    }

    // Light / Dark Theme Switcher
    if (el.themeToggleBtn) {
      el.themeToggleBtn.addEventListener("click", () => {
        toggleTheme();
      });
    }

    // Import Modal
    if (el.importCsvBtn) {
      el.importCsvBtn.addEventListener("click", () => {
        el.importModal.classList.add("active");
        el.importStatusMsg.textContent = "";
      });
    }

    if (el.btnCloseImportModal) {
      el.btnCloseImportModal.addEventListener("click", () => {
        el.importModal.classList.remove("active");
      });
    }

    if (el.btnCancelImport) {
      el.btnCancelImport.addEventListener("click", () => {
        el.importModal.classList.remove("active");
      });
    }

    if (el.btnUploadCsv) {
      el.btnUploadCsv.addEventListener("click", handleCsvUpload);
    }

    // Simulator Buttons
    if (el.btnPreviewPolicy) {
      el.btnPreviewPolicy.addEventListener("click", () => runSimulator(false));
    }

    if (el.btnApplyPolicy) {
      el.btnApplyPolicy.addEventListener("click", () => runSimulator(true));
    }

    // Experiment Button
    if (el.btnRunExperiment) {
      el.btnRunExperiment.addEventListener("click", handleRunExperiment);
    }
  }

  function switchTab(targetTab) {
    el.navTabs.forEach((t) => {
      t.classList.toggle("active", t.dataset.tab === targetTab);
    });
    el.tabPanes.forEach((p) => {
      p.classList.toggle("active", p.id === `pane-${targetTab}`);
    });

    // Resize charts if overview or simulator became visible
    if (targetTab === "overview") {
      setTimeout(() => {
        if (state.charts.alloc) state.charts.alloc.resize();
        if (state.charts.util) state.charts.util.resize();
        if (state.charts.telemetry) state.charts.telemetry.resize();
      }, 50);
    }
  }

  // -------------------------------------------------------------
  // Data Loading & API Calls
  // -------------------------------------------------------------
  async function loadAllData() {
    try {
      await Promise.all([
        loadHealth(),
        loadSummary(),
        loadSegments(),
        loadAlerts(),
        loadMeasurements(),
        loadScenarios(),
        loadHistory(),
        loadLabPreview()
      ]);
      updateLastUpdatedTimestamp();
    } catch (err) {
      console.error("Error loading dashboard data:", err);
      showToast("Network fetch error. Retrying...", "error");
    }
  }

  async function loadHealth() {
    const res = await fetch("/api/health");
    if (!res.ok) return;
    const data = await res.json();
    if (el.healthPill) {
      el.healthPill.textContent = `${data.status} • SQLite ${data.database_status}`;
    }
  }

  async function loadSummary() {
    const res = await fetch("/api/summary");
    if (!res.ok) return;
    state.summary = await res.json();
    renderSummary();
  }

  async function loadSegments() {
    const res = await fetch("/api/segments");
    if (!res.ok) return;
    const data = await res.json();
    state.segments = data.segments;
    renderSegments();
    renderSimulatorControls();
    updateCharts();
  }

  async function loadAlerts() {
    const res = await fetch("/api/alerts");
    if (!res.ok) return;
    const data = await res.json();
    state.alerts = data.alerts;
    renderAlerts();
  }

  async function loadMeasurements() {
    const res = await fetch("/api/measurements?limit=15");
    if (!res.ok) return;
    const data = await res.json();
    state.measurements = data.measurements;
    updateTelemetryChart();
  }

  async function loadScenarios() {
    const res = await fetch("/api/scenarios");
    if (!res.ok) return;
    const data = await res.json();
    state.scenarios = data.scenarios;
    renderScenarioOptions();
  }

  async function loadHistory() {
    const res = await fetch("/api/history?limit=10");
    if (!res.ok) return;
    const data = await res.json();
    state.history = data.experiments;
    renderHistoryTable();
  }

  async function loadLabPreview() {
    const res = await fetch("/api/lab/preview");
    if (!res.ok) return;
    const data = await res.json();
    renderLabTab(data);
  }

  // -------------------------------------------------------------
  // Renderers
  // -------------------------------------------------------------
  function renderSummary() {
    const s = state.summary;
    if (!s) return;

    if (el.kpiCapacity) el.kpiCapacity.innerHTML = `${s.total_modeled_capacity_mbps || 0} <span class="kpi-unit">Mbps</span>`;
    if (el.kpiDemand) el.kpiDemand.innerHTML = `${s.total_demand_mbps || 0} <span class="kpi-unit">Mbps</span>`;
    if (el.kpiAllocated) el.kpiAllocated.innerHTML = `${s.total_allocated_mbps || 0} <span class="kpi-unit">Mbps</span>`;

    const utilPct = s.aggregate_utilization_pct || 0;
    if (el.kpiUtilization) {
      el.kpiUtilization.innerHTML = `${utilPct.toFixed(1)} <span class="kpi-unit">%</span>`;
    }

    const alertsTotal = s.active_alerts ? s.active_alerts.total : 0;
    const criticals = s.active_alerts ? s.active_alerts.critical : 0;
    if (el.kpiAlerts) {
      el.kpiAlerts.innerHTML = `${alertsTotal} <span class="kpi-unit">(${criticals} Crit)</span>`;
    }

    if (el.kpiSatisfaction) {
      el.kpiSatisfaction.innerHTML = `${(s.satisfaction_rate_pct || 0).toFixed(1)} <span class="kpi-unit">%</span>`;
    }

    if (el.dataSourceBadge) {
      el.dataSourceBadge.textContent = s.data_source_badge || "SIMULATED";
      el.dataSourceBadge.className = `badge badge-${(s.data_source_badge || "simulated").toLowerCase()}`;
    }
  }

  function renderSegments() {
    if (!el.segmentsGrid) return;
    el.segmentsGrid.innerHTML = "";

    state.segments.forEach((seg) => {
      const card = document.createElement("div");
      card.className = "segment-card";

      const util = seg.utilization_pct || 0;
      const statusClass = seg.status === "CRITICAL" ? "critical" : (seg.status === "WARNING" ? "warning" : "normal");

      card.innerHTML = `
        <div class="segment-header">
          <div class="segment-title-wrap">
            <h3>${escapeHtml(seg.name)}</h3>
            <div class="segment-desc">${escapeHtml(seg.description || "")}</div>
          </div>
          <span class="badge badge-${statusClass}">
            <span class="status-dot ${statusClass}"></span> ${seg.status}
          </span>
        </div>

        <div class="metrics-row">
          <div class="metric-item">
            <span class="label">Demand</span>
            <span class="val">${seg.demand_mbps} <small>Mbps</small></span>
          </div>
          <div class="metric-item">
            <span class="label">Allocation</span>
            <span class="val" style="color: var(--color-cyan);">${seg.allocated_mbps} <small>Mbps</small></span>
          </div>
          <div class="metric-item">
            <span class="label">Link Capacity</span>
            <span class="val">${seg.capacity_mbps} <small>Mbps</small></span>
          </div>
          <div class="metric-item">
            <span class="label">QoS Weight</span>
            <span class="val">${seg.priority_weight}x</span>
          </div>
        </div>

        <div class="progress-container">
          <div class="progress-header">
            <span>Link Utilization</span>
            <span class="font-mono">${util.toFixed(1)}%</span>
          </div>
          <div class="progress-bar-bg">
            <div class="progress-bar-fill ${statusClass}" style="width: ${Math.min(100, util)}%;"></div>
          </div>
        </div>

        <div class="telemetry-row">
          <span>Latency: <strong>${seg.latency_ms !== null ? seg.latency_ms + ' ms' : 'N/A'}</strong></span>
          <span>Loss: <strong>${seg.packet_loss_pct !== null ? seg.packet_loss_pct + '%' : '0%'}</strong></span>
          <span>Source: <strong style="color: var(--color-blue);">${seg.data_source}</strong></span>
        </div>
      `;

      el.segmentsGrid.appendChild(card);
    });
  }

  function renderAlerts() {
    if (!el.alertsList) return;
    el.alertsList.innerHTML = "";

    if (el.alertsBadgeCount) {
      el.alertsBadgeCount.textContent = `${state.alerts.length} Active`;
    }

    if (state.alerts.length === 0) {
      el.alertsList.innerHTML = `
        <div style="text-align: center; padding: 2rem; color: var(--text-muted); background: var(--bg-card); border-radius: var(--radius-md);">
          ✓ All segment interfaces are within normal demonstration thresholds. No active bottlenecks.
        </div>
      `;
      return;
    }

    state.alerts.forEach((alert) => {
      const item = document.createElement("div");
      const isCrit = alert.severity === "CRITICAL";
      item.className = `alert-item ${isCrit ? "critical" : "warning"}`;

      item.innerHTML = `
        <div class="alert-item-header">
          <div class="alert-title">
            <span class="status-dot ${isCrit ? "critical" : "warning"}"></span>
            <strong>${escapeHtml(alert.segment_name)}: ${escapeHtml(alert.trigger_rule)}</strong>
            <span class="badge badge-${isCrit ? "critical" : "warning"}">${alert.severity}</span>
            ${alert.is_persistent ? '<span class="badge" style="background:rgba(255,255,255,0.1); color:#fff;">PERSISTENT</span>' : ''}
          </div>
          <small style="color: var(--text-muted);">${formatTime(alert.timestamp)}</small>
        </div>
        <div class="alert-reason">${escapeHtml(alert.explanation)}</div>
        <div class="alert-action-box">
          <div><span class="action-label">Recommended Action:</span> ${escapeHtml(alert.recommended_action)}</div>
          <button class="btn btn-primary btn-sm quick-optimize-btn" data-segid="${alert.segment_id}" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;">
            Apply QoS Action
          </button>
        </div>
      `;

      el.alertsList.appendChild(item);
    });

    // Bind quick optimize buttons
    el.alertsList.querySelectorAll(".quick-optimize-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        switchTab("simulator");
        runSimulator(false);
        showToast("Loaded recommended QoS parameters into Simulator", "info");
      });
    });
  }

  function renderSimulatorControls() {
    if (!el.simSegmentsContainer) return;
    el.simSegmentsContainer.innerHTML = "";

    if (el.simCapacityInput && !el.simCapacityInput.value) {
      el.simCapacityInput.value = state.summary.total_modeled_capacity_mbps || 800;
    }

    state.segments.forEach((seg) => {
      const row = document.createElement("div");
      row.className = "control-panel-card";
      row.style.padding = "1rem";
      row.dataset.segId = seg.id;

      row.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
          <h4 style="font-size: 0.95rem; color: #fff;">${escapeHtml(seg.name)}</h4>
          <span class="badge badge-outline" style="border-color: var(--border-subtle); color: var(--text-secondary);">
            Capacity: ${seg.capacity_mbps} Mbps
          </span>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
          <div class="form-group">
            <label>Requested Demand (Mbps):</label>
            <input type="number" class="form-control sim-demand-input" value="${seg.demand_mbps}" min="0" step="5">
          </div>
          <div class="form-group">
            <label>Priority Weight (1.0 - 5.0):</label>
            <div class="slider-group">
              <input type="range" class="slider-input sim-weight-slider" min="1.0" max="5.0" step="0.5" value="${seg.priority_weight}">
              <span class="slider-val-badge sim-weight-val">${seg.priority_weight}x</span>
            </div>
          </div>
        </div>
      `;

      // Live update slider badge
      const slider = row.querySelector(".sim-weight-slider");
      const badge = row.querySelector(".sim-weight-val");
      slider.addEventListener("input", (e) => {
        badge.textContent = `${e.target.value}x`;
      });

      el.simSegmentsContainer.appendChild(row);
    });
  }

  async function runSimulator(applyToDatabase = false) {
    const totalCap = parseFloat(el.simCapacityInput.value) || 800.0;
    const segmentPayloads = [];

    const rows = el.simSegmentsContainer.querySelectorAll("[data-seg-id]");
    rows.forEach((row) => {
      const segId = row.dataset.segId;
      const dem = parseFloat(row.querySelector(".sim-demand-input").value) || 0.0;
      const weight = parseFloat(row.querySelector(".sim-weight-slider").value) || 1.0;
      segmentPayloads.push({
        id: segId,
        demand_mbps: dem,
        priority_weight: weight
      });
    });

    try {
      const res = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          apply: applyToDatabase,
          total_capacity_mbps: totalCap,
          segments: segmentPayloads
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        showToast(errData.error || "Optimization error", "error");
        return;
      }

      const result = await res.json();
      state.previewResult = result;

      // Render explanations
      if (el.simSummaryText) {
        el.simSummaryText.textContent = result.policy_summary;
      }

      if (el.simExplanationList) {
        el.simExplanationList.innerHTML = "";
        result.segments.forEach((s) => {
          const li = document.createElement("li");
          li.innerHTML = `<strong>${escapeHtml(s.name)}:</strong> Allocated <strong>${s.allocated_mbps} Mbps</strong> of ${s.demand_mbps} Mbps (${s.satisfaction_pct}% satisfied). <span style="color:var(--text-secondary);">${escapeHtml(s.explanation)}</span>`;
          el.simExplanationList.appendChild(li);
        });
      }

      if (el.simExplanationBox) {
        el.simExplanationBox.style.display = "flex";
      }

      if (applyToDatabase) {
        showToast("Optimized policy applied to campus database!", "success");
        await loadAllData();
      } else {
        showToast("Live preview calculated. Review mathematical explanations below.", "info");
      }
    } catch (err) {
      console.error(err);
      showToast("Failed to communicate with optimization engine.", "error");
    }
  }

  function renderScenarioOptions() {
    if (!el.scenarioSelect) return;
    el.scenarioSelect.innerHTML = "";
    state.scenarios.forEach((sc) => {
      const opt = document.createElement("option");
      opt.value = sc.id;
      opt.textContent = `${sc.name} (${sc.shared_capacity_mbps} Mbps Link)`;
      el.scenarioSelect.appendChild(opt);
    });
  }

  async function handleRunExperiment() {
    const scenarioId = el.scenarioSelect.value;
    try {
      el.btnRunExperiment.disabled = true;
      el.btnRunExperiment.textContent = "Simulating Experiment...";

      const res = await fetch("/api/experiments/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario_id: scenarioId,
          notes: "Interactive experiment triggered from Web NOC"
        })
      });

      if (!res.ok) {
        const err = await res.json();
        showToast(err.error || "Experiment run failed", "error");
        return;
      }

      const exp = await res.json();
      renderExperimentComparison(exp);
      showToast(`Experiment completed: ${exp.scenario_name}`, "success");
      await loadHistory();
    } catch (err) {
      console.error(err);
      showToast("Error running experiment", "error");
    } finally {
      el.btnRunExperiment.disabled = false;
      el.btnRunExperiment.textContent = "Run Controlled Experiment";
    }
  }

  function renderExperimentComparison(exp) {
    if (!el.expComparisonWrap || !el.expTableBody) return;
    el.expComparisonWrap.style.display = "block";
    el.expTableBody.innerHTML = "";

    const baseMap = {};
    exp.baseline_segments.forEach((b) => (baseMap[b.id] = b));

    exp.optimized_segments.forEach((opt) => {
      const base = baseMap[opt.id] || {};
      const allocDelta = (opt.allocated_mbps - (base.allocated_mbps || 0)).toFixed(1);
      const satDelta = (opt.satisfaction_pct - (base.satisfaction_pct || 0)).toFixed(1);
      const latDelta = ((opt.modeled_latency_ms || 0) - (base.modeled_latency_ms || 0)).toFixed(1);

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${escapeHtml(opt.name)}</strong></td>
        <td>${opt.demand_mbps} Mbps</td>
        <td>${base.allocated_mbps || 0} Mbps <small>(${base.satisfaction_pct || 0}%)</small></td>
        <td style="color:var(--color-cyan); font-weight:600;">${opt.allocated_mbps} Mbps <small>(${opt.satisfaction_pct}%)</small></td>
        <td class="${allocDelta >= 0 ? 'delta-pos' : 'delta-neg'}">${allocDelta >= 0 ? '+' + allocDelta : allocDelta} Mbps (${satDelta >= 0 ? '+' + satDelta : satDelta}%)</td>
        <td>${base.modeled_latency_ms || 0} ms → <strong style="color:var(--color-emerald);">${opt.modeled_latency_ms || 0} ms</strong></td>
        <td><span class="badge badge-${(opt.status || 'normal').toLowerCase()}">${opt.status}</span></td>
      `;
      el.expTableBody.appendChild(tr);
    });

    const sum = exp.comparison_summary;
    if (el.expDeltaHpGain) el.expDeltaHpGain.textContent = `+${sum.improvements.high_priority_gain_pct}%`;
    if (el.expDeltaAlertsPrevented) el.expDeltaAlertsPrevented.textContent = `${sum.improvements.critical_alerts_prevented} Prevented`;
    if (el.expDeltaUnmetRed) {
      const unmetRed = (sum.baseline.total_unmet_demand_mbps - sum.optimized.total_unmet_demand_mbps).toFixed(1);
      el.expDeltaUnmetRed.textContent = `${unmetRed} Mbps`;
    }
  }

  function renderHistoryTable() {
    if (!el.expHistoryTableBody) return;
    el.expHistoryTableBody.innerHTML = "";

    if (state.history.length === 0) {
      el.expHistoryTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No prior experiments recorded yet.</td></tr>`;
      return;
    }

    state.history.forEach((h) => {
      const tr = document.createElement("tr");
      const hpGain = h.summary.improvements ? h.summary.improvements.high_priority_gain_pct : 0;
      tr.innerHTML = `
        <td>#${h.id}</td>
        <td><strong>${escapeHtml(h.scenario_name)}</strong></td>
        <td>${h.total_capacity_mbps} Mbps</td>
        <td class="delta-pos">+${hpGain}% Priority Gain</td>
        <td><small style="color:var(--text-muted);">${formatTime(h.created_at)}</small></td>
      `;
      el.expHistoryTableBody.appendChild(tr);
    });
  }

  function renderLabTab(labData) {
    if (el.labStatusBanner) {
      const isReady = labData.environment.is_lab_available;
      el.labStatusBanner.className = `alert-item ${isReady ? 'warning' : 'info'}`;
      el.labStatusBanner.style.borderLeftColor = isReady ? 'var(--color-emerald)' : 'var(--color-blue)';
      el.labStatusBanner.innerHTML = `
        <div style="font-weight: 600; font-size: 0.95rem; color: #fff;">
          Environment Inspection: <span class="badge badge-${isReady ? 'normal' : 'simulated'}">${labData.environment.status_label}</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.25rem;">
          ${escapeHtml(labData.environment.message)}
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.35rem;">
          OS: ${labData.environment.os_name} | Mininet: ${labData.environment.has_mininet ? '✓ Found' : '✗ Not detected'} | OVS: ${labData.environment.has_openvswitch ? '✓ Found' : '✗ Not detected'} | TC: ${labData.environment.has_tc ? '✓ Found' : '✗ Not detected'}
        </div>
      `;
    }

    if (el.labTcCodeBlock) {
      el.labTcCodeBlock.textContent = labData.generated_commands;
    }
  }

  // -------------------------------------------------------------
  // Theme Management (Light & Dark NOC)
  // -------------------------------------------------------------
  function getPreferredTheme() {
    const saved = localStorage.getItem("campusnet_theme");
    if (saved === "light" || saved === "dark") return saved;
    return "dark"; // Default NOC theme
  }

  function initTheme() {
    const currentTheme = getPreferredTheme();
    setTheme(currentTheme, false);
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || "dark";
    const nextTheme = current === "light" ? "dark" : "light";
    setTheme(nextTheme, true);
  }

  function setTheme(theme, notify = false) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("campusnet_theme", theme);

    if (el.themeToggleLabel) {
      el.themeToggleLabel.textContent = theme === "light" ? "Light" : "Dark";
    }

    if (el.themeToggleBtn) {
      el.themeToggleBtn.setAttribute(
        "title",
        `Current: ${theme === "light" ? "Light" : "Dark"} mode. Click to switch to ${theme === "light" ? "Dark" : "Light"} mode.`
      );
      if (theme === "light") {
        el.themeToggleBtn.classList.add("theme-light");
        el.themeToggleBtn.classList.remove("theme-dark");
      } else {
        el.themeToggleBtn.classList.add("theme-dark");
        el.themeToggleBtn.classList.remove("theme-light");
      }
    }

    applyThemeToCharts(theme);

    if (notify) {
      showToast(`Switched to ${theme === "light" ? "Light" : "Dark"} theme`, "info");
    }
  }

  function getChartThemeColors(theme) {
    const isLight = (theme || document.documentElement.getAttribute("data-theme")) === "light";
    return {
      isLight,
      textColor: isLight ? "#475569" : "#9CA3AF",
      headingColor: isLight ? "#1E293B" : "#D1D5DB",
      gridColor: isLight ? "rgba(0, 0, 0, 0.08)" : "rgba(255, 255, 255, 0.05)",
      demandBg: isLight ? "rgba(100, 116, 139, 0.35)" : "rgba(156, 163, 175, 0.45)",
      demandBorder: isLight ? "#64748B" : "#9CA3AF"
    };
  }

  function applyThemeToCharts(theme) {
    if (!window.Chart) return;
    const colors = getChartThemeColors(theme);

    // 1. Allocation Chart
    if (state.charts.alloc) {
      const c = state.charts.alloc;
      if (c.data?.datasets?.[0]) {
        c.data.datasets[0].backgroundColor = colors.demandBg;
        c.data.datasets[0].borderColor = colors.demandBorder;
      }
      if (c.options.plugins?.legend?.labels) {
        c.options.plugins.legend.labels.color = colors.headingColor;
      }
      if (c.options.scales?.x) {
        if (c.options.scales.x.ticks) c.options.scales.x.ticks.color = colors.textColor;
        if (c.options.scales.x.grid) c.options.scales.x.grid.color = colors.gridColor;
      }
      if (c.options.scales?.y) {
        if (c.options.scales.y.ticks) c.options.scales.y.ticks.color = colors.textColor;
        if (c.options.scales.y.grid) c.options.scales.y.grid.color = colors.gridColor;
        if (c.options.scales.y.title) c.options.scales.y.title.color = colors.textColor;
      }
      c.update();
    }

    // 2. Utilization Chart
    if (state.charts.util) {
      const c = state.charts.util;
      if (c.options.scales?.x) {
        if (c.options.scales.x.ticks) c.options.scales.x.ticks.color = colors.textColor;
        if (c.options.scales.x.grid) c.options.scales.x.grid.color = colors.gridColor;
        if (c.options.scales.x.title) c.options.scales.x.title.color = colors.textColor;
      }
      if (c.options.scales?.y) {
        if (c.options.scales.y.ticks) c.options.scales.y.ticks.color = colors.headingColor;
      }
      c.update();
    }

    // 3. Telemetry Chart
    if (state.charts.telemetry) {
      const c = state.charts.telemetry;
      if (c.options.plugins?.legend?.labels) {
        c.options.plugins.legend.labels.color = colors.headingColor;
      }
      if (c.options.scales?.x) {
        if (c.options.scales.x.ticks) c.options.scales.x.ticks.color = colors.textColor;
        if (c.options.scales.x.grid) c.options.scales.x.grid.color = colors.gridColor;
      }
      if (c.options.scales?.yLatency) {
        if (c.options.scales.yLatency.grid) c.options.scales.yLatency.grid.color = colors.gridColor;
      }
      c.update();
    }
  }

  // -------------------------------------------------------------
  // Chart.js Visualizations
  // -------------------------------------------------------------
  function updateCharts() {
    if (!window.Chart) return;

    const colors = getChartThemeColors();
    const labels = state.segments.map((s) => s.name);
    const demands = state.segments.map((s) => s.demand_mbps);
    const allocs = state.segments.map((s) => s.allocated_mbps);
    const utils = state.segments.map((s) => s.utilization_pct);

    // 1. Allocation vs Demand Chart
    const ctxAlloc = document.getElementById("chart-allocations");
    if (ctxAlloc) {
      if (state.charts.alloc) {
        state.charts.alloc.data.labels = labels;
        state.charts.alloc.data.datasets[0].data = demands;
        state.charts.alloc.data.datasets[0].backgroundColor = colors.demandBg;
        state.charts.alloc.data.datasets[0].borderColor = colors.demandBorder;
        state.charts.alloc.data.datasets[1].data = allocs;
        state.charts.alloc.update();
      } else {
        state.charts.alloc = new Chart(ctxAlloc, {
          type: "bar",
          data: {
            labels: labels,
            datasets: [
              {
                label: "Requested Demand (Mbps)",
                data: demands,
                backgroundColor: colors.demandBg,
                borderColor: colors.demandBorder,
                borderWidth: 1,
                borderRadius: 4
              },
              {
                label: "Allocated Bandwidth (Mbps)",
                data: allocs,
                backgroundColor: "rgba(6, 182, 212, 0.7)",
                borderColor: "#06B6D4",
                borderWidth: 1,
                borderRadius: 4
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { labels: { color: colors.headingColor, font: { family: "Inter" } } }
            },
            scales: {
              x: { ticks: { color: colors.textColor }, grid: { color: colors.gridColor } },
              y: {
                title: { display: true, text: "Bandwidth (Mbps)", color: colors.textColor },
                ticks: { color: colors.textColor },
                grid: { color: colors.gridColor }
              }
            }
          }
        });
      }
    }

    // 2. Utilization vs Thresholds Chart
    const ctxUtil = document.getElementById("chart-utilization");
    if (ctxUtil) {
      const bgColors = utils.map((u) => (u >= 85 ? "rgba(239, 68, 68, 0.8)" : u >= 70 ? "rgba(245, 158, 11, 0.8)" : "rgba(16, 185, 129, 0.8)"));

      if (state.charts.util) {
        state.charts.util.data.labels = labels;
        state.charts.util.data.datasets[0].data = utils;
        state.charts.util.data.datasets[0].backgroundColor = bgColors;
        state.charts.util.update();
      } else {
        state.charts.util = new Chart(ctxUtil, {
          type: "bar",
          data: {
            labels: labels,
            datasets: [
              {
                label: "Link Utilization (%)",
                data: utils,
                backgroundColor: bgColors,
                borderRadius: 4
              }
            ]
          },
          options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false }
            },
            scales: {
              x: {
                max: 100,
                ticks: { color: colors.textColor },
                grid: { color: colors.gridColor },
                title: { display: true, text: "Utilization (%)", color: colors.textColor }
              },
              y: { ticks: { color: colors.headingColor }, grid: { display: false } }
            }
          }
        });
      }
    }
  }

  function updateTelemetryChart() {
    if (!window.Chart || state.measurements.length === 0) return;

    const ctxTelemetry = document.getElementById("chart-telemetry");
    if (!ctxTelemetry) return;

    const colors = getChartThemeColors();
    const labels = state.measurements.map((m) => `${m.segment_name.substring(0, 8)} (${m.timestamp.substring(11, 16)})`);
    const latencies = state.measurements.map((m) => m.latency_ms);
    const losses = state.measurements.map((m) => m.packet_loss_pct);

    if (state.charts.telemetry) {
      state.charts.telemetry.data.labels = labels;
      state.charts.telemetry.data.datasets[0].data = latencies;
      state.charts.telemetry.data.datasets[1].data = losses;
      state.charts.telemetry.update();
    } else {
      state.charts.telemetry = new Chart(ctxTelemetry, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Latency (ms)",
              data: latencies,
              borderColor: "#38BDF8",
              backgroundColor: "rgba(56, 189, 248, 0.1)",
              yAxisID: "yLatency",
              tension: 0.3,
              fill: true
            },
            {
              label: "Packet Loss (%)",
              data: losses,
              borderColor: "#EF4444",
              backgroundColor: "rgba(239, 68, 68, 0.1)",
              yAxisID: "yLoss",
              tension: 0.3,
              fill: false
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: colors.headingColor } }
          },
          scales: {
            x: { ticks: { color: colors.textColor, maxRotation: 45 }, grid: { color: colors.gridColor } },
            yLatency: {
              type: "linear",
              position: "left",
              ticks: { color: "#38BDF8" },
              title: { display: true, text: "Latency (ms)", color: "#38BDF8" },
              grid: { color: colors.gridColor }
            },
            yLoss: {
              type: "linear",
              position: "right",
              ticks: { color: "#EF4444" },
              title: { display: true, text: "Packet Loss (%)", color: "#EF4444" },
              grid: { drawOnChartArea: false }
            }
          }
        }
      });
    }
  }

  // -------------------------------------------------------------
  // CSV Upload & Reset Actions
  // -------------------------------------------------------------
  async function handleCsvUpload() {
    const file = el.csvFileInput.files[0];
    if (!file) {
      showToast("Please choose a .csv file to upload.", "error");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    el.btnUploadCsv.disabled = true;
    el.btnUploadCsv.textContent = "Validating...";

    try {
      const res = await fetch("/api/import/csv", {
        method: "POST",
        body: formData
      });

      const data = await res.json();
      if (!res.ok) {
        el.importStatusMsg.style.color = "var(--color-rose)";
        el.importStatusMsg.textContent = data.error || "CSV Validation Failed";
        showToast("CSV validation rejected file.", "error");
        return;
      }

      el.importStatusMsg.style.color = "var(--color-emerald)";
      el.importStatusMsg.textContent = `✓ Ingested ${data.rows_imported} aggregate rows as IMPORTED data provenance.`;
      showToast(`Imported ${data.rows_imported} rows!`, "success");

      setTimeout(() => {
        el.importModal.classList.remove("active");
        loadAllData();
      }, 1200);
    } catch (err) {
      console.error(err);
      el.importStatusMsg.style.color = "var(--color-rose)";
      el.importStatusMsg.textContent = "Error communicating with server.";
    } finally {
      el.btnUploadCsv.disabled = false;
      el.btnUploadCsv.textContent = "Upload & Ingest";
    }
  }

  async function resetDemo() {
    if (!confirm("Reset network model back to calibrated baseline demonstration dataset?")) return;

    try {
      const res = await fetch("/api/demo/reset", { method: "POST" });
      if (res.ok) {
        showToast("Demo state reset to calibrated baseline.", "success");
        await loadAllData();
      }
    } catch (err) {
      console.error(err);
      showToast("Reset failed.", "error");
    }
  }

  function startAutoRefresh() {
    state.autoRefreshInterval = setInterval(() => {
      if (!state.isPaused) {
        loadAllData();
      }
    }, 15000);
  }

  function updateLastUpdatedTimestamp() {
    if (el.lastUpdated) {
      const d = new Date();
      el.lastUpdated.textContent = `Synced: ${d.toLocaleTimeString()}`;
    }
  }

  // -------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------
  function showToast(message, type = "info") {
    if (!el.toastContainer) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    const icon = type === "success" ? "✓" : (type === "error" ? "⚠" : "ℹ");
    toast.innerHTML = `<strong>${icon}</strong> <span>${escapeHtml(message)}</span>`;
    el.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatTime(isoString) {
    if (!isoString) return "";
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return isoString;
    }
  }

  // Bootstrap when DOM is ready
  document.addEventListener("DOMContentLoaded", init);
})();
