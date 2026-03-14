from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

import backend.app as app_module
from backend.excel_writer import WorkbookSummary
from backend.parser import ParseResult, ParsedRow, PartialParseError


def sample_parse_result() -> ParseResult:
    return ParseResult(
        round_label="CAP Round I",
        academic_year="2025-26",
        sheet_name="CAP Round I Cutoffs",
        output_filename="MHT_CET_CAP_Round_I_Cutoffs_2025-26.xlsx",
        rows=[
            ParsedRow(
                college_code="01002",
                college_name="Government College of Engineering, Amravati",
                city="Amravati",
                district="Amravati",
                college_type="Government",
                minority_status="General",
                home_university="Sant Gadge Baba Amravati University",
                branch_code="0100224210",
                branch_name="Computer Science and Engineering",
                data={"GOPENS": {"rank": 9196, "pct": 97.3737374}},
            )
        ],
    )


def make_client(work_dir: Path, monkeypatch) -> TestClient:
    jobs_dir = work_dir / "jobs"
    monkeypatch.setattr(app_module, "JOBS_DIR", jobs_dir)
    jobs_dir.mkdir(parents=True, exist_ok=True)
    with app_module.JOBS_LOCK:
        app_module.JOBS.clear()
    return TestClient(app_module.app)


def test_upload_rejects_non_pdf(monkeypatch) -> None:
    base_dir = Path("backend") / "tmp" / "test-artifacts"
    base_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=base_dir) as temp_dir:
        client = make_client(Path(temp_dir), monkeypatch)

        response = client.post(
            "/api/upload",
            files={"file": ("notes.txt", b"plain text", "text/plain")},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Please upload a valid MHT-CET CAP Round PDF."


def test_upload_status_and_download_complete(monkeypatch) -> None:
    result = sample_parse_result()

    def fake_parse_pdf(pdf_path, progress_callback=None, source_name=None):  # noqa: ANN001
        if progress_callback:
            progress_callback(
                {
                    "pages_processed": 2,
                    "total_pages": 2,
                    "colleges_found": 1,
                    "branches_found": 1,
                    "rows_found": 1,
                    "current_college": "Government College of Engineering, Amravati",
                    "current_branch": "Computer Science and Engineering",
                    "message": "Extracting branch cutoffs... (1 branches processed)",
                }
            )
        return result

    def fake_write_excel(parse_result, output_path):  # noqa: ANN001
        Path(output_path).write_bytes(b"excel-bytes")
        return WorkbookSummary(
            sheet_name=parse_result.sheet_name,
            output_filename=Path(output_path).name,
            row_count=parse_result.rows_found,
        )

    monkeypatch.setattr(app_module, "parse_pdf", fake_parse_pdf)
    monkeypatch.setattr(app_module, "write_excel", fake_write_excel)
    monkeypatch.setattr(
        app_module,
        "start_job",
        lambda job_id, pdf_path, original_filename: app_module.process_job(
            job_id,
            Path(pdf_path),
            original_filename,
        ),
    )

    base_dir = Path("backend") / "tmp" / "test-artifacts"
    base_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=base_dir) as temp_dir:
        client = make_client(Path(temp_dir), monkeypatch)
        upload = client.post(
            "/api/upload",
            files={"file": ("cutoff.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )

        assert upload.status_code == 200
        payload = upload.json()
        status = client.get(f"/api/status/{payload['job_id']}")
        download = client.get(f"/api/download/{payload['job_id']}")

        assert status.status_code == 200
        assert status.json()["status"] == "complete"
        assert status.json()["output_filename"] == "MHT_CET_CAP_Round_I_Cutoffs_2025-26.xlsx"
        assert download.status_code == 200
        assert download.content == b"excel-bytes"


def test_partial_download_available_on_parse_error(monkeypatch) -> None:
    partial_result = sample_parse_result()

    def fake_parse_pdf(pdf_path, progress_callback=None, source_name=None):  # noqa: ANN001
        raise PartialParseError("parser exploded", partial_result=partial_result)

    def fake_write_excel(parse_result, output_path):  # noqa: ANN001
        Path(output_path).write_bytes(b"partial-excel")
        return WorkbookSummary(
            sheet_name=parse_result.sheet_name,
            output_filename=Path(output_path).name,
            row_count=parse_result.rows_found,
        )

    monkeypatch.setattr(app_module, "parse_pdf", fake_parse_pdf)
    monkeypatch.setattr(app_module, "write_excel", fake_write_excel)
    monkeypatch.setattr(
        app_module,
        "start_job",
        lambda job_id, pdf_path, original_filename: app_module.process_job(
            job_id,
            Path(pdf_path),
            original_filename,
        ),
    )

    base_dir = Path("backend") / "tmp" / "test-artifacts"
    base_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=base_dir) as temp_dir:
        client = make_client(Path(temp_dir), monkeypatch)
        upload = client.post(
            "/api/upload",
            files={"file": ("cutoff.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )

        payload = upload.json()
        status = client.get(f"/api/status/{payload['job_id']}")
        download = client.get(f"/api/download/{payload['job_id']}")

        assert status.status_code == 200
        assert status.json()["status"] == "error"
        assert status.json()["partial_available"] is True
        assert download.status_code == 200
        assert download.content == b"partial-excel"
