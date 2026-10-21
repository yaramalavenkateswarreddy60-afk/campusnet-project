"""
Unit Tests for adapters/csv_import.py
Validates safe ingestion, header validation, boundary checks, and error reporting.
"""

import os
import tempfile
import pytest
from database.db import init_db
from adapters.csv_import import validate_and_import_csv, CSVValidationError

@pytest.fixture
def test_db_path(tmp_path):
    db_file = tmp_path / "test_csv.db"
    init_db(str(db_file), seed_if_empty=True)
    return str(db_file)


def test_valid_csv_import(test_db_path):
    csv_content = """timestamp,segment_name,demand_mbps,throughput_mbps,latency_ms,packet_loss_pct,jitter_ms,notes
2026-10-21T10:00:00Z,Computer Lab,250.0,240.0,30.5,0.8,4.0,Valid batch entry
2026-10-21T10:00:00Z,Library,80.0,79.5,18.0,0.1,1.5,Valid library entry
"""
    result = validate_and_import_csv(csv_content, db_path=test_db_path)
    assert result["success"] is True
    assert result["rows_imported"] == 2
    assert result["data_source"] == "IMPORTED"


def test_csv_missing_required_headers(test_db_path):
    # Missing 'demand_mbps'
    bad_csv = """timestamp,segment_name,latency_ms
2026-10-21T10:00:00Z,Computer Lab,30.5
"""
    with pytest.raises(CSVValidationError) as exc:
        validate_and_import_csv(bad_csv, db_path=test_db_path)
    assert "Missing required CSV column" in str(exc.value)


def test_csv_unknown_segment_name(test_db_path):
    bad_csv = """timestamp,segment_name,demand_mbps
2026-10-21T10:00:00Z,NonExistentSegmentXYZ,200.0
"""
    with pytest.raises(CSVValidationError) as exc:
        validate_and_import_csv(bad_csv, db_path=test_db_path)
    assert "does not match existing campus segments" in str(exc.value)


def test_csv_invalid_packet_loss_percentage(test_db_path):
    # packet loss > 100% is physically impossible
    bad_csv = """timestamp,segment_name,demand_mbps,packet_loss_pct
2026-10-21T10:00:00Z,Computer Lab,200.0,150.0
"""
    with pytest.raises(CSVValidationError) as exc:
        validate_and_import_csv(bad_csv, db_path=test_db_path)
    assert "packet_loss_pct" in str(exc.value)


def test_csv_negative_demand(test_db_path):
    bad_csv = """timestamp,segment_name,demand_mbps
2026-10-21T10:00:00Z,Computer Lab,-45.0
"""
    with pytest.raises(CSVValidationError) as exc:
        validate_and_import_csv(bad_csv, db_path=test_db_path)
    assert "demand_mbps" in str(exc.value)
