from __future__ import annotations

import logging
import os
import re
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .excel_writer import write_excel
from .parser import PartialParseError, parse_pdf

BASE_DIR = Path(__file__).resolve().parent.parent
JOBS_DIR = BASE_DIR / "backend" / "tmp" / "jobs"
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
JOB_RETENTION_SECONDS = 24 * 60 * 60
MAX_UPLOAD_BYTES = max(int(os.getenv("MAX_UPLOAD_BYTES", 25 * 1024 * 1024)), 1)
UPLOAD_CHUNK_SIZE = max(int(os.getenv("UPLOAD_CHUNK_SIZE", 1024 * 1024)), 1024)
MAX_WORKERS = max(int(os.getenv("MAX_WORKERS", 2)), 1)
MAX_QUEUED_JOBS = max(int(os.getenv("MAX_QUEUED_JOBS", 8)), 0)
CLEANUP_INTERVAL_SECONDS = max(int(os.getenv("CLEANUP_INTERVAL_SECONDS", 30 * 60)), 1)
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_-]+")
GENERIC_PARSE_ERROR = "Unable to process the uploaded PDF."
PARTIAL_RESULT_ERROR = "Processing stopped before completion. A partial workbook is available."
INVALID_PDF_ERROR = "Uploaded file does not appear to be a valid PDF."
QUEUE_FULL_ERROR = "The service is busy. Please try again later."
logger = logging.getLogger(__name__)
JOBS_LOCK = threading.Lock()
JOBS: dict[str, dict[str, Any]] = {}
JOB_EXECUTOR: ThreadPoolExecutor | None = None
CLEANUP_STOP_EVENT = threading.Event()
CLEANUP_THREAD: threading.Thread | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global JOB_EXECUTOR
    global CLEANUP_THREAD

    cleanup_stale_jobs()
    JOB_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="cutoff-job")
    CLEANUP_STOP_EVENT.clear()
    if CLEANUP_THREAD is None or not CLEANUP_THREAD.is_alive():
        CLEANUP_THREAD = threading.Thread(
            target=cleanup_loop,
            args=(CLEANUP_STOP_EVENT,),
            daemon=True,
            name="cutoff-cleanup",
        )
        CLEANUP_THREAD.start()

    try:
        yield
    finally:
        CLEANUP_STOP_EVENT.set()
        if CLEANUP_THREAD is not None and CLEANUP_THREAD.is_alive():
            CLEANUP_THREAD.join(timeout=1)
        CLEANUP_THREAD = None
        if JOB_EXECUTOR is not None:
            JOB_EXECUTOR.shutdown(wait=False, cancel_futures=False)
            JOB_EXECUTOR = None


app = FastAPI(
    title="MHT-CET Cutoff PDF to Counseling Excel Converter",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ensure_jobs_dir() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def cleanup_loop(stop_event: threading.Event) -> None:
    while not stop_event.wait(CLEANUP_INTERVAL_SECONDS):
        cleanup_stale_jobs()


def sanitize_filename(filename: str) -> str:
    basename = filename.replace("\\", "/").split("/")[-1].strip()
    if not basename:
        raise HTTPException(status_code=400, detail="Please upload a valid MHT-CET CAP Round PDF.")

    raw_path = Path(basename)
    if raw_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Please upload a valid MHT-CET CAP Round PDF.")

    safe_stem = SAFE_FILENAME_RE.sub("_", raw_path.stem).strip("._-")
    if not safe_stem:
        safe_stem = "upload"
    return f"{safe_stem}.pdf"


def build_job_file_path(job_dir: Path, filename: str) -> Path:
    resolved_job_dir = job_dir.resolve()
    candidate = (resolved_job_dir / filename).resolve()
    if candidate.parent != resolved_job_dir:
        raise HTTPException(status_code=400, detail="Invalid upload filename.")
    return candidate


def get_job_counts() -> tuple[int, int]:
    with JOBS_LOCK:
        return get_job_counts_locked()


def get_job_counts_locked() -> tuple[int, int]:
    queued_jobs = sum(1 for job in JOBS.values() if job["status"] in {"uploading", "queued"})
    running_jobs = sum(1 for job in JOBS.values() if job["status"] == "processing")
    return queued_jobs, running_jobs


def remove_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS.pop(job_id, None)

    if not job:
        return

    job_dir = job.get("job_dir")
    if job_dir:
        shutil.rmtree(job_dir, ignore_errors=True)


def serialize_job(job: dict[str, Any]) -> dict[str, Any]:
    queued_jobs, running_jobs = get_job_counts()
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "progress_pct": job["progress_pct"],
        "colleges_found": job["colleges_found"],
        "branches_found": job["branches_found"],
        "rows_found": job["rows_found"],
        "current_college": job["current_college"],
        "current_branch": job["current_branch"],
        "message": job["message"],
        "estimated_time_remaining_seconds": job["estimated_time_remaining_seconds"],
        "output_filename": job["output_filename"],
        "partial_available": job["partial_available"],
        "error": job["error"],
        "queued_jobs": queued_jobs,
        "running_jobs": running_jobs,
    }


