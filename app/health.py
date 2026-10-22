"""Build / COOL / KleidiCV status for /health and reports."""

from __future__ import annotations

import os
import platform
from typing import Any


def opencv_build_info() -> dict[str, Any]:
    try:
        import cv2
    except ImportError:
        return {"available": False, "error": "opencv not installed"}

    info_raw = cv2.getBuildInformation() if hasattr(cv2, "getBuildInformation") else ""
    kleidicv = "unknown"
    lower = info_raw.lower()
    if "kleidicv" in lower or "kleidi" in lower:
        kleidicv = "mentioned_in_build_info"
    elif "neon" in lower and platform.machine().lower() in {"aarch64", "arm64"}:
        kleidicv = "not_explicit_arm_neon_present"

    cool_hint = bool(
        os.environ.get("LOOKAGAIN_COOL")
        or os.path.exists("/opt/cool")
        or "cool" in (getattr(cv2, "__file__", "") or "").lower()
    )

    return {
        "available": True,
        "version": getattr(cv2, "__version__", "unknown"),
        "file": getattr(cv2, "__file__", None),
        "cool_env": cool_hint,
        "kleidicv": kleidicv,
        "has_aliked": hasattr(cv2, "ALIKED") or hasattr(cv2, "ALIKED_create"),
        "has_lightglue": hasattr(cv2, "LightGlueMatcher")
        or hasattr(cv2, "LightGlueMatcher_create"),
        "has_sift": hasattr(cv2, "SIFT_create"),
        "has_usac_magsac": hasattr(cv2, "USAC_MAGSAC"),
        "aliked_needs_model_path": True,
        "build_info_excerpt": _excerpt(info_raw),
    }


def _excerpt(build_info: str, limit: int = 1200) -> str:
    if not build_info:
        return ""
    lines = []
    for line in build_info.splitlines():
        key = line.split(":")[0].strip().lower() if ":" in line else ""
        if any(
            k in key
            for k in (
                "version",
                "platform",
                "cpu",
                "neon",
                "kleidi",
                "dnn",
                "parallel",
                "to be",
            )
        ):
            lines.append(line.rstrip())
        if len("\n".join(lines)) > limit:
            break
    return "\n".join(lines)[:limit]


def health_payload(correlation_id: str | None = None) -> dict[str, Any]:
    agent_mode = os.environ.get("LOOKAGAIN_AGENT", "auto")
    model = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
    return {
        "service": "lookagain",
        "status": "ok",
        "correlation_id": correlation_id,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "opencv": opencv_build_info(),
        "agent": {
            "mode": agent_mode,
            "bedrock_model_id": model,
            "tools": [
                "triage_frame",
                "remediate_frame",
                "compare_shots",
                "inspect_pack",
                "request_capture",
                "finalize_report",
                "escalate_human",
            ],
        },
        "approved_packs": [
            "appliance_leds",
            "bike_brake_pad",
            "leaf_spot",
        ],
    }
