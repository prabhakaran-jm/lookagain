"""LookAgain hello-world FastAPI entrypoint (Thursday AWS scaffold)."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.health import health_payload

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="LookAgain", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    request.state.correlation_id = cid
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


@app.get("/health")
async def health(request: Request):
    return health_payload(getattr(request.state, "correlation_id", None))


@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/api/session/start")
async def start_session(
    request: Request,
    pack_id: str = Form(...),
):
    """Pack allowlist gate — non-approved packs force HITL escalate."""
    approved = {"appliance_leds", "bike_brake_pad", "leaf_spot"}
    cid = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    if pack_id not in approved:
        return JSONResponse(
            {
                "correlation_id": cid,
                "pack_id": pack_id,
                "allowed": False,
                "next_action": "escalate_human",
                "reason": "pack_id_not_in_allowlist",
            },
            status_code=200,
        )
    return {
        "correlation_id": cid,
        "pack_id": pack_id,
        "allowed": True,
        "session_id": str(uuid.uuid4()),
        "retakes_remaining": 3,
        "next_action": "triage_frame",
    }


@app.post("/api/upload")
async def upload_image(
    request: Request,
    pack_id: str = Form(...),
    file: UploadFile = File(...),
    x_correlation_id: str | None = Header(default=None),
):
    """Phone capture / file upload smoke endpoint (max 8 MiB)."""
    cid = x_correlation_id or getattr(request.state, "correlation_id", str(uuid.uuid4()))
    data = await file.read()
    max_bytes = 8 * 1024 * 1024
    if len(data) > max_bytes:
        return JSONResponse(
            {"correlation_id": cid, "error": "upload_too_large", "max_bytes": max_bytes},
            status_code=413,
        )
    return {
        "correlation_id": cid,
        "pack_id": pack_id,
        "filename": file.filename,
        "bytes": len(data),
        "content_type": file.content_type,
        "status": "received",
        "note": "vision tools wire-up is Fri; Thursday hello-world only",
    }
