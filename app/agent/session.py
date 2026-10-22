"""In-memory session store + one-step vision agent loop."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from app.vision.compare_shots import MAX_RETAKES, compare_shots
from app.vision.evidence_gate import validate_claims
from app.vision.packs.appliance_leds import inspect_appliance_leds
from app.vision.packs.bike_brake_pad import inspect_bike_brake_pad
from app.vision.packs.leaf_spot import inspect_leaf_spot
from app.vision.remediate import remediate_frame
from app.vision.triage import triage_frame

APPROVED_PACKS = frozenset({"appliance_leds", "bike_brake_pad", "leaf_spot"})


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


_SESSIONS: dict[str, Session] = {}


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
    }


def get_session(session_id: str) -> Session | None:
    return _SESSIONS.get(session_id)


def decode_image(data: bytes) -> np.ndarray | None:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _inspect(pack_id: str, bgr: np.ndarray, roi: tuple[int, int, int, int] | None) -> dict[str, Any]:
    if pack_id == "appliance_leds":
        return inspect_appliance_leds(bgr, roi).to_dict()
    if pack_id == "bike_brake_pad":
        return inspect_bike_brake_pad(bgr, roi).to_dict()
    if pack_id == "leaf_spot":
        return inspect_leaf_spot(bgr, roi).to_dict()
    return {
        "claims": [f"{pack_id}: pack not allowlisted — escalate."],
        "next_action": "escalate_human",
        "metrics": {},
    }


def run_step(session: Session, image_bytes: bytes) -> dict[str, Any]:
    """One agent step: decode → triage → remediate? → compare? → inspect → gate."""
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

    triage = triage_frame(bgr)
    session.trace.append({"tool": "triage_frame", "result": triage.to_dict()})

    working = bgr
    working_triage = triage

    if not triage.passed:
        rem = remediate_frame(bgr, triage)
        session.trace.append(
            {
                "tool": "remediate_frame",
                "result": {
                    "improved": rem.improved,
                    "passed_after": rem.passed_after,
                    "steps_applied": rem.steps_applied,
                    "metrics": rem.metrics,
                    "retake_reason": rem.retake_reason,
                },
            }
        )
        if rem.passed_after:
            working = rem.image_bgr
            working_triage = triage_frame(working)
        else:
            reason = rem.retake_reason or triage.retake_reason or "hold_steadier"
            if session.retakes_remaining <= 0:
                out = {
                    "correlation_id": cid,
                    "session_id": session.session_id,
                    "pack_id": session.pack_id,
                    "next_action": "escalate_human",
                    "reason": "max_retakes_exhausted",
                    "last_retake_reason": reason,
                    "retakes_remaining": 0,
                    "trace": session.trace,
                }
                return out
            session.retakes_remaining -= 1
            session.pending_retake_reason = reason
            session.last_shot_bgr = working
            session.last_roi = triage.roi
            return {
                "correlation_id": cid,
                "session_id": session.session_id,
                "pack_id": session.pack_id,
                "next_action": "request_capture",
                "retake_reason": reason,
                "retakes_remaining": session.retakes_remaining,
                "triage": triage.to_dict(),
                "trace": session.trace,
            }

    # Optional compare gate when this shot follows a guided retake
    if (
        session.pending_retake_reason
        and session.last_shot_bgr is not None
        and session.last_roi is not None
    ):
        cmp = compare_shots(
            session.last_shot_bgr,
            working,
            session.last_roi,
            session.pending_retake_reason,  # type: ignore[arg-type]
            triage_shot2_passed=working_triage.passed,
        )
        session.trace.append(
            {
                "tool": "compare_shots",
                "result": {
                    "passed": cmp.passed,
                    "scale": cmp.scale,
                    "overlap": cmp.overlap,
                    "inlier_count": cmp.inlier_count,
                    "fail_reason": cmp.fail_reason,
                    "matcher": cmp.matcher,
                    "retake_reason": cmp.retake_reason,
                },
            }
        )
        if not cmp.passed:
            if session.retakes_remaining <= 0:
                return {
                    "correlation_id": cid,
                    "session_id": session.session_id,
                    "pack_id": session.pack_id,
                    "next_action": "escalate_human",
                    "reason": "compare_failed_max_retakes",
                    "compare": session.trace[-1]["result"],
                    "retakes_remaining": 0,
                    "trace": session.trace,
                }
            session.retakes_remaining -= 1
            return {
                "correlation_id": cid,
                "session_id": session.session_id,
                "pack_id": session.pack_id,
                "next_action": "request_capture",
                "retake_reason": session.pending_retake_reason,
                "compare_fail": cmp.fail_reason,
                "retakes_remaining": session.retakes_remaining,
                "trace": session.trace,
            }
        session.pending_retake_reason = None

    inspect = _inspect(session.pack_id, working, working_triage.roi)
    session.trace.append({"tool": f"inspect_{session.pack_id}", "result": inspect})

    if inspect.get("next_action") == "request_capture":
        if session.retakes_remaining <= 0:
            return {
                "correlation_id": cid,
                "session_id": session.session_id,
                "pack_id": session.pack_id,
                "next_action": "escalate_human",
                "reason": "inspect_needs_closer_shot",
                "retakes_remaining": 0,
                "trace": session.trace,
            }
        session.retakes_remaining -= 1
        session.pending_retake_reason = "move_closer"
        session.last_shot_bgr = working
        session.last_roi = working_triage.roi
        return {
            "correlation_id": cid,
            "session_id": session.session_id,
            "pack_id": session.pack_id,
            "next_action": "request_capture",
            "retake_reason": "move_closer",
            "retakes_remaining": session.retakes_remaining,
            "inspect": inspect,
            "trace": session.trace,
        }

    gate = validate_claims(list(inspect.get("claims") or []))
    session.trace.append({"tool": "evidence_gate", "result": gate.to_dict()})

    if not gate.allowed:
        return {
            "correlation_id": cid,
            "session_id": session.session_id,
            "pack_id": session.pack_id,
            "next_action": "escalate_human",
            "reason": "evidence_gate_blocked",
            "gate": gate.to_dict(),
            "retakes_remaining": session.retakes_remaining,
            "trace": session.trace,
        }

    session.last_shot_bgr = working
    session.last_roi = working_triage.roi

    return {
        "correlation_id": cid,
        "session_id": session.session_id,
        "pack_id": session.pack_id,
        "next_action": "finalize_report",
        "claims": gate.claims,
        "inspect": {k: v for k, v in inspect.items() if k not in {"leds"}},
        "triage": working_triage.to_dict(),
        "retakes_remaining": session.retakes_remaining,
        "trace": session.trace,
    }
