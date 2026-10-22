"""Bedrock tool specs + local executors. Vision outputs drive the next call."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from app.vision.compare_shots import compare_shots
from app.vision.evidence_gate import validate_claims
from app.vision.packs.appliance_leds import inspect_appliance_leds
from app.vision.packs.bike_brake_pad import inspect_bike_brake_pad
from app.vision.packs.leaf_spot import inspect_leaf_spot
from app.vision.remediate import remediate_frame
from app.vision.triage import TriageResult, triage_frame

# Tools the model may call. Terminal tools end the upload step.
TOOL_NAMES = (
    "triage_frame",
    "remediate_frame",
    "compare_shots",
    "inspect_pack",
    "request_capture",
    "finalize_report",
    "escalate_human",
)

TERMINAL_TOOLS = frozenset({"request_capture", "finalize_report", "escalate_human"})


def bedrock_tool_config() -> dict[str, Any]:
    """AWS Bedrock Converse toolConfig payload."""
    return {
        "tools": [
            {
                "toolSpec": {
                    "name": "triage_frame",
                    "description": (
                        "Score the current capture: sharpness, glare, exposure, ROI. "
                        "Call this first on every new photo. If passed=false, prefer "
                        "remediate_frame before request_capture."
                    ),
                    "inputSchema": {"json": {"type": "object", "properties": {}, "additionalProperties": False}},
                }
            },
            {
                "toolSpec": {
                    "name": "remediate_frame",
                    "description": (
                        "Software recovery (CLAHE, glare inpaint, denoise, unsharp) then re-triage. "
                        "Use when triage_frame failed. If still failing, request_capture with the "
                        "returned retake_reason."
                    ),
                    "inputSchema": {"json": {"type": "object", "properties": {}, "additionalProperties": False}},
                }
            },
            {
                "toolSpec": {
                    "name": "compare_shots",
                    "description": (
                        "Gate a retake against the previous shot with SIFT+USAC_MAGSAC "
                        "(reason-aware scale/overlap). Required when pending_retake_reason is set "
                        "before inspect_pack. If failed, request_capture again or escalate_human."
                    ),
                    "inputSchema": {"json": {"type": "object", "properties": {}, "additionalProperties": False}},
                }
            },
            {
                "toolSpec": {
                    "name": "inspect_pack",
                    "description": (
                        "Run the allowlisted pack inspector (LEDs / brake pad / leaf spots) on the "
                        "working image. Emits candidate claims — then finalize_report or "
                        "request_capture(move_closer) based on inspector next_action."
                    ),
                    "inputSchema": {"json": {"type": "object", "properties": {}, "additionalProperties": False}},
                }
            },
            {
                "toolSpec": {
                    "name": "request_capture",
                    "description": (
                        "Ask the user for another phone photo with a guided reason. "
                        "Terminal for this step."
                    ),
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "reason": {
                                    "type": "string",
                                    "enum": ["move_closer", "hold_steadier", "less_glare", "blur"],
                                }
                            },
                            "required": ["reason"],
                            "additionalProperties": False,
                        }
                    },
                }
            },
            {
                "toolSpec": {
                    "name": "finalize_report",
                    "description": (
                        "Emit bounded claims through the evidence gate. Never invent disease names "
                        "or 'safe to ride'. Prefer claims from inspect_pack. Terminal."
                    ),
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "claims": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Optional override; defaults to inspect_pack claims.",
                                }
                            },
                            "additionalProperties": False,
                        }
                    },
                }
            },
            {
                "toolSpec": {
                    "name": "escalate_human",
                    "description": "Hand off to a human when tools cannot proceed safely. Terminal.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {"reason": {"type": "string"}},
                            "required": ["reason"],
                            "additionalProperties": False,
                        }
                    },
                }
            },
        ]
    }


@dataclass
class ToolContext:
    """Mutable per-step state tools read/write."""

    pack_id: str
    working_bgr: np.ndarray
    retakes_remaining: int
    pending_retake_reason: str | None = None
    last_shot_bgr: np.ndarray | None = None
    last_roi: tuple[int, int, int, int] | None = None
    last_triage: TriageResult | None = None
    last_inspect: dict[str, Any] | None = None
    terminal: dict[str, Any] | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)


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


def execute_tool(name: str, inp: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Run one vision/control tool; may set ctx.terminal."""
    if name == "triage_frame":
        triage = triage_frame(ctx.working_bgr)
        ctx.last_triage = triage
        out = triage.to_dict()
        ctx.trace.append({"tool": name, "result": out})
        return out

    if name == "remediate_frame":
        before = ctx.last_triage or triage_frame(ctx.working_bgr)
        rem = remediate_frame(ctx.working_bgr, before)
        if rem.passed_after or rem.improved:
            ctx.working_bgr = rem.image_bgr
            ctx.last_triage = triage_frame(ctx.working_bgr)
        out = {
            "improved": rem.improved,
            "passed_after": rem.passed_after,
            "steps_applied": rem.steps_applied,
            "metrics": rem.metrics,
            "retake_reason": rem.retake_reason,
            "triage_after": rem.triage_after,
        }
        ctx.trace.append({"tool": name, "result": out})
        return out

    if name == "compare_shots":
        if (
            not ctx.pending_retake_reason
            or ctx.last_shot_bgr is None
            or ctx.last_roi is None
        ):
            out = {
                "passed": False,
                "fail_reason": "no_pending_retake_to_compare",
                "hint": "Skip compare_shots unless a prior request_capture set pending_retake_reason.",
            }
            ctx.trace.append({"tool": name, "result": out})
            return out
        triage_ok = bool(ctx.last_triage and ctx.last_triage.passed)
        cmp = compare_shots(
            ctx.last_shot_bgr,
            ctx.working_bgr,
            ctx.last_roi,
            ctx.pending_retake_reason,  # type: ignore[arg-type]
            triage_shot2_passed=triage_ok,
        )
        out = {
            "passed": cmp.passed,
            "scale": cmp.scale,
            "overlap": cmp.overlap,
            "inlier_count": cmp.inlier_count,
            "fail_reason": cmp.fail_reason,
            "matcher": cmp.matcher,
            "retake_reason": cmp.retake_reason,
        }
        if cmp.passed:
            ctx.pending_retake_reason = None
        ctx.trace.append({"tool": name, "result": out})
        return out

    if name == "inspect_pack":
        roi = ctx.last_triage.roi if ctx.last_triage else None
        inspect = _inspect(ctx.pack_id, ctx.working_bgr, roi)
        ctx.last_inspect = inspect
        ctx.trace.append({"tool": name, "result": inspect})
        return inspect

    if name == "request_capture":
        reason = str(inp.get("reason") or "hold_steadier")
        if ctx.retakes_remaining <= 0:
            ctx.terminal = {
                "next_action": "escalate_human",
                "reason": "max_retakes_exhausted",
                "last_retake_reason": reason,
            }
            ctx.trace.append({"tool": name, "result": ctx.terminal})
            return ctx.terminal
        ctx.retakes_remaining -= 1
        ctx.pending_retake_reason = reason
        ctx.last_shot_bgr = ctx.working_bgr.copy()
        ctx.last_roi = ctx.last_triage.roi if ctx.last_triage else None
        ctx.terminal = {
            "next_action": "request_capture",
            "retake_reason": reason,
            "retakes_remaining": ctx.retakes_remaining,
        }
        ctx.trace.append({"tool": name, "result": ctx.terminal})
        return ctx.terminal

    if name == "finalize_report":
        claims = list(inp.get("claims") or [])
        if not claims and ctx.last_inspect:
            claims = list(ctx.last_inspect.get("claims") or [])
        gate = validate_claims(claims)
        ctx.trace.append({"tool": "evidence_gate", "result": gate.to_dict()})
        if not gate.allowed:
            ctx.terminal = {
                "next_action": "escalate_human",
                "reason": "evidence_gate_blocked",
                "gate": gate.to_dict(),
            }
        else:
            ctx.terminal = {
                "next_action": "finalize_report",
                "claims": gate.claims,
                "inspect": {
                    k: v
                    for k, v in (ctx.last_inspect or {}).items()
                    if k not in {"leds"}
                },
            }
        ctx.trace.append({"tool": name, "result": ctx.terminal})
        return ctx.terminal

    if name == "escalate_human":
        ctx.terminal = {
            "next_action": "escalate_human",
            "reason": str(inp.get("reason") or "model_escalated"),
        }
        ctx.trace.append({"tool": name, "result": ctx.terminal})
        return ctx.terminal

    err = {"error": f"unknown_tool:{name}"}
    ctx.trace.append({"tool": name, "result": err})
    return err


def encode_jpeg_thumb(bgr: np.ndarray, max_side: int = 512, quality: int = 75) -> bytes:
    h, w = bgr.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale < 1.0:
        bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("jpeg_encode_failed")
    return bytes(buf)
