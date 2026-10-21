"""
CampusNet: Reporting & Download Center Module
Generates structured CSV and printable executive reports for authorized users.
"""

import io
import csv
from datetime import datetime, timezone
from database.db import get_db
from services.metrics import aggregate_network_summary, calculate_utilization, calculate_unmet_demand, calculate_satisfaction_rate
from services.settings import get_all_settings
from services.audit import query_audit_logs, export_audit_logs_csv
from services.policies import list_policies, export_policies_csv


def generate_telemetry_csv(db_path=None) -> str:
    """Generates detailed CSV of all campus network segments and current telemetry."""
    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM segments ORDER BY priority_weight DESC;")
    segments = [dict(r) for r in cursor.fetchall()]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Segment ID", "Segment Name", "Description", "Modeled Capacity (Mbps)",
        "Requested Demand (Mbps)", "Allocated Bandwidth (Mbps)", "Unmet Demand (Mbps)",
        "Satisfaction Rate (%)", "Priority Weight", "Min Guaranteed (Mbps)", "Max Limit (Mbps)",
        "Utilization (%)", "Latency (ms)", "Packet Loss (%)", "Jitter (ms)",
        "Throughput (Mbps)", "Status", "Data Source", "Last Updated"
    ])

    for s in segments:
        unmet = calculate_unmet_demand(s["demand_mbps"], s["allocated_mbps"])
        sat = calculate_satisfaction_rate(s["allocated_mbps"], s["demand_mbps"])
        writer.writerow([
            s["id"], s["name"], s.get("description", ""), s["capacity_mbps"],
            s["demand_mbps"], s["allocated_mbps"], unmet, sat,
            s["priority_weight"], s.get("min_guaranteed_mbps", 0.0), s.get("max_limit_mbps", "None"),
            s["utilization_pct"], s.get("latency_ms", "N/A"), s.get("packet_loss_pct", "N/A"),
            s.get("jitter_ms", "N/A"), s.get("throughput_mbps", "N/A"), s["status"],
            s["data_source"], s["updated_at"]
        ])

    return output.getvalue()


def generate_audit_csv(limit: int = 500, db_path=None) -> str:
    """Generates CSV of audit trail records."""
    logs_data = query_audit_logs(limit=limit, db_path=db_path)
    return export_audit_logs_csv(logs_data["logs"])


def generate_policies_csv(limit: int = 100, db_path=None) -> str:
    """Generates CSV of optimization policy history."""
    policies = list_policies(limit=limit, db_path=db_path)
    return export_policies_csv(policies)


