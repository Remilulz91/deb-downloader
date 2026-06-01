#!/usr/bin/env python3
"""deb-downloader — HTTP API (MVP, synchronous).
Copyright (c) 2026 Remilulz91. All rights reserved.

Wraps the fetch engine behind a small FastAPI app:
  GET  /                   -> minimal selection UI (ui.html)
  GET  /healthz            -> health check
  GET  /api/distributions  -> supported distro/version list
  POST /api/fetch          -> run the fetch synchronously, return the .zip

Synchronous MVP: the request blocks until the .zip is ready (a fetch can take a
while). The async job-queue version (Redis/RQ) is the next step — see
../ARCHITECTURE.md.

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
import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

import distros
import fetch

app = FastAPI(
    title="deb-downloader API",
    version="0.5.0",
    description="Fetch a Debian/Ubuntu package and all its dependencies as a .zip.",
)

UI_PATH = Path(__file__).parent / "ui.html"
FAVICON_PATH = Path(__file__).parent.parent / "favicon.svg"  # repo root


class FetchRequest(BaseModel):
    distro: str = Field(..., examples=["ubuntu"])
    release: str = Field(..., examples=["26.04"])
    arch: str = Field("amd64", examples=["amd64"])
    packages: List[str] = Field(..., min_length=1, examples=[["nginx"]])
    no_recommends: bool = False


@app.get("/", response_class=HTMLResponse)
def ui():
    """Serve the minimal selection UI."""
    if UI_PATH.exists():
        return HTMLResponse(UI_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>deb-downloader API</h1><p>See <a href='/docs'>/docs</a>.</p>")


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


@app.post("/api/fetch")
def api_fetch(req: FetchRequest):
    """Run the fetch synchronously and return the resulting .zip archive."""
    # Reuse the engine's strict validation (distro supported, safe pkg names).
    try:
        fetch.validate(req.distro, req.release, req.arch, req.packages)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    out_dir = Path(tempfile.mkdtemp(prefix="ddl_api_"))
    try:
        zip_path = fetch.run(
            req.distro, req.release, req.arch, req.packages,
            out_dir=out_dir, no_recommends=req.no_recommends,
        )
    except RuntimeError as e:                 # e.g. Docker not installed
        _cleanup(out_dir)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:                    # docker/apt failure, timeout, etc.
        _cleanup(out_dir)
        raise HTTPException(status_code=500, detail=f"fetch failed: {e}")

    # Delete the temporary files once the response has been sent.
    return FileResponse(
        str(zip_path),
        media_type="application/zip",
        filename=zip_path.name,
        background=BackgroundTask(_cleanup, out_dir, zip_path),
    )


def _cleanup(*paths):
    """Best-effort removal of temporary files/folders."""
    for p in paths:
        p = Path(p)
        try:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()
        except OSError:
            pass
