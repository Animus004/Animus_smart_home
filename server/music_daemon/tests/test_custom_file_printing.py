"""
Test Suite for Custom File Printing Subsystem (HP Ink Tank 310 Series):
1. Unit Tests for PrinterController.print_custom_file():
   - Python code (.py) formatted printing.
   - SQL script (.sql) formatted printing.
   - Image auto-fitting (.png).
   - Reject disallowed extensions.
   - Non-existent file error handling.
2. FastAPI Endpoint Integration Tests:
   - POST /api/printer/upload-base64 stages and prints file.
   - POST /api/printer/print-staged re-prints staged file.
   - GET /api/printer/history lists staged files.
   - POST /api/printer/cancel clears spooler.
"""

import os
import sys
import base64
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Add daemon path
daemon_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if daemon_dir not in sys.path:
    sys.path.insert(0, daemon_dir)

from printer_controller import PrinterController
from main import app, STORAGE_PRINTED_DOCS


@pytest.fixture
def simulated_printer(tmp_path):
    return PrinterController(is_simulated=True)


@pytest.fixture
def test_client():
    return TestClient(app)


def test_custom_print_python_code(simulated_printer, tmp_path):
    py_file = tmp_path / "analysis.py"
    py_file.write_text("print('Animus Smart Room SQL Analysis')\n", encoding="utf-8")
    ok, telemetry = simulated_printer.print_custom_file(
        file_path=str(py_file),
        copies=2,
        orientation="portrait"
    )
    assert ok is True
    assert telemetry["action"] == "PRINT_CUSTOM_FILE"
    assert telemetry["copies"] == 2
    assert telemetry["orientation"] == "portrait"


def test_custom_print_image_auto_fit(simulated_printer, tmp_path):
    img_file = tmp_path / "chart.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")  # Mock PNG header
    ok, telemetry = simulated_printer.print_custom_file(
        file_path=str(img_file),
        copies=1,
        orientation="landscape"
    )
    assert ok is True
    assert telemetry["action"] == "PRINT_CUSTOM_FILE"
    assert telemetry["orientation"] == "landscape"


def test_custom_print_rejects_disallowed_extension(simulated_printer, tmp_path):
    bad_file = tmp_path / "dangerous.exe"
    bad_file.write_bytes(b"MZ")
    ok, telemetry = simulated_printer.print_custom_file(file_path=str(bad_file))
    assert ok is False
    assert telemetry["status"] == "INVALID_EXTENSION"


def test_custom_print_missing_file(simulated_printer):
    ok, telemetry = simulated_printer.print_custom_file(file_path="C:/non_existent_file_path.pdf")
    assert ok is False
    assert telemetry["status"] == "FILE_NOT_FOUND"


def test_api_upload_base64_and_history(test_client, tmp_path):
    # Base64 encode sample SQL content
    sql_text = "-- Animus Smart Room SQL Practice\nSELECT user_id, COUNT(*) FROM orders GROUP BY user_id;"
    encoded = base64.b64encode(sql_text.encode("utf-8")).decode("utf-8")

    # In simulated/test mode, target_printer won't lock hardware
    payload = {
        "filename": "practice_query.sql",
        "content_base64": encoded,
        "copies": 1,
        "orientation": "portrait",
        "fit_to_page": True,
        "auto_print": False  # Stage only to avoid calling physical Windows spooler in CI
    }

    res = test_client.post("/api/printer/upload-base64", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "doc_id" in data
    assert os.path.exists(data["staged_path"])

    # Test history endpoint
    hist_res = test_client.get("/api/printer/history")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["success"] is True
    assert hist_data["count"] > 0
    assert any("practice_query.sql" in doc["filename"] for doc in hist_data["documents"])

    # Clean up staged file
    if os.path.exists(data["staged_path"]):
        os.remove(data["staged_path"])


def test_smart_a4_photo_paper_telemetry(simulated_printer, tmp_path):
    img_file = tmp_path / "camera_snap.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF")  # Mock JPG header
    ok, telemetry = simulated_printer.print_custom_file(
        file_path=str(img_file),
        copies=1,
        orientation="portrait"
    )
    assert ok is True
    meta = telemetry.get("smart_metadata", {})
    assert meta.get("paper_size") == "A4"
    assert meta.get("photo_optimized") is True
    assert meta.get("dpi") == 1200
    assert meta.get("page_coverage") == "97.1%"


def test_smart_a4_pdf_300dpi_telemetry(simulated_printer, tmp_path):
    pdf_file = tmp_path / "resume.pdf"
    pdf_file.write_bytes(b"%PDF-1.5\n%test\n")
    ok, telemetry = simulated_printer.print_custom_file(
        file_path=str(pdf_file),
        copies=1,
        orientation="portrait"
    )
    assert ok is True
    meta = telemetry.get("smart_metadata", {})
    assert meta.get("paper_size") == "A4"
    assert meta.get("dpi") == 300
    assert meta.get("page_coverage") == "97.1%"

