#!/usr/bin/env python3
"""deb-downloader — HTTP API (asynchronous, in-process jobs).
Copyright (c) 2026 Remilulz91. All rights reserved.

Wraps the fetch engine behind a small FastAPI app:
  GET  /                        -> minimal selection UI (ui.html)
  GET  /favicon.svg             -> site icon
  GET  /healthz                 -> health check
  GET  /api/distributions       -> supported distro/version list
  POST /api/jobs                -> enqueue a fetch, returns {job_id, status}
  POST /api/jobs/update         -> enqueue a SYSTEM UPDATE job (multipart upload
                                   of the target machine's dpkg status file)
  GET  /api/jobs/{id}           -> job status (queued|running|done|error)
  GET  /api/jobs/{id}/download  -> the .zip once the job is done

Jobs run in a small in-process thread pool: the POST returns immediately and the
UI polls the status. No external service (Redis/worker) is required. Jobs and
their archives are kept for JOB_TTL then purged; in-flight jobs are lost if the
API restarts (acceptable for a single, personal instance).

Run (on a host with Docker + dpkg-dev). Debian's pip is externally managed
(PEP 668), so use a virtual environment:
    sudo apt-get install -y python3-venv
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app:app --host 0.0.0.0 --port 8000
Then open http://localhost:8000  (interactive API docs at /docs).
"""
from __future__ import annotations
import os
import time
import uuid
import errno
import shutil
import threading
import tempfile
from pathlib import Path
from typing import List
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

import distros
import fetch

app = FastAPI(
    title="deb-downloader API",
    version="1.8.0",
    description="Fetch a Debian/Ubuntu package and all its dependencies as a .zip.",
)


# --- Security headers (defense in depth) ----------------------------------
# Applied to every response. The UI is a single self-contained page, so the CSP
# allows inline script/style but nothing external, blocks framing/plugins, and
# restricts network calls (connect-src) to same origin. HSTS is intentionally
# left to the TLS terminator (nginx) since the app itself may be served over
# plain HTTP on a LAN.
_CSP = ("default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "form-action 'self'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'; "
        "object-src 'none'")
_SECURITY_HEADERS = {
    "Content-Security-Policy": _CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    for k, v in _SECURITY_HEADERS.items():
        resp.headers.setdefault(k, v)
    return resp

UI_PATH = Path(__file__).parent / "ui.html"
FAVICON_PATH = Path(__file__).parent.parent / "favicon.svg"  # repo root

# --- Job system (in-process) ---------------------------------------------
MAX_WORKERS = 2          # max concurrent fetches (each spawns a Docker container)
JOB_TTL = 3600           # seconds a finished job (and its .zip) is kept
# Working/results directory. Override with DDL_JOBS_DIR to point it at a
# partition with enough space (big package sets like gnome-core need a few GB,
# and /tmp may be a small tmpfs). Defaults to the system temp dir.
JOBS_DIR = Path(os.environ.get("DDL_JOBS_DIR") or
                (Path(tempfile.gettempdir()) / "deb-downloader-jobs"))
JOBS_DIR.mkdir(parents=True, exist_ok=True)

# Optional per-job size quota (megabytes). 0 = unlimited. Set via DDL_MAX_JOB_MB.
try:
    MAX_JOB_MB = max(0, int(os.environ.get("DDL_MAX_JOB_MB") or 0))
except ValueError:
    MAX_JOB_MB = 0
MAX_JOB_BYTES = MAX_JOB_MB * 1024 * 1024

# Max size accepted for an uploaded dpkg status file (typical: 3-5 MB).
MAX_STATUS_BYTES = 20 * 1024 * 1024

_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_WORKERS)
_JOBS = {}               # job_id -> dict
_LOCK = threading.Lock()


class FetchRequest(BaseModel):
    # Hard bounds at the schema edge (Zero Trust): reject absurd input before it
    # reaches the engine. Exact format/allowlist checks happen in fetch.validate.
    distro: str = Field(..., max_length=32, examples=["ubuntu"])
    release: str = Field(..., max_length=16, examples=["26.04"])
    arch: str = Field("amd64", max_length=16, examples=["amd64"])
    packages: List[str] = Field(..., min_length=1, max_length=20,
                                examples=[["nginx"]])
    no_recommends: bool = False


