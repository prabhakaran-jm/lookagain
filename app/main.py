"""LookAgain FastAPI — pack gate + vision agent step loop."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agent.session import create_session, get_session, run_step
from app.health import health_payload

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
FIXTURES_DIR = STATIC_DIR / "fixtures"
STATIC_DIR.mkdir(exist_ok=True)
FIXTURES_DIR.mkdir(exist_ok=True)

DEMO_PAIRS = {
    "leds_glare_retake": "Glare wash → clean retake (less_glare / compare pass)",
    "leds_closer_retake": "Full panel → closer crop (move_closer / compare pass)",
}

app = FastAPI(title="LookAgain", version="0.3.1")
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
    cid = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return create_session(pack_id, cid)


@app.post("/api/session/{session_id}/step")
async def session_step(
    session_id: str,
    request: Request,
    file: UploadFile = File(...),
    x_correlation_id: str | None = Header(default=None),
):
    """Run one agent step on an uploaded frame."""
    cid = x_correlation_id or getattr(request.state, "correlation_id", str(uuid.uuid4()))
    session = get_session(session_id)
    if session is None:
        return JSONResponse(
            {"correlation_id": cid, "error": "session_not_found", "session_id": session_id},
            status_code=404,
        )
    session.correlation_id = cid
    data = await file.read()
    max_bytes = 8 * 1024 * 1024
    if len(data) > max_bytes:
        return JSONResponse(
            {"correlation_id": cid, "error": "upload_too_large", "max_bytes": max_bytes},
            status_code=413,
        )
    return run_step(session, data)


@app.post("/api/upload")
async def upload_image(
    request: Request,
    pack_id: str = Form(...),
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    x_correlation_id: str | None = Header(default=None),
):
    """Start (if needed) + run one step — phone-friendly single call."""
    cid = x_correlation_id or getattr(request.state, "correlation_id", str(uuid.uuid4()))
    data = await file.read()
    max_bytes = 8 * 1024 * 1024
    if len(data) > max_bytes:
        return JSONResponse(
            {"correlation_id": cid, "error": "upload_too_large", "max_bytes": max_bytes},
            status_code=413,
        )

    if session_id:
        session = get_session(session_id)
        if session is None:
            return JSONResponse(
                {"correlation_id": cid, "error": "session_not_found", "session_id": session_id},
                status_code=404,
            )
    else:
        started = create_session(pack_id, cid)
        if not started.get("allowed"):
            return started
        session = get_session(started["session_id"])
        assert session is not None

    session.correlation_id = cid
    return run_step(session, data)


@app.get("/api/demo/pairs")
async def list_demo_pairs():
    """Available no-prop fixture pairs for video / judging demos."""
    pairs = []
    for pair_id, blurb in DEMO_PAIRS.items():
        d = FIXTURES_DIR / pair_id
        pairs.append(
            {
                "pair_id": pair_id,
                "description": blurb,
                "shot1_url": f"/static/fixtures/{pair_id}/shot1.jpg",
                "shot2_url": f"/static/fixtures/{pair_id}/shot2.jpg",
                "ready": (d / "shot1.jpg").exists() and (d / "shot2.jpg").exists(),
            }
        )
    return {"pairs": pairs}


@app.post("/api/demo/run_pair")
async def run_demo_pair(
    request: Request,
    pair_id: str = Form("leds_glare_retake"),
    pack_id: str = Form("appliance_leds"),
    x_correlation_id: str | None = Header(default=None),
):
    """Run shot1 then shot2 through the agent — glare→retake→pass without props."""
    cid = x_correlation_id or getattr(request.state, "correlation_id", str(uuid.uuid4()))
    if pair_id not in DEMO_PAIRS:
        return JSONResponse(
            {"correlation_id": cid, "error": "unknown_pair", "known": list(DEMO_PAIRS)},
            status_code=400,
        )
    shot1_path = FIXTURES_DIR / pair_id / "shot1.jpg"
    shot2_path = FIXTURES_DIR / pair_id / "shot2.jpg"
    if not shot1_path.exists() or not shot2_path.exists():
        return JSONResponse(
            {
                "correlation_id": cid,
                "error": "fixtures_missing",
                "hint": "python scripts/make_fixture_pairs.py",
            },
            status_code=404,
        )

    started = create_session(pack_id, cid)
    if not started.get("allowed"):
        return started
    session = get_session(started["session_id"])
    assert session is not None

    step1 = run_step(session, shot1_path.read_bytes())
    step2 = run_step(session, shot2_path.read_bytes())
    return {
        "correlation_id": cid,
        "pair_id": pair_id,
        "pack_id": pack_id,
        "session_id": session.session_id,
        "step1": step1,
        "step2": step2,
        "demo_ok": step2.get("next_action") == "finalize_report",
    }
