"""In-memory session store + vision agent step (Bedrock tool-use or heuristic)."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from app.agent.bedrock_loop import run_bedrock_agent
from app.agent.tools import ToolContext, execute_tool
from app.vision.compare_shots import MAX_RETAKES

APPROVED_PACKS = frozenset({"appliance_leds", "bike_brake_pad", "leaf_spot"})

# auto → try Bedrock, fall back to heuristic on credential/API failure
# bedrock → Bedrock only (error surfaces in response)
# heuristic → local fixed policy (no LLM)
# Sticky disable only for auth-ish failures; model EOL / NotFound should retry
# after BEDROCK_MODEL_ID changes (common during local setup).
_BEDROCK_OK: bool | None = None
_BEDROCK_DISABLED_REASON: str | None = None
_AUTH_FAILURE_MARKERS = (
    "ExpiredToken",
    "UnrecognizedClientException",
    "InvalidIdentityToken",
    "AccessDeniedException",
    "NoCredentialsError",
    "Unable to locate credentials",
)


@dataclass
class Session:
    session_id: str
    pack_id: str
    correlation_id: str
    retakes_remaining: int = MAX_RETAKES
    last_shot_bgr: np.ndarray | None = None
    last_roi: tuple[int, int, int, int] | None = None
    pending_retake_reason: str | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_agent: dict[str, Any] | None = None


_SESSIONS: dict[str, Session] = {}


def agent_mode() -> str:
    return os.environ.get("LOOKAGAIN_AGENT", "auto").strip().lower()


def create_session(pack_id: str, correlation_id: str) -> dict[str, Any]:
    if pack_id not in APPROVED_PACKS:
        return {
            "correlation_id": correlation_id,
            "pack_id": pack_id,
            "allowed": False,
            "next_action": "escalate_human",
            "reason": "pack_id_not_in_allowlist",
        }
    sid = str(uuid.uuid4())
    _SESSIONS[sid] = Session(
        session_id=sid,
        pack_id=pack_id,
        correlation_id=correlation_id,
    )
    return {
        "correlation_id": correlation_id,
        "pack_id": pack_id,
        "allowed": True,
        "session_id": sid,
        "retakes_remaining": MAX_RETAKES,
        "next_action": "triage_frame",
        "agent_mode": agent_mode(),
    }


def get_session(session_id: str) -> Session | None:
    return _SESSIONS.get(session_id)


def decode_image(data: bytes) -> np.ndarray | None:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _ctx_from_session(session: Session, bgr: np.ndarray) -> ToolContext:
    return ToolContext(
        pack_id=session.pack_id,
        working_bgr=bgr,
        retakes_remaining=session.retakes_remaining,
        pending_retake_reason=session.pending_retake_reason,
        last_shot_bgr=session.last_shot_bgr,
        last_roi=session.last_roi,
        trace=list(session.trace),
    )


def _apply_ctx(session: Session, ctx: ToolContext) -> None:
    session.retakes_remaining = ctx.retakes_remaining
    session.pending_retake_reason = ctx.pending_retake_reason
    session.last_shot_bgr = ctx.last_shot_bgr
    session.last_roi = ctx.last_roi
    session.trace = ctx.trace


def run_step_bedrock(session: Session, image_bytes: bytes, *, client: Any = None) -> dict[str, Any]:
    """Bedrock Converse chooses tools; OpenCV tools execute locally."""
    cid = session.correlation_id
    bgr = decode_image(image_bytes)
    if bgr is None:
        return {
            "correlation_id": cid,
            "session_id": session.session_id,
            "next_action": "request_capture",
            "reason": "decode_failed",
            "retakes_remaining": session.retakes_remaining,
            "trace": session.trace,
        }

    ctx = _ctx_from_session(session, bgr)
    out = run_bedrock_agent(ctx, client=client)
    _apply_ctx(session, ctx)
    session.last_agent = out.get("agent")
    out["correlation_id"] = cid
    out["session_id"] = session.session_id
    out["pack_id"] = session.pack_id
    return out


def run_step_heuristic(session: Session, image_bytes: bytes) -> dict[str, Any]:
    """Fixed local policy (no LLM) — same tools, deterministic routing."""
    cid = session.correlation_id
    bgr = decode_image(image_bytes)
    if bgr is None:
        return {
            "correlation_id": cid,
            "session_id": session.session_id,
            "next_action": "request_capture",
            "reason": "decode_failed",
            "retakes_remaining": session.retakes_remaining,
            "trace": session.trace,
        }

    ctx = _ctx_from_session(session, bgr)
    execute_tool("triage_frame", {}, ctx)
    assert ctx.last_triage is not None

    if not ctx.last_triage.passed:
        execute_tool("remediate_frame", {}, ctx)
        if not (ctx.last_triage and ctx.last_triage.passed):
            reason = (
                (ctx.trace[-1]["result"].get("retake_reason") if ctx.trace else None)
                or ctx.last_triage.retake_reason
                or "hold_steadier"
            )
            execute_tool("request_capture", {"reason": reason}, ctx)
            _apply_ctx(session, ctx)
            out = dict(ctx.terminal or {})
            out.update(
                {
                    "correlation_id": cid,
                    "session_id": session.session_id,
                    "pack_id": session.pack_id,
                    "agent": {"backend": "heuristic", "tools_called": [t["tool"] for t in ctx.trace]},
                    "trace": session.trace,
                    "retakes_remaining": session.retakes_remaining,
                }
            )
            return out

    if ctx.pending_retake_reason and ctx.last_shot_bgr is not None and ctx.last_roi is not None:
        execute_tool("compare_shots", {}, ctx)
        cmp = ctx.trace[-1]["result"]
        if not cmp.get("passed"):
            execute_tool(
                "request_capture",
                {"reason": ctx.pending_retake_reason or "hold_steadier"},
                ctx,
            )
            _apply_ctx(session, ctx)
            out = dict(ctx.terminal or {})
            out.update(
                {
                    "correlation_id": cid,
                    "session_id": session.session_id,
                    "pack_id": session.pack_id,
                    "compare_fail": cmp.get("fail_reason"),
                    "agent": {"backend": "heuristic", "tools_called": [t["tool"] for t in ctx.trace]},
                    "trace": session.trace,
                    "retakes_remaining": session.retakes_remaining,
                }
            )
            return out

    execute_tool("inspect_pack", {}, ctx)
    inspect = ctx.last_inspect or {}
    if inspect.get("next_action") == "request_capture":
        execute_tool("request_capture", {"reason": "move_closer"}, ctx)
    else:
        execute_tool("finalize_report", {}, ctx)

    _apply_ctx(session, ctx)
    out = dict(ctx.terminal or {"next_action": "escalate_human", "reason": "heuristic_no_terminal"})
    out.update(
        {
            "correlation_id": cid,
            "session_id": session.session_id,
            "pack_id": session.pack_id,
            "agent": {"backend": "heuristic", "tools_called": [t["tool"] for t in ctx.trace]},
            "trace": session.trace,
            "retakes_remaining": session.retakes_remaining,
        }
    )
    if ctx.last_triage:
        out["triage"] = ctx.last_triage.to_dict()
    return out


def run_step(session: Session, image_bytes: bytes, *, client: Any = None) -> dict[str, Any]:
    """Route to Bedrock tool-use or heuristic per LOOKAGAIN_AGENT."""
    global _BEDROCK_OK, _BEDROCK_DISABLED_REASON
    mode = agent_mode()
    use_bedrock = mode == "bedrock" or (mode == "auto" and _BEDROCK_OK is not False)

    if use_bedrock:
        try:
            out = run_step_bedrock(session, image_bytes, client=client)
            _BEDROCK_OK = True
            _BEDROCK_DISABLED_REASON = None
            return out
        except Exception as exc:  # noqa: BLE001 — surface or fall back
            msg = str(exc)
            sticky = any(m in msg for m in _AUTH_FAILURE_MARKERS)
            if sticky:
                _BEDROCK_OK = False
                _BEDROCK_DISABLED_REASON = msg
            else:
                # Model EOL / ResourceNotFound / throttles: retry next request
                _BEDROCK_OK = None
                _BEDROCK_DISABLED_REASON = msg
            if mode == "bedrock":
                return {
                    "correlation_id": session.correlation_id,
                    "session_id": session.session_id,
                    "pack_id": session.pack_id,
                    "next_action": "escalate_human",
                    "reason": "bedrock_error",
                    "error": msg,
                    "retakes_remaining": session.retakes_remaining,
                    "trace": session.trace,
                    "agent": {"backend": "bedrock_converse", "error": msg},
                }
            # auto → heuristic
            out = run_step_heuristic(session, image_bytes)
            out.setdefault("agent", {})
            if isinstance(out["agent"], dict):
                out["agent"]["bedrock_fallback"] = msg
                out["agent"]["bedrock_hint"] = (
                    "Set BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 "
                    "and restart uvicorn (old Haiku 3 IDs are EOL)."
                )
            return out

    out = run_step_heuristic(session, image_bytes)
    if mode == "auto" and _BEDROCK_DISABLED_REASON and isinstance(out.get("agent"), dict):
        out["agent"]["bedrock_skipped"] = _BEDROCK_DISABLED_REASON
    return out