@app.get("/", response_class=HTMLResponse)
def ui():
    """Serve the minimal selection UI.

    Sent with no-cache headers so a new version is picked up immediately after an
    update (otherwise a stale cached page may call removed endpoints).
    """
    headers = {"Cache-Control": "no-cache, no-store, must-revalidate"}
    if UI_PATH.exists():
        return HTMLResponse(UI_PATH.read_text(encoding="utf-8"), headers=headers)
    return HTMLResponse("<h1>deb-downloader API</h1><p>See <a href='/docs'>/docs</a>.</p>",
                        headers=headers)


@app.get("/favicon.svg", include_in_schema=False)
def favicon():
    """Serve the site favicon (lives at the repo root)."""
    if FAVICON_PATH.exists():
        return FileResponse(str(FAVICON_PATH), media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="favicon not found")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/api/distributions")
def api_distributions():
    """List supported distribution/version pairs and architectures."""
    return {
        "distributions": distros.list_supported(),
        "arches": sorted(distros.ARCHES),
    }


@app.get("/api/status")
def api_status():
    """Server status: free disk space in the jobs dir and the per-job quota."""
    try:
        du = shutil.disk_usage(JOBS_DIR)
        free, total = du.free, du.total
    except OSError:
        free, total = None, None
    return {"disk_free": free, "disk_total": total, "max_job_bytes": MAX_JOB_BYTES}


@app.post("/api/jobs")
def create_job(req: FetchRequest):
    """Validate, enqueue a fetch job, and return its id immediately."""
    try:
        fetch.validate(req.distro, req.release, req.arch, req.packages)
    except fetch.FetchError as e:
        status = 422 if e.code == "package_not_found" else 400
        raise HTTPException(status_code=status,
                            detail={"code": e.code, "message": str(e), **e.data})

    _purge_expired()
    job_id = uuid.uuid4().hex
    with _LOCK:
        _JOBS[job_id] = {
            "id": job_id, "status": "queued", "created": time.time(),
            "packages": req.packages, "distro": req.distro, "release": req.release,
        }
    _EXECUTOR.submit(_run_job, job_id, req)
    return {"job_id": job_id, "status": "queued"}


@app.post("/api/jobs/update")
async def create_update_job(distro: str = Form(..., max_length=32),
                            release: str = Form(..., max_length=16),
                            status: UploadFile = File(...)):
    """Enqueue a SYSTEM UPDATE job.

    The client uploads the target machine's dpkg status file
    (/var/lib/dpkg/status). The engine then computes and downloads exactly the
    updates that machine needs within its release (point release, kernel and
    security fixes included). One machine = one status file = one job.
    """
    try:
        fetch.validate_update(distro, release, "amd64")
    except fetch.FetchError as e:
        raise HTTPException(status_code=400,
                            detail={"code": e.code, "message": str(e), **e.data})

    data = await status.read()
    if len(data) > MAX_STATUS_BYTES:
        raise HTTPException(status_code=413,
                            detail={"code": "status_too_large",
                                    "message": "Uploaded file too large."})
    head = data[:8192].decode("utf-8", "replace")
    if "Package:" not in head or "Status:" not in head:
        raise HTTPException(status_code=422,
                            detail={"code": "bad_status_file",
                                    "message": "Not a dpkg status file "
                                               "(expected /var/lib/dpkg/status)."})

    _purge_expired()
    job_id = uuid.uuid4().hex
    with _LOCK:
        _JOBS[job_id] = {
            "id": job_id, "status": "queued", "created": time.time(),
            "packages": ["system-update"], "distro": distro, "release": release,
        }
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    status_path = job_dir / "dpkg-status"
    status_path.write_bytes(data)
    _EXECUTOR.submit(_run_update_job, job_id, distro, release, str(status_path))
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    """Return the current state of a job."""
    with _LOCK:
        j = _JOBS.get(job_id)
        if not j:
            raise HTTPException(status_code=404,
                                detail={"code": "not_found", "message": "Unknown job."})
        out = {
            "job_id": j["id"], "status": j["status"],
            "packages": j.get("packages"), "distro": j.get("distro"),
            "release": j.get("release"),
        }
        if j["status"] == "done":
            out.update(filename=j.get("filename"), size=j.get("size"),
                       package_count=j.get("package_count"),
                       download_url="api/jobs/%s/download" % job_id)
        elif j["status"] == "error":
            out["error"] = j.get("error")
        elif j["status"] == "running":
            out["progress"] = j.get("progress")   # {"done": int, "total": int|None} or None
    return out