def generate_executive_html_report(db_path=None) -> str:
    """Generates a clean, professional, printable HTML executive summary report."""
    conn = get_db(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM segments ORDER BY priority_weight DESC;")
    segments = [dict(r) for r in cursor.fetchall()]

    summary = aggregate_network_summary(segments, shared_capacity_mbps=800.0)

    cursor.execute("SELECT * FROM alerts WHERE is_resolved = 0 ORDER BY severity DESC, id DESC;")
    alerts = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM optimization_policies ORDER BY id DESC LIMIT 5;")
    recent_policies = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 10;")
    recent_audits = [dict(r) for r in cursor.fetchall()]

    settings = get_all_settings(db_path=db_path)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Generate HTML report
    rows_seg = ""
    for s in segments:
        status_color = "#10B981" if s["status"] == "NORMAL" else ("#F59E0B" if s["status"] == "WARNING" else "#EF4444")
        rows_seg += f"""
        <tr>
            <td style="font-weight:600;">{s['name']}</td>
            <td>{s['capacity_mbps']} Mbps</td>
            <td>{s['demand_mbps']} Mbps</td>
            <td><strong>{s['allocated_mbps']} Mbps</strong></td>
            <td>{s['priority_weight']}x</td>
            <td>{s['utilization_pct']}%</td>
            <td>{s.get('latency_ms', 0)} ms</td>
            <td>{s.get('packet_loss_pct', 0)}%</td>
            <td><span style="color:{status_color}; font-weight:700;">{s['status']}</span></td>
        </tr>
        """

    rows_alerts = ""
    if alerts:
        for a in alerts:
            badge_color = "#EF4444" if a["severity"] == "CRITICAL" else "#F59E0B"
            rows_alerts += f"""
            <div style="border-left: 4px solid {badge_color}; background:#f9fafb; padding:10px 14px; margin-bottom:8px; border-radius:4px;">
                <div style="font-weight:700; color:{badge_color}; font-size:13px;">[{a['severity']}] {a['metric_name'].upper()} ALERT - {a['segment_id']}</div>
                <div style="font-size:12px; margin-top:3px; color:#374151;">{a['explanation']}</div>
                <div style="font-size:11px; margin-top:3px; color:#4B5563;"><em>Remediation:</em> {a['recommended_action']}</div>
            </div>
            """
    else:
        rows_alerts = "<p style='color:#10B981; font-weight:600;'>No active network alerts. All segment thresholds within normal tolerances.</p>"

    rows_policies = ""
    for p in recent_policies:
        rows_policies += f"""
        <tr>
            <td>#{p['id']}</td>
            <td><strong>{p['name']}</strong></td>
            <td><span style="padding:2px 8px; border-radius:4px; font-size:11px; font-weight:700; background:#E5E7EB;">{p['status']}</span></td>
            <td>{p['target_environment']}</td>
            <td>{p['proposed_by']}</td>
            <td>{p.get('reviewed_by') or '—'}</td>
            <td>{p['created_at'][:19]}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>CampusNet Executive Network &amp; Compliance Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 30px; color: #111827; background: #fff; line-height: 1.5; }}
        .header {{ border-bottom: 2px solid #2563EB; padding-bottom: 16px; margin-bottom: 24px; }}
        h1 {{ font-size: 24px; margin: 0 0 6px 0; color: #1E3A8A; }}
        .meta {{ font-size: 12px; color: #6B7280; }}
        .grid {{ display: flex; gap: 16px; margin-bottom: 24px; }}
        .card {{ flex: 1; border: 1px solid #E5E7EB; border-radius: 8px; padding: 14px; background: #F9FAFB; }}
        .card-val {{ font-size: 20px; font-weight: 700; color: #1F2937; }}
        .card-lbl {{ font-size: 11px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; margin-bottom: 24px; font-size: 12px; }}
        th, td {{ border: 1px solid #E5E7EB; padding: 8px 10px; text-align: left; }}
        th {{ background: #F3F4F6; font-weight: 600; color: #374151; }}
        .section-title {{ font-size: 16px; font-weight: 700; color: #1E3A8A; margin-top: 24px; margin-bottom: 8px; border-bottom: 1px solid #E5E7EB; padding-bottom: 4px; }}
        .badge {{ padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; }}
        @media print {{ body {{ margin: 0; }} button {{ display: none; }} }}
    </style>
</head>
<body>
    <div style="text-align: right; margin-bottom: 10px;">
        <button onclick="window.print()" style="background:#2563EB; color:#fff; border:none; padding:8px 16px; border-radius:4px; cursor:pointer; font-size:12px; font-weight:600;">Print / Save as PDF</button>
    </div>
    <div class="header">
        <h1>CampusNet Operations &amp; Optimization Executive Report</h1>
        <div class="meta">
            Generated: {now_str} • System: CampusNet Operations Center • Mode: Isolated Simulation &amp; Testbed
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <div class="card-lbl">Total Capacity</div>
            <div class="card-val">{summary['total_modeled_capacity_mbps']} Mbps</div>
        </div>
        <div class="card">
            <div class="card-lbl">Total Demand</div>
            <div class="card-val">{summary['total_demand_mbps']} Mbps</div>
        </div>
        <div class="card">
            <div class="card-lbl">Total Allocated</div>
            <div class="card-val">{summary['total_allocated_mbps']} Mbps</div>
        </div>
        <div class="card">
            <div class="card-lbl">Satisfaction Rate</div>
            <div class="card-val">{summary['satisfaction_rate_pct']}%</div>
        </div>
        <div class="card">
            <div class="card-lbl">Active Alerts</div>
            <div class="card-val" style="color: {'#EF4444' if len(alerts) > 0 else '#10B981'};">{len(alerts)}</div>
        </div>
    </div>

    <div class="section-title">Campus Network Segments &amp; Performance Telemetry</div>
    <table>
        <thead>
            <tr>
                <th>Segment Name</th>
                <th>Capacity</th>
                <th>Demand</th>
                <th>Allocated</th>
                <th>Weight</th>
                <th>Utilization</th>
                <th>Latency</th>
                <th>Packet Loss</th>
                <th>Status</th>
            </tr>
        </thead>
        <tbody>
            {rows_seg}
        </tbody>
    </table>

    <div class="section-title">Active Congestion Alerts &amp; Recommended Actions</div>
    {rows_alerts}

    <div class="section-title">Recent Optimization Policy Lifecycle &amp; Governance</div>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Policy Name</th>
                <th>Status</th>
                <th>Environment</th>
                <th>Proposed By</th>
                <th>Reviewed By</th>
                <th>Date</th>
            </tr>
        </thead>
        <tbody>
            {rows_policies}
        </tbody>
    </table>

    <div style="margin-top: 30px; border-top: 1px solid #E5E7EB; padding-top: 10px; font-size: 11px; color: #9CA3AF; text-align: center;">
        CampusNet National Competition Network Optimization Operations Center • Confidential Administrative Report
    </div>
</body>
</html>
    """
    return html
