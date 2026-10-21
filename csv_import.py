"""
CampusNet: Aggregate Network Measurement CSV Importer
Safely validates and ingests historical aggregate measurements.
Guarantees data provenance ('IMPORTED') and protects against malformed files.
"""

import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Tuple
from database.db import get_db

REQUIRED_COLUMNS = {"timestamp", "segment_name", "demand_mbps"}
ALLOWED_COLUMNS = {
    "timestamp", "segment_name", "demand_mbps", "throughput_mbps",
    "capacity_mbps", "latency_ms", "packet_loss_pct", "jitter_ms", "notes"
}

class CSVValidationError(ValueError):
    """Custom exception raised on CSV structure or validation failure."""
    pass


def validate_and_import_csv(
    file_stream_or_text: str,
    db_path: str = None
) -> Dict[str, Any]:
    """
    Parses and validates CSV content line by line.
    Enforces safe numeric bounds and links measurements to campus segments.
    """
    if isinstance(file_stream_or_text, str):
        stream = io.StringIO(file_stream_or_text.strip())
    else:
        stream = io.StringIO(file_stream_or_text.read().decode("utf-8-sig"))

    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        raise CSVValidationError("The uploaded CSV file is empty or missing headers.")

    fieldnames = [f.strip().lower() for f in reader.fieldnames if f]
    missing = REQUIRED_COLUMNS - set(fieldnames)
    if missing:
        raise CSVValidationError(
            f"Missing required CSV column(s): {', '.join(sorted(missing))}. "
            f"Required columns are: {', '.join(sorted(REQUIRED_COLUMNS))}."
        )

    conn = get_db(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM segments;")
    existing_segments = {row["name"].strip().lower(): row["id"] for row in cursor.fetchall()}

    valid_rows = []
    errors = []

    for line_num, raw_row in enumerate(reader, start=2):
        row = {k.strip().lower(): v.strip() for k, v in raw_row.items() if k}
        
        # Check segment name
        seg_name = row.get("segment_name", "")
        if not seg_name:
            errors.append(f"Row {line_num}: 'segment_name' cannot be blank.")
            continue

        seg_id = existing_segments.get(seg_name.lower())
        if not seg_id:
            # Segment not in baseline DB
            errors.append(
                f"Row {line_num}: Segment '{seg_name}' does not match existing campus segments: "
                f"{', '.join(sorted([s.title() for s in existing_segments.keys()]))}"
            )
            continue

        # Check timestamp
        ts_raw = row.get("timestamp", "")
        if not ts_raw:
            errors.append(f"Row {line_num}: 'timestamp' is required.")
            continue

        # Validate numeric fields
        try:
            demand = float(row.get("demand_mbps", 0.0))
            if demand < 0:
                errors.append(f"Row {line_num}: 'demand_mbps' must be >= 0, got {demand}.")
                continue
        except (ValueError, TypeError):
            errors.append(f"Row {line_num}: 'demand_mbps' must be a valid number.")
            continue

        throughput = None
        if row.get("throughput_mbps"):
            try:
                throughput = float(row["throughput_mbps"])
                if throughput < 0:
                    errors.append(f"Row {line_num}: 'throughput_mbps' must be >= 0.")
                    continue
            except ValueError:
                errors.append(f"Row {line_num}: 'throughput_mbps' must be a number.")
                continue

        latency = None
        if row.get("latency_ms"):
            try:
                latency = float(row["latency_ms"])
                if latency < 0:
                    errors.append(f"Row {line_num}: 'latency_ms' must be >= 0.")
                    continue
            except ValueError:
                errors.append(f"Row {line_num}: 'latency_ms' must be a number.")
                continue

        loss = None
        if row.get("packet_loss_pct"):
            try:
                loss = float(row["packet_loss_pct"])
                if not (0.0 <= loss <= 100.0):
                    errors.append(f"Row {line_num}: 'packet_loss_pct' must be between 0 and 100, got {loss}.")
                    continue
            except ValueError:
                errors.append(f"Row {line_num}: 'packet_loss_pct' must be a number.")
                continue

        jitter = None
        if row.get("jitter_ms"):
            try:
                jitter = float(row["jitter_ms"])
                if jitter < 0:
                    errors.append(f"Row {line_num}: 'jitter_ms' must be >= 0.")
                    continue
            except ValueError:
                errors.append(f"Row {line_num}: 'jitter_ms' must be a number.")
                continue

        notes = row.get("notes", "Imported measurement batch")

        # Approximate utilization if capacity exists
        cursor.execute("SELECT capacity_mbps FROM segments WHERE id = ?;", (seg_id,))
        cap_row = cursor.fetchone()
        seg_cap = cap_row["capacity_mbps"] if cap_row else 100.0
        active_rate = throughput if throughput is not None else demand
        util = round((active_rate / seg_cap * 100.0) if seg_cap > 0 else 0.0, 2)

        valid_rows.append((
            seg_id, throughput, latency, loss, jitter, util, "IMPORTED", ts_raw, notes
        ))

    if errors and len(valid_rows) == 0:
        raise CSVValidationError(f"CSV import failed with errors:\n" + "\n".join(errors[:10]))

    # Insert valid rows
    if valid_rows:
        cursor.executemany(
            """
            INSERT INTO measurements (
                segment_id, throughput_mbps, latency_ms, packet_loss_pct, jitter_ms,
                utilization_pct, data_source, timestamp, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            valid_rows
        )
        conn.commit()

    return {
        "success": True,
        "rows_imported": len(valid_rows),
        "validation_warnings": errors,
        "data_source": "IMPORTED"
    }