@app.get("/api/jobs/{job_id}/download")
def job_download(job_id: str):
    """Return the .zip once the job is done."""
    with _LOCK:
        j = _JOBS.get(job_id)
        zip_path = j.get("zip_path") if j else None
        filename = j.get("filename") if j else None
        ready = bool(j and j["status"] == "done" and zip_path and Path(zip_path).exists())
    if not ready:
        raise HTTPException(status_code=404,
                            detail={"code": "not_ready", "message": "Archive not available."})
    return FileResponse(zip_path, media_type="application/zip",
                        filename=filename or "packages.zip")


# --- Worker + housekeeping ------------------------------------------------
def _run_job(job_id, req):
    """Worker entry for a package-fetch job."""
    _execute_job(job_id, lambda work, progress: fetch.run(
        req.distro, req.release, req.arch, req.packages, out_dir=work,
        no_recommends=req.no_recommends, progress_cb=progress,
        max_bytes=MAX_JOB_BYTES))


def _run_update_job(job_id, distro, release, status_path):
    """Worker entry for a system-update job (uploaded dpkg status file)."""
    _execute_job(job_id, lambda work, progress: fetch.run(
        distro, release, "amd64", [], out_dir=work, status_path=status_path,
        progress_cb=progress, max_bytes=MAX_JOB_BYTES))


def _execute_job(job_id, runner):
    """Executed in a worker thread: run the fetch and record the result.

    `runner(work_dir, progress_cb)` does the actual fetch and returns the
    zip path (it closes over the job-specific parameters).
    """
    def progress(done, total):
        with _LOCK:
            if job_id in _JOBS:
                _JOBS[job_id]["progress"] = {"done": done, "total": total}

    with _LOCK:
        if job_id in _JOBS:
            _JOBS[job_id]["status"] = "running"
    work = JOBS_DIR / job_id / "work"

    def _keep_log():
        """Preserve the container output on failure for debugging.

        The work tree (incl. its .log) is removed after a job, so on error we
        copy the log up to <job>/error.log, which survives until the job is
        purged (JOB_TTL). Lets us see e.g. a frozen Docker image pull.
        """
        try:
            src = work / ".log"
            if src.exists():
                shutil.copy2(src, JOBS_DIR / job_id / "error.log")
        except OSError:
            pass

    try:
        work.mkdir(parents=True, exist_ok=True)
        zip_path = runner(work, progress)
        try:
            count = sum(1 for _ in (work / "debs").glob("*.deb"))
        except OSError:
            count = None
        size = zip_path.stat().st_size if zip_path.exists() else None
        shutil.rmtree(work, ignore_errors=True)   # keep the .zip, drop the work tree
        with _LOCK:
            if job_id in _JOBS:
                _JOBS[job_id].update(status="done", zip_path=str(zip_path),
                                     filename=zip_path.name, size=size,
                                     package_count=count)
    except fetch.FetchError as e:
        _keep_log()
        shutil.rmtree(work, ignore_errors=True)
        with _LOCK:
            if job_id in _JOBS:
                _JOBS[job_id].update(status="error",
                                     error={"code": e.code, "message": str(e), **e.data})
    except Exception as e:
        _keep_log()
        shutil.rmtree(work, ignore_errors=True)
        code = "internal"
        if isinstance(e, OSError) and getattr(e, "errno", None) == errno.ENOSPC:
            code = "no_space"
        with _LOCK:
            if job_id in _JOBS:
                _JOBS[job_id].update(status="error",
                                     error={"code": code, "message": str(e)})


def _purge_expired():
    """Drop jobs (and their archives) older than JOB_TTL.

    Sweeps the filesystem too, so it also removes orphan job folders left by a
    previous run (after a restart, in-memory records are gone). Folders of jobs
    still queued/running are never touched.
    """
    now = time.time()
    with _LOCK:
        active = {jid for jid, j in _JOBS.items()
                  if j.get("status") in ("queued", "running")}
        expired = [jid for jid, j in _JOBS.items() if jid not in active
                   and now - j.get("created", now) > JOB_TTL]
        for jid in expired:
            _JOBS.pop(jid, None)
    try:
        for d in JOBS_DIR.iterdir():
            if not d.is_dir() or d.name in active:
                continue
            try:
                if now - d.stat().st_mtime > JOB_TTL:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass
    except OSError:
        pass


def _purge_loop():
    """Background thread: purge old job archives periodically, even when idle."""
    while True:
        time.sleep(300)  # every 5 minutes
        try:
            _purge_expired()
        except Exception:
            pass


threading.Thread(target=_purge_loop, daemon=True).start()
