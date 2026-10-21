/**
 * CampusNet: Authority & Administration Module Controller
 * Manages RBAC, policy approval workflow, audit trail, user accounts, and reports.
 */

(function () {
  "use strict";

  const authState = {
    currentUser: null,
    policies: [],
    auditLogs: [],
    users: [],
    settings: {},
    activeSubtab: "subtab-policies"
  };

  const dom = {};

  function init() {
    cacheDom();
    bindEvents();
    checkUserSession();
  }

  function cacheDom() {
    // Header & User Session
    dom.userSessionWidget = document.getElementById("user-session-widget");
    dom.loginModal = document.getElementById("login-modal");
    dom.btnLoginModalClose = document.getElementById("btn-close-login-modal");
    dom.loginForm = document.getElementById("login-form");
    dom.loginUsernameInput = document.getElementById("login-username");
    dom.loginPasswordInput = document.getElementById("login-password");
    dom.loginStatusMsg = document.getElementById("login-status-msg");
    dom.presetChips = document.querySelectorAll(".preset-role-chip");

    // Sub-Navigation Tabs
    dom.subtabBtns = document.querySelectorAll(".sub-tab-btn");
    dom.subPanes = document.querySelectorAll(".admin-sub-pane");

    // Policy Approval Elements
    dom.policiesTableBody = document.getElementById("policies-table-body");
    dom.policyStatusFilter = document.getElementById("policy-status-filter");
    dom.btnRefreshPolicies = document.getElementById("btn-refresh-policies");
    dom.btnOpenProposeModal = document.getElementById("btn-open-propose-modal");
    dom.proposeModal = document.getElementById("propose-modal");
    dom.btnCloseProposeModal = document.getElementById("btn-close-propose-modal");
    dom.btnCancelPropose = document.getElementById("btn-cancel-propose");
    dom.btnSubmitProposal = document.getElementById("btn-submit-proposal");
    dom.proposeNameInput = document.getElementById("propose-name");
    dom.proposeDescInput = document.getElementById("propose-desc");
    dom.proposeTargetEnv = document.getElementById("propose-target-env");

    // Reject Modal
    dom.rejectModal = document.getElementById("reject-modal");
    dom.btnCloseRejectModal = document.getElementById("btn-close-reject-modal");
    dom.btnCancelReject = document.getElementById("btn-cancel-reject");
    dom.btnConfirmReject = document.getElementById("btn-confirm-reject");
    dom.rejectReasonInput = document.getElementById("reject-reason");
    dom.rejectPolicyIdInput = document.getElementById("reject-policy-id");

    // Policy Details Modal
    dom.policyDetailsModal = document.getElementById("policy-details-modal");
    dom.btnClosePolicyDetails = document.getElementById("btn-close-policy-details");
    dom.policyDetailsContent = document.getElementById("policy-details-content");

    // Audit Trail Elements
    dom.auditTableBody = document.getElementById("audit-table-body");
    dom.auditActionFilter = document.getElementById("audit-action-filter");
    dom.auditSearchInput = document.getElementById("audit-search-input");
    dom.btnRefreshAudit = document.getElementById("btn-refresh-audit");
    dom.btnExportAuditCsv = document.getElementById("btn-export-audit-csv");

    // User Administration Elements
    dom.usersTableBody = document.getElementById("users-table-body");
    dom.btnOpenCreateUserModal = document.getElementById("btn-open-create-user-modal");
    dom.createUserModal = document.getElementById("create-user-modal");
    dom.btnCloseCreateUserModal = document.getElementById("btn-close-create-user-modal");
    dom.btnCancelCreateUser = document.getElementById("btn-cancel-create-user");
    dom.btnSubmitCreateUser = document.getElementById("btn-submit-create-user");
    dom.createUsernameInput = document.getElementById("create-username");
    dom.createFullNameInput = document.getElementById("create-full-name");
    dom.createEmailInput = document.getElementById("create-email");
    dom.createPasswordInput = document.getElementById("create-password");
    dom.createRoleSelect = document.getElementById("create-role");

    // Reset Password Modal
    dom.resetPasswordModal = document.getElementById("reset-password-modal");
    dom.btnCloseResetPassword = document.getElementById("btn-close-reset-password");
    dom.btnCancelResetPassword = document.getElementById("btn-cancel-reset-password");
    dom.btnConfirmResetPassword = document.getElementById("btn-confirm-reset-password");
    dom.resetPasswordUserId = document.getElementById("reset-password-user-id");
    dom.resetPasswordInput = document.getElementById("reset-password-input");

    // Settings & Thresholds Elements
    dom.settingWarnUtil = document.getElementById("setting-warn-util");
    dom.settingCritUtil = document.getElementById("setting-crit-util");
    dom.settingWarnLat = document.getElementById("setting-warn-lat");
    dom.settingCritLat = document.getElementById("setting-crit-lat");
    dom.settingWarnLoss = document.getElementById("setting-warn-loss");
    dom.settingCritLoss = document.getElementById("setting-crit-loss");
    dom.settingEnforcement = document.getElementById("setting-enforcement-toggle");
    dom.btnSaveSettings = document.getElementById("btn-save-settings");

    // Reports Elements
    dom.btnDownloadTelemetry = document.getElementById("btn-download-telemetry");
    dom.btnDownloadPolicies = document.getElementById("btn-download-policies");
    dom.btnDownloadAudit = document.getElementById("btn-download-audit");
    dom.btnViewExecutive = document.getElementById("btn-view-executive");
  }

  function bindEvents() {
    // Sub-tab Navigation
    dom.subtabBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = btn.dataset.subtab;
        switchSubtab(target);
      });
    });

    // Preset Roles Fast Login
    dom.presetChips.forEach((chip) => {
      chip.addEventListener("click", () => {
        const u = chip.dataset.user;
        const p = chip.dataset.pass;
        if (dom.loginUsernameInput) dom.loginUsernameInput.value = u;
        if (dom.loginPasswordInput) dom.loginPasswordInput.value = p;
        handleLoginSubmit();
      });
    });

    // Login Modal Triggers
    if (dom.loginForm) {
      dom.loginForm.addEventListener("submit", (e) => {
        e.preventDefault();
        handleLoginSubmit();
      });
    }

    if (dom.btnLoginModalClose) {
      dom.btnLoginModalClose.addEventListener("click", () => {
        dom.loginModal.classList.remove("active");
      });
    }

    // Policy Approval Events
    if (dom.policyStatusFilter) {
      dom.policyStatusFilter.addEventListener("change", loadPolicies);
    }
    if (dom.btnRefreshPolicies) {
      dom.btnRefreshPolicies.addEventListener("click", loadPolicies);
    }
    if (dom.btnOpenProposeModal) {
      dom.btnOpenProposeModal.addEventListener("click", openProposeModal);
    }
    if (dom.btnCloseProposeModal) {
      dom.btnCloseProposeModal.addEventListener("click", () => dom.proposeModal.classList.remove("active"));
    }
    if (dom.btnCancelPropose) {
      dom.btnCancelPropose.addEventListener("click", () => dom.proposeModal.classList.remove("active"));
    }
    if (dom.btnSubmitProposal) {
      dom.btnSubmitProposal.addEventListener("click", handleProposeSubmit);
    }

    // Reject Modal Events
    if (dom.btnCloseRejectModal) {
      dom.btnCloseRejectModal.addEventListener("click", () => dom.rejectModal.classList.remove("active"));
    }
    if (dom.btnCancelReject) {
      dom.btnCancelReject.addEventListener("click", () => dom.rejectModal.classList.remove("active"));
    }
    if (dom.btnConfirmReject) {
      dom.btnConfirmReject.addEventListener("click", handleConfirmReject);
    }

    // Policy Details Modal
    if (dom.btnClosePolicyDetails) {
      dom.btnClosePolicyDetails.addEventListener("click", () => dom.policyDetailsModal.classList.remove("active"));
    }

    // Audit Trail Events
    if (dom.auditActionFilter) {
      dom.auditActionFilter.addEventListener("change", loadAuditLogs);
    }
    if (dom.auditSearchInput) {
      let debounceTimer;
      dom.auditSearchInput.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(loadAuditLogs, 300);
      });
    }
    if (dom.btnRefreshAudit) {
      dom.btnRefreshAudit.addEventListener("click", loadAuditLogs);
    }
    if (dom.btnExportAuditCsv) {
      dom.btnExportAuditCsv.addEventListener("click", () => {
        window.location.href = "/api/audit-logs/export";
      });
    }

    // User Administration Events
    if (dom.btnOpenCreateUserModal) {
      dom.btnOpenCreateUserModal.addEventListener("click", () => {
        dom.createUserModal.classList.add("active");
      });
    }
    if (dom.btnCloseCreateUserModal) {
      dom.btnCloseCreateUserModal.addEventListener("click", () => dom.createUserModal.classList.remove("active"));
    }
    if (dom.btnCancelCreateUser) {
      dom.btnCancelCreateUser.addEventListener("click", () => dom.createUserModal.classList.remove("active"));
    }
    if (dom.btnSubmitCreateUser) {
      dom.btnSubmitCreateUser.addEventListener("click", handleCreateUserSubmit);
    }

    // Reset Password Events
    if (dom.btnCloseResetPassword) {
      dom.btnCloseResetPassword.addEventListener("click", () => dom.resetPasswordModal.classList.remove("active"));
    }
    if (dom.btnCancelResetPassword) {
      dom.btnCancelResetPassword.addEventListener("click", () => dom.resetPasswordModal.classList.remove("active"));
    }
    if (dom.btnConfirmResetPassword) {
      dom.btnConfirmResetPassword.addEventListener("click", handleConfirmResetPassword);
    }

    // Settings Events
    if (dom.btnSaveSettings) {
      dom.btnSaveSettings.addEventListener("click", handleSaveSettings);
    }

    // Reports Events
    if (dom.btnDownloadTelemetry) {
      dom.btnDownloadTelemetry.addEventListener("click", () => {
        window.location.href = "/api/reports/telemetry";
      });
    }
    if (dom.btnDownloadPolicies) {
      dom.btnDownloadPolicies.addEventListener("click", () => {
        window.location.href = "/api/reports/policies";
      });
    }
    if (dom.btnDownloadAudit) {
      dom.btnDownloadAudit.addEventListener("click", () => {
        window.location.href = "/api/reports/audit";
      });
    }
    if (dom.btnViewExecutive) {
      dom.btnViewExecutive.addEventListener("click", () => {
        window.open("/api/reports/executive", "_blank");
      });
    }
  }

  // -------------------------------------------------------------
  // Sub-Navigation Tabs Switching
  // -------------------------------------------------------------
  function switchSubtab(subtabId) {
    authState.activeSubtab = subtabId;
    dom.subtabBtns.forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.subtab === subtabId);
    });
    dom.subPanes.forEach((pane) => {
      pane.classList.toggle("active", pane.id === subtabId);
    });

    if (subtabId === "subtab-policies") loadPolicies();
    else if (subtabId === "subtab-audit") loadAuditLogs();
    else if (subtabId === "subtab-users") loadUsers();
    else if (subtabId === "subtab-settings") loadSettings();
  }

  // -------------------------------------------------------------
  // Authentication & Session
  // -------------------------------------------------------------
  async function checkUserSession() {
    try {
      const res = await fetch("/api/auth/me");
      if (!res.ok) return;
      const data = await res.json();
      if (data.authenticated) {
        authState.currentUser = data.user;
      } else {
        authState.currentUser = null;
      }
      renderUserWidget();
      applyRoleUiPermissions();
      loadPolicies();
    } catch (err) {
      console.error("Session check error:", err);
    }
  }

  function renderUserWidget() {
    if (!dom.userSessionWidget) return;
    const u = authState.currentUser;

    if (u) {
      const roleBadgeClass = u.role === "admin" ? "badge-admin" : (u.role === "netadmin" ? "badge-netadmin" : "badge-readonly");
      const roleLabel = u.role === "admin" ? "Admin" : (u.role === "netadmin" ? "NetAdmin" : "Authority");

      dom.userSessionWidget.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.5rem; background: rgba(31, 41, 55, 0.7); border: 1px solid var(--border-subtle); padding: 0.25rem 0.6rem; border-radius: var(--radius-md);">
          <span style="font-size: 1.1rem;">👤</span>
          <div style="line-height: 1.2;">
            <div style="font-size: 0.8rem; font-weight: 700; color: #fff;">${escapeHtml(u.full_name || u.username)}</div>
            <span class="badge ${roleBadgeClass}" style="font-size: 0.65rem; padding: 0.1rem 0.35rem;">${roleLabel}</span>
          </div>
        </div>
        <button id="btn-logout" class="btn btn-outline btn-sm" title="Sign Out">Sign Out</button>
      `;

      const btnLogout = document.getElementById("btn-logout");
      if (btnLogout) {
        btnLogout.addEventListener("click", handleLogout);
      }
    } else {
      dom.userSessionWidget.innerHTML = `
        <button id="btn-open-login" class="btn btn-primary" title="Sign In to Operations &amp; Administration">
          <span>🔒</span> Sign In
        </button>
      `;
      const btnOpen = document.getElementById("btn-open-login");
      if (btnOpen) {
        btnOpen.addEventListener("click", () => {
          dom.loginModal.classList.add("active");
        });
      }
    }
  }

  async function handleLoginSubmit() {
    const username = dom.loginUsernameInput.value.trim();
    const password = dom.loginPasswordInput.value;

    if (!username || !password) {
      showLoginError("Please enter both username and password.");
      return;
    }

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();

      if (!res.ok) {
        showLoginError(data.error || "Login failed.");
        return;
      }

      authState.currentUser = data.user;
      dom.loginModal.classList.remove("active");
      dom.loginForm.reset();
      dom.loginStatusMsg.textContent = "";

      renderUserWidget();
      applyRoleUiPermissions();
      switchSubtab(authState.activeSubtab);
      showToast(`Logged in as ${data.user.full_name} (${data.user.role})`, "success");
    } catch (err) {
      console.error("Login request failed:", err);
      showLoginError("Error connecting to authorization server.");
    }
  }

  async function handleLogout() {
    try {
      await fetch("/api/auth/logout", { method: "POST" });
      authState.currentUser = null;
      renderUserWidget();
      applyRoleUiPermissions();
      showToast("Signed out successfully.", "info");
      loadPolicies();
    } catch (err) {
      console.error("Logout error:", err);
    }
  }

  function showLoginError(msg) {
    if (!dom.loginStatusMsg) return;
    dom.loginStatusMsg.style.color = "var(--color-rose)";
    dom.loginStatusMsg.textContent = msg;
  }

  function applyRoleUiPermissions() {
    const u = authState.currentUser;
    const role = u ? u.role : "anonymous";

    // Non-admins cannot add users or save settings
    if (dom.btnOpenCreateUserModal) {
      dom.btnOpenCreateUserModal.style.display = role === "admin" ? "inline-flex" : "none";
    }
    if (dom.btnSaveSettings) {
      dom.btnSaveSettings.disabled = role !== "admin";
      dom.btnSaveSettings.title = role === "admin" ? "Save dynamic configuration" : "Administrator authorization required";
    }
    if (dom.btnOpenProposeModal) {
      dom.btnOpenProposeModal.style.display = (role === "admin" || role === "netadmin") ? "inline-flex" : "none";
    }
  }

  // -------------------------------------------------------------
  // Policy Approval Workflow
  // -------------------------------------------------------------
  async function loadPolicies() {
    if (!dom.policiesTableBody) return;
    const filter = dom.policyStatusFilter ? dom.policyStatusFilter.value : "";
    const url = filter ? `/api/policies?status=${encodeURIComponent(filter)}` : "/api/policies";

    try {
      const res = await fetch(url);
      if (res.status === 401) {
        dom.policiesTableBody.innerHTML = `
          <tr>
            <td colspan="8" style="text-align: center; color: var(--color-amber); padding: 2rem;">
              🔒 Please <strong><a href="#" id="link-prompt-login" style="color: var(--color-cyan); text-decoration: underline;">Sign In</a></strong> to view optimization policies.
            </td>
          </tr>
        `;
        const link = document.getElementById("link-prompt-login");
        if (link) link.addEventListener("click", () => dom.loginModal.classList.add("active"));
        return;
      }
      if (!res.ok) return;

      const data = await res.json();
      authState.policies = data.policies || [];
      renderPoliciesTable();
    } catch (err) {
      console.error("Error loading policies:", err);
    }
  }

  function renderPoliciesTable() {
    const u = authState.currentUser;
    const role = u ? u.role : "anonymous";
    const policies = authState.policies;

    if (!policies.length) {
      dom.policiesTableBody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">
            No optimization policies found matching the filter.
          </td>
        </tr>
      `;
      return;
    }

    let rowsHtml = "";
    policies.forEach((p) => {
      const statusBadge = `<span class="badge status-${p.status.toLowerCase()}">${p.status}</span>`;
      const envBadge = `<span style="font-family: var(--font-mono); font-size: 0.75rem; color: ${p.target_environment === 'PRODUCTION' ? 'var(--color-rose)' : 'var(--color-cyan)'}; font-weight: 600;">${p.target_environment}</span>`;

      // Role-aware action buttons
      let actionButtons = `<button class="btn btn-outline btn-sm btn-view-policy" data-id="${p.id}">Inspect</button>`;

      if (p.status === "PENDING" && role === "admin") {
        actionButtons += `
          <button class="btn btn-primary btn-sm btn-approve-policy" data-id="${p.id}">Approve</button>
          <button class="btn btn-danger btn-sm btn-reject-policy" data-id="${p.id}">Reject</button>
        `;
      } else if (p.status === "APPROVED" && (role === "admin" || role === "netadmin")) {
        actionButtons += `
          <button class="btn btn-success btn-sm btn-apply-policy" data-id="${p.id}" style="background: rgba(16, 185, 129, 0.2); border: 1px solid var(--color-emerald); color: #34D399;">
            Execute in Testbed
          </button>
        `;
      } else if (p.status === "APPLIED" && (role === "admin" || role === "netadmin")) {
        actionButtons += `
          <button class="btn btn-outline btn-sm btn-rollback-policy" data-id="${p.id}" style="color: #C084FC; border-color: rgba(168, 85, 247, 0.5);">
            ↺ Rollback
          </button>
        `;
      }

      rowsHtml += `
        <tr>
          <td style="font-family: var(--font-mono); font-weight: 700;">#${p.id}</td>
          <td>
            <strong>${escapeHtml(p.name)}</strong>
            <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(p.description || '')}</div>
            ${p.rejection_reason ? `<div style="font-size: 0.725rem; color: var(--color-rose); margin-top: 2px;"><em>Rejection note: ${escapeHtml(p.rejection_reason)}</em></div>` : ''}
          </td>
          <td>${envBadge}</td>
          <td>${statusBadge}</td>
          <td>${escapeHtml(p.proposed_by)}</td>
          <td>${escapeHtml(p.reviewed_by || '—')}</td>
          <td>${escapeHtml(p.applied_by || '—')}</td>
          <td><div class="btn-group">${actionButtons}</div></td>
        </tr>
      `;
    });

    dom.policiesTableBody.innerHTML = rowsHtml;
    bindPolicyRowButtons();
  }

  function bindPolicyRowButtons() {
    // Inspect Details
    dom.policiesTableBody.querySelectorAll(".btn-view-policy").forEach((btn) => {
      btn.addEventListener("click", () => {
        const pol = authState.policies.find(p => p.id == btn.dataset.id);
        if (pol) showPolicyDetailsModal(pol);
      });
    });

    // Approve
    dom.policiesTableBody.querySelectorAll(".btn-approve-policy").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        if (!confirm(`Authorize and approve Policy #${id}?`)) return;
        try {
          const res = await fetch(`/api/policies/${id}/approve`, { method: "POST" });
          const data = await res.json();
          if (res.ok) {
            showToast(`Policy #${id} approved successfully!`, "success");
            loadPolicies();
          } else {
            showToast(data.error || "Approval failed.", "error");
          }
        } catch (err) {
          console.error(err);
        }
      });
    });

    // Reject
    dom.policiesTableBody.querySelectorAll(".btn-reject-policy").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        if (dom.rejectPolicyIdInput) dom.rejectPolicyIdInput.value = id;
        if (dom.rejectReasonInput) dom.rejectReasonInput.value = "";
        dom.rejectModal.classList.add("active");
      });
    });

    // Apply / Execute
    dom.policiesTableBody.querySelectorAll(".btn-apply-policy").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        if (!confirm(`Execute Policy #${id} in the isolated test network?`)) return;
        try {
          const res = await fetch(`/api/policies/${id}/apply`, { method: "POST" });
          const data = await res.json();
          if (res.ok) {
            showToast(`Policy #${id} applied in ${data.policy.target_environment}!`, "success");
            loadPolicies();
            if (typeof window.CampusNetRefresh === "function") window.CampusNetRefresh();
          } else {
            showToast(data.error || "Application failed.", "error");
          }
        } catch (err) {
          console.error(err);
        }
      });
    });

    // Rollback
    dom.policiesTableBody.querySelectorAll(".btn-rollback-policy").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        if (!confirm(`Rollback Policy #${id} and restore previous network allocations?`)) return;
        try {
          const res = await fetch(`/api/policies/${id}/rollback`, { method: "POST" });
          const data = await res.json();
          if (res.ok) {
            showToast(`Policy #${id} rolled back. Previous allocations restored.`, "info");
            loadPolicies();
            if (typeof window.CampusNetRefresh === "function") window.CampusNetRefresh();
          } else {
            showToast(data.error || "Rollback failed.", "error");
          }
        } catch (err) {
          console.error(err);
        }
      });
    });
  }

  function openProposeModal() {
    dom.proposeNameInput.value = `Peak Optimization Plan - ${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
    dom.proposeDescInput.value = "Algorithmic WFQ-PF bandwidth distribution proposal generated for operations review.";
    dom.proposeModal.classList.add("active");
  }

  async function handleProposeSubmit() {
    const name = dom.proposeNameInput.value.trim();
    const desc = dom.proposeDescInput.value.trim();
    const targetEnv = dom.proposeTargetEnv.value;

    if (!name) {
      showToast("Policy name is required.", "error");
      return;
    }

    // Fetch current segment states to construct proposal policy payload
    try {
      const segRes = await fetch("/api/segments");
      const segData = await segRes.json();
      const segments = segData.segments || [];

      // Run WFQ-PF preview
      const optRes = await fetch("/api/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apply: false, segments })
      });
      const optData = await optRes.json();

      const payload = {
        name,
        description: desc,
        target_environment: targetEnv,
        policy_data: {
          total_allocated_mbps: optData.total_allocated_mbps,
          policy_summary: optData.policy_summary,
          algorithm: "WFQ-PF",
          segments: optData.segments
        }
      };

      const propRes = await fetch("/api/policies/propose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const resData = await propRes.json();

      if (propRes.ok) {
        showToast(`Policy proposed! Current status: PENDING.`, "success");
        dom.proposeModal.classList.remove("active");
        loadPolicies();
      } else {
        showToast(resData.error || "Proposal failed.", "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Failed to propose policy.", "error");
    }
  }

  async function handleConfirmReject() {
    const id = dom.rejectPolicyIdInput.value;
    const reason = dom.rejectReasonInput.value.trim();

    if (!reason) {
      showToast("Please provide an explicit rejection reason.", "error");
      return;
    }

    try {
      const res = await fetch(`/api/policies/${id}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason })
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`Policy #${id} rejected.`, "info");
        dom.rejectModal.classList.remove("active");
        loadPolicies();
      } else {
        showToast(data.error || "Rejection error.", "error");
      }
    } catch (err) {
      console.error(err);
    }
  }

  function showPolicyDetailsModal(p) {
    if (!dom.policyDetailsContent) return;
    const data = p.policy_data || {};
    const segments = data.segments || [];

    let segRows = "";
    segments.forEach(s => {
      segRows += `
        <tr>
          <td><strong>${escapeHtml(s.name || s.id)}</strong></td>
          <td>${s.demand_mbps || '—'} Mbps</td>
          <td><span style="color: var(--color-cyan); font-weight:700;">${s.allocated_mbps} Mbps</span></td>
          <td>${s.priority_weight || '—'}x</td>
        </tr>
      `;
    });

    dom.policyDetailsContent.innerHTML = `
      <div style="margin-bottom: 1rem;">
        <h4 style="color:#fff; font-size:1.1rem; margin-bottom: 0.25rem;">Policy #${p.id}: ${escapeHtml(p.name)}</h4>
        <div style="font-size: 0.85rem; color: var(--text-secondary);">${escapeHtml(p.description || '')}</div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; margin-bottom: 1.25rem; font-size: 0.825rem;">
        <div style="background: rgba(31, 41, 55, 0.7); padding: 0.5rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
          <span style="color: var(--text-muted);">Status:</span> <strong style="color: #fff;">${p.status}</strong>
        </div>
        <div style="background: rgba(31, 41, 55, 0.7); padding: 0.5rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
          <span style="color: var(--text-muted);">Environment:</span> <strong style="color: var(--color-cyan);">${p.target_environment}</strong>
        </div>
        <div style="background: rgba(31, 41, 55, 0.7); padding: 0.5rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
          <span style="color: var(--text-muted);">Proposed By:</span> <strong style="color: #fff;">${escapeHtml(p.proposed_by)}</strong>
        </div>
      </div>

      <table class="data-table" style="font-size: 0.85rem;">
        <thead>
          <tr>
            <th>Segment</th>
            <th>Requested Demand</th>
            <th>Allocated QoS Slice</th>
            <th>Priority Weight</th>
          </tr>
        </thead>
        <tbody>
          ${segRows || '<tr><td colspan="4">No segment data.</td></tr>'}
        </tbody>
      </table>
    `;
    dom.policyDetailsModal.classList.add("active");
  }

  // -------------------------------------------------------------
  // Audit Trail & Governance
  // -------------------------------------------------------------
  async function loadAuditLogs() {
    if (!dom.auditTableBody) return;
    const action = dom.auditActionFilter ? dom.auditActionFilter.value : "";
    const search = dom.auditSearchInput ? dom.auditSearchInput.value.trim() : "";

    let url = "/api/audit-logs?limit=50";
    if (action) url += `&action=${encodeURIComponent(action)}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;

    try {
      const res = await fetch(url);
      if (res.status === 401) {
        dom.auditTableBody.innerHTML = `
          <tr><td colspan="5" style="text-align: center; color: var(--color-amber); padding: 1.5rem;">🔒 Sign in to view immutable audit trail.</td></tr>
        `;
        return;
      }
      if (!res.ok) return;

      const data = await res.json();
      authState.auditLogs = data.logs || [];
      renderAuditLogsTable();
    } catch (err) {
      console.error("Error loading audit trail:", err);
    }
  }

  function renderAuditLogsTable() {
    const logs = authState.auditLogs;
    if (!logs.length) {
      dom.auditTableBody.innerHTML = `
        <tr><td colspan="5" style="text-align:center; color:var(--text-muted); padding:1.5rem;">No audit events recorded matching current filters.</td></tr>
      `;
      return;
    }

    let rowsHtml = "";
    logs.forEach(l => {
      let actionClass = "policy";
      if (l.action.includes("LOGIN") || l.action.includes("LOGOUT")) actionClass = "login";
      else if (l.action.includes("CONFIG") || l.action.includes("THRESHOLD")) actionClass = "config";
      else if (l.action.includes("DELETE") || l.action.includes("UNAUTHORIZED")) actionClass = "danger";

      const timeStr = l.timestamp ? new Date(l.timestamp).toLocaleString() : "—";

      rowsHtml += `
        <tr>
          <td style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">${timeStr}</td>
          <td>
            <strong>${escapeHtml(l.username)}</strong>
            <span class="badge ${l.role === 'admin' ? 'badge-admin' : (l.role === 'netadmin' ? 'badge-netadmin' : 'badge-readonly')}" style="font-size:0.65rem; margin-left:4px;">${l.role}</span>
          </td>
          <td><span class="action-badge ${actionClass}">${l.action}</span></td>
          <td style="font-family: var(--font-mono); font-size: 0.75rem;">${escapeHtml(l.ip_address || '127.0.0.1')}</td>
          <td style="font-size: 0.8rem; color: var(--text-secondary); max-width: 400px; word-break: break-word;">${escapeHtml(l.details)}</td>
        </tr>
      `;
    });

    dom.auditTableBody.innerHTML = rowsHtml;
  }

  // -------------------------------------------------------------
  // User Accounts & Role Management
  // -------------------------------------------------------------
  async function loadUsers() {
    if (!dom.usersTableBody) return;

    try {
      const res = await fetch("/api/admin/users");
      if (res.status === 403) {
        dom.usersTableBody.innerHTML = `
          <tr><td colspan="7" style="text-align: center; color: var(--color-amber); padding: 1.5rem;">🔒 User account management is restricted to Administrators only.</td></tr>
        `;
        return;
      }
      if (!res.ok) return;

      const data = await res.json();
      authState.users = data.users || [];
      renderUsersTable();
    } catch (err) {
      console.error("Error loading users:", err);
    }
  }

  function renderUsersTable() {
    const users = authState.users;
    if (!users.length) {
      dom.usersTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No user accounts found.</td></tr>`;
      return;
    }

    let rowsHtml = "";
    users.forEach(u => {
      const roleBadge = `<span class="badge ${u.role === 'admin' ? 'badge-admin' : (u.role === 'netadmin' ? 'badge-netadmin' : 'badge-readonly')}">${u.role}</span>`;
      const statusBadge = u.is_active ? `<span style="color: var(--color-emerald); font-weight:700;">● Active</span>` : `<span style="color: var(--color-rose); font-weight:700;">● Deactivated</span>`;
      const lastLogin = u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never";

      rowsHtml += `
        <tr>
          <td style="font-family: var(--font-mono); font-weight: 700;">#${u.id}</td>
          <td><strong>${escapeHtml(u.username)}</strong></td>
          <td>${escapeHtml(u.full_name)}</td>
          <td style="color: var(--text-muted);">${escapeHtml(u.email || '—')}</td>
          <td>${roleBadge}</td>
          <td>${statusBadge}</td>
          <td style="font-size: 0.75rem; color: var(--text-muted);">${lastLogin}</td>
          <td>
            <div class="btn-group">
              <button class="btn btn-outline btn-sm btn-reset-pwd" data-id="${u.id}">Reset Pwd</button>
              <button class="btn btn-outline btn-sm btn-toggle-active" data-id="${u.id}" data-active="${u.is_active}">${u.is_active ? 'Deactivate' : 'Activate'}</button>
              ${u.role !== 'admin' ? `<button class="btn btn-danger btn-sm btn-del-user" data-id="${u.id}">Delete</button>` : ''}
            </div>
          </td>
        </tr>
      `;
    });

    dom.usersTableBody.innerHTML = rowsHtml;
    bindUserRowButtons();
  }

  function bindUserRowButtons() {
    dom.usersTableBody.querySelectorAll(".btn-reset-pwd").forEach(btn => {
      btn.addEventListener("click", () => {
        if (dom.resetPasswordUserId) dom.resetPasswordUserId.value = btn.dataset.id;
        if (dom.resetPasswordInput) dom.resetPasswordInput.value = "";
        dom.resetPasswordModal.classList.add("active");
      });
    });

    dom.usersTableBody.querySelectorAll(".btn-toggle-active").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        const currentActive = btn.dataset.active === "1";
        const newActive = currentActive ? 0 : 1;
        try {
          const res = await fetch(`/api/admin/users/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_active: newActive })
          });
          if (res.ok) {
            showToast(`User status updated.`, "success");
            loadUsers();
          }
        } catch (err) {
          console.error(err);
        }
      });
    });

    dom.usersTableBody.querySelectorAll(".btn-del-user").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        if (!confirm(`Delete user account #${id}?`)) return;
        try {
          const res = await fetch(`/api/admin/users/${id}`, { method: "DELETE" });
          const data = await res.json();
          if (res.ok) {
            showToast("User deleted.", "info");
            loadUsers();
          } else {
            showToast(data.error || "Delete failed.", "error");
          }
        } catch (err) {
          console.error(err);
        }
      });
    });
  }

  async function handleCreateUserSubmit() {
    const username = dom.createUsernameInput.value.trim();
    const full_name = dom.createFullNameInput.value.trim();
    const email = dom.createEmailInput.value.trim();
    const password = dom.createPasswordInput.value;
    const role = dom.createRoleSelect.value;

    if (!username || !password || !full_name) {
      showToast("Username, full name, and password are required.", "error");
      return;
    }

    try {
      const res = await fetch("/api/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, full_name, email, password, role })
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`User '${username}' created successfully!`, "success");
        dom.createUserModal.classList.remove("active");
        dom.createUsernameInput.value = "";
        dom.createFullNameInput.value = "";
        dom.createEmailInput.value = "";
        dom.createPasswordInput.value = "";
        loadUsers();
      } else {
        showToast(data.error || "User creation failed.", "error");
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function handleConfirmResetPassword() {
    const id = dom.resetPasswordUserId.value;
    const new_password = dom.resetPasswordInput.value;

    if (!new_password || new_password.length < 6) {
      showToast("Password must be at least 6 characters long.", "error");
      return;
    }

    try {
      const res = await fetch(`/api/admin/users/${id}/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password })
      });
      const data = await res.json();
      if (res.ok) {
        showToast("Password successfully reset.", "success");
        dom.resetPasswordModal.classList.remove("active");
      } else {
        showToast(data.error || "Failed to reset password.", "error");
      }
    } catch (err) {
      console.error(err);
    }
  }

  // -------------------------------------------------------------
  // Dynamic Settings & Thresholds
  // -------------------------------------------------------------
  async function loadSettings() {
    try {
      const res = await fetch("/api/admin/config");
      if (!res.ok) return;
      const data = await res.json();
      const th = data.thresholds || {};

      if (dom.settingWarnUtil) dom.settingWarnUtil.value = th.warn_util || 70;
      if (dom.settingCritUtil) dom.settingCritUtil.value = th.crit_util || 85;
      if (dom.settingWarnLat) dom.settingWarnLat.value = th.warn_lat || 50;
      if (dom.settingCritLat) dom.settingCritLat.value = th.crit_lat || 100;
      if (dom.settingWarnLoss) dom.settingWarnLoss.value = th.warn_loss || 1.0;
      if (dom.settingCritLoss) dom.settingCritLoss.value = th.crit_loss || 3.0;

      const enf = data.enforcement_safety || {};
      if (dom.settingEnforcement) dom.settingEnforcement.checked = enf.enforcement_enabled || false;
    } catch (err) {
      console.error(err);
    }
  }

  async function handleSaveSettings() {
    const payload = {
      threshold_warning_utilization: dom.settingWarnUtil.value,
      threshold_critical_utilization: dom.settingCritUtil.value,
      threshold_warning_latency_ms: dom.settingWarnLat.value,
      threshold_critical_latency_ms: dom.settingCritLat.value,
      threshold_warning_packet_loss: dom.settingWarnLoss.value,
      threshold_critical_packet_loss: dom.settingCritLoss.value,
      network_enforcement_enabled: dom.settingEnforcement.checked ? "true" : "false"
    };

    try {
      const res = await fetch("/api/admin/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        showToast("Dynamic thresholds & settings updated successfully!", "success");
      } else {
        showToast(data.error || "Failed to update configuration.", "error");
      }
    } catch (err) {
      console.error(err);
    }
  }

  // -------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------
  function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    const icon = type === "success" ? "✓" : (type === "error" ? "⚠" : "ℹ");
    toast.innerHTML = `<strong>${icon}</strong> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
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

  // Expose global hook for refresh sync
  window.CampusNetAdmin = {
    checkUserSession,
    loadPolicies,
    loadAuditLogs
  };

  document.addEventListener("DOMContentLoaded", init);
})();