def new_job(job_id: str, original_filename: str) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "original_filename": original_filename,
        "created_at": time.time(),
        "updated_at": time.time(),
        "status": "queued",
        "progress_pct": 0,
        "colleges_found": 0,
        "branches_found": 0,
        "rows_found": 0,
        "current_college": "",
        "current_branch": "",
        "message": "Queued for processing.",
        "estimated_time_remaining_seconds": None,
        "output_filename": None,
        "partial_available": False,
        "error": None,
        "input_path": None,
        "output_path": None,
        "job_dir": None,
    }


def set_job_state(job_id: str, **updates: Any) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS[job_id]
        job.update(updates)
        job["updated_at"] = time.time()
        return dict(job)


def get_job(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return dict(job)


def cleanup_stale_jobs() -> None:
    ensure_jobs_dir()
    cutoff = time.time() - JOB_RETENTION_SECONDS
    for job_dir in JOBS_DIR.iterdir():
        if job_dir.is_dir() and job_dir.stat().st_mtime < cutoff:
            shutil.rmtree(job_dir, ignore_errors=True)

    with JOBS_LOCK:
        stale_ids = [job_id for job_id, job in JOBS.items() if job["updated_at"] < cutoff]
        for job_id in stale_ids:
            JOBS.pop(job_id, None)


def update_job_from_progress(job_id: str, event: dict[str, Any], started_at: float) -> None:
    pages_processed = max(int(event.get("pages_processed", 0)), 0)
    total_pages = max(int(event.get("total_pages", 0)), 0)
    parse_progress = 10
    if total_pages > 0:
        parse_progress = min(85, max(10, int((pages_processed / total_pages) * 85)))

    estimated_time_remaining = None
    elapsed = time.time() - started_at
    if pages_processed > 0 and total_pages >= pages_processed:
        rate = elapsed / pages_processed
        estimated_time_remaining = int(max((total_pages - pages_processed) * rate, 0))

    set_job_state(
        job_id,
        status="processing",
        progress_pct=parse_progress,
        colleges_found=int(event.get("colleges_found", 0)),
        branches_found=int(event.get("branches_found", 0)),
        rows_found=int(event.get("rows_found", 0)),
        current_college=event.get("current_college", ""),
        current_branch=event.get("current_branch", ""),
        message=event.get("message", "Parsing college entries..."),
        estimated_time_remaining_seconds=estimated_time_remaining,
    )


def process_job(job_id: str, pdf_path: Path, original_filename: str) -> None:
    started_at = time.time()
    job = get_job(job_id)
    job_dir = Path(job["job_dir"])
    partial_output_path = job_dir / "partial_output.xlsx"

    set_job_state(
        job_id,
        status="processing",
        progress_pct=5,
        message="Reading PDF pages...",
        estimated_time_remaining_seconds=None,
    )

    try:
        result = parse_pdf(
            pdf_path,
            progress_callback=lambda event: update_job_from_progress(job_id, event, started_at),
            source_name=original_filename,
        )
        set_job_state(
            job_id,
            progress_pct=92,
            colleges_found=result.colleges_found,
            branches_found=result.branches_found,
            rows_found=result.rows_found,
            message="Writing Excel file with counseling structure...",
            current_college="",
            current_branch="",
            output_filename=result.output_filename,
        )

        output_path = job_dir / result.output_filename
        write_excel(result, output_path)
        set_job_state(
            job_id,
            status="complete",
            progress_pct=100,
            colleges_found=result.colleges_found,
            branches_found=result.branches_found,
            rows_found=result.rows_found,
            current_college="",
            current_branch="",
            message="Conversion complete.",
            estimated_time_remaining_seconds=0,
            output_filename=output_path.name,
            output_path=str(output_path),
            partial_available=False,
            error=None,
        )
    except PartialParseError as exc:
        logger.warning("Job %s hit a recoverable parse error: %s", job_id, exc)
        partial = exc.partial_result
        if partial and partial.rows:
            try:
                write_excel(partial, partial_output_path)
            except Exception:  # pragma: no cover
                logger.exception("Job %s failed while writing a partial workbook", job_id)
                set_job_state(
                    job_id,
                    status="error",
                    progress_pct=100,
                    message=GENERIC_PARSE_ERROR,
                    estimated_time_remaining_seconds=0,
                    partial_available=False,
                    error=GENERIC_PARSE_ERROR,
                )
                return

            set_job_state(
                job_id,
                status="error",
                progress_pct=100,
                colleges_found=partial.colleges_found,
                branches_found=partial.branches_found,
                rows_found=partial.rows_found,
                current_college="",
                current_branch="",
                message=f"Parsed {partial.colleges_found} colleges before error.",
                estimated_time_remaining_seconds=0,
                output_filename=partial_output_path.name,
                output_path=str(partial_output_path),
                partial_available=True,
                error=PARTIAL_RESULT_ERROR,
            )
            return

        set_job_state(
            job_id,
            status="error",
            progress_pct=100,
            message=GENERIC_PARSE_ERROR,
            estimated_time_remaining_seconds=0,
            partial_available=False,
            error=GENERIC_PARSE_ERROR,
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("Job %s failed unexpectedly", job_id)
        set_job_state(
            job_id,
            status="error",
            progress_pct=100,
            message=GENERIC_PARSE_ERROR,
            estimated_time_remaining_seconds=0,
            partial_available=False,
            error=GENERIC_PARSE_ERROR,
        )


def start_job(job_id: str, pdf_path: Path, original_filename: str) -> None:
    if JOB_EXECUTOR is None:
        raise RuntimeError("Job executor is not available.")
    JOB_EXECUTOR.submit(process_job, job_id, pdf_path, original_filename)


async def stream_upload_to_disk(file: UploadFile, destination: Path) -> int:
    total_bytes = 0
    saw_header = False

    with destination.open("wb") as output_file:
        while True:
            chunk = await file.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break

            if not saw_header:
                saw_header = True
                if b"%PDF-" not in chunk[:1024]:
                    raise HTTPException(status_code=400, detail=INVALID_PDF_ERROR)

            total_bytes += len(chunk)
            if total_bytes > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Uploaded PDF exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
                )
            output_file.write(chunk)

    if total_bytes == 0:
        raise HTTPException(status_code=400, detail=INVALID_PDF_ERROR)

    return total_bytes


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)) -> JSONResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Please upload a valid MHT-CET CAP Round PDF.")

    ensure_jobs_dir()
    safe_filename = sanitize_filename(file.filename)
    job_id = uuid.uuid4().hex[:12]
    job_dir = JOBS_DIR / job_id
    job = new_job(job_id, safe_filename)
    job["status"] = "uploading"
    job["message"] = "Uploading PDF..."
    job["job_dir"] = str(job_dir)

    with JOBS_LOCK:
        queued_jobs, running_jobs = get_job_counts_locked()
        if queued_jobs + running_jobs >= MAX_WORKERS + MAX_QUEUED_JOBS:
            raise HTTPException(status_code=429, detail=QUEUE_FULL_ERROR)
        JOBS[job_id] = job

    try:
        job_dir.mkdir(parents=True, exist_ok=True)
        input_path = build_job_file_path(job_dir, safe_filename)
        set_job_state(job_id, input_path=str(input_path))
        await stream_upload_to_disk(file, input_path)
        set_job_state(job_id, status="queued", message="Queued for processing.")
        logger.info("Accepted upload for job %s as %s", job_id, safe_filename)
        start_job(job_id, input_path, safe_filename)
        return JSONResponse({"job_id": job_id, "status": "queued"})
    except Exception:
        remove_job(job_id)
        raise
    finally:
        await file.close()


@app.get("/api/status/{job_id}")
def get_status(job_id: str) -> JSONResponse:
    return JSONResponse(serialize_job(get_job(job_id)))


@app.get("/api/download/{job_id}")
def download_result(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if job["status"] not in {"complete", "error"}:
        raise HTTPException(status_code=409, detail="The file is not ready for download yet.")

    if job["status"] == "error" and not job["partial_available"]:
        raise HTTPException(status_code=409, detail="No partial workbook is available for this failed job.")

    output_path = job.get("output_path")
    if not output_path:
        raise HTTPException(status_code=404, detail="Generated workbook not found.")

    output_file = Path(output_path)
    if not output_file.exists():
        raise HTTPException(status_code=404, detail="Generated workbook not found.")

    return FileResponse(
        output_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=job["output_filename"],
    )


if FRONTEND_DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def serve_index() -> FileResponse:
        return FileResponse(FRONTEND_DIST_DIR / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str) -> FileResponse:
        requested_file = FRONTEND_DIST_DIR / full_path
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        if requested_file.exists() and requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(FRONTEND_DIST_DIR / "index.html")
