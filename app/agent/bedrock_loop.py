"""Thin Bedrock Converse tool-use loop — vision tool results choose the next tool."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from app.agent.tools import (
    TERMINAL_TOOLS,
    ToolContext,
    bedrock_tool_config,
    encode_jpeg_thumb,
    execute_tool,
)

DEFAULT_MODEL = os.environ.get(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
)
DEFAULT_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
MAX_TURNS = int(os.environ.get("LOOKAGAIN_BEDROCK_MAX_TURNS", "8"))


SYSTEM_PROMPT = """You are LookAgain, an agentic visual troubleshooting agent for the OpenCV AI Competition.

Rules:
- Vision metrics MUST decide the next tool. Do not skip triage_frame on a new photo.
- If triage_frame fails: call remediate_frame. If still failing: request_capture with that retake_reason.
- If pending_retake_reason is set from a prior step: call compare_shots before inspect_pack.
- After a clean frame: inspect_pack, then finalize_report using inspector claims (or request_capture if inspector says so).
- Never claim "safe to ride", disease names, or medical diagnoses — evidence_gate will block them.
- escalate_human only when retakes are exhausted or evidence is unsafe.
- Call exactly one tool at a time. Prefer the minimal path to a terminal tool.
"""


class ConverseClient(Protocol):
    def converse(self, **kwargs: Any) -> dict[str, Any]: ...


def json_safe(value: Any) -> Any:
    """Bedrock document types reject tuple/numpy — coerce to plain JSON."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, (int, float)):
        # numpy scalars also subclass these in some builds; normalize
        return value.item() if hasattr(value, "item") and not isinstance(value, bool) else value
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, "tolist"):
        try:
            return json_safe(value.tolist())
        except Exception:  # noqa: BLE001
            pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # noqa: BLE001
            pass
    return str(value)


def _boto_client(region: str | None = None) -> Any:
    import boto3

    return boto3.client("bedrock-runtime", region_name=region or DEFAULT_REGION)


def bedrock_available(client: ConverseClient | None = None) -> bool:
    """Best-effort probe — False means caller should use heuristic loop."""
    try:
        c = client or _boto_client()
        # Lightweight: list is on bedrock control plane; here just ensure client builds.
        return c is not None
    except Exception:
        return False


def _tool_uses(message: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for block in message.get("content") or []:
        if "toolUse" in block:
            out.append(block["toolUse"])
    return out


def _assistant_text(message: dict[str, Any]) -> str:
    parts = []
    for block in message.get("content") or []:
        if "text" in block:
            parts.append(block["text"])
    return "\n".join(parts).strip()


def run_bedrock_agent(
    ctx: ToolContext,
    *,
    client: ConverseClient | None = None,
    model_id: str | None = None,
    max_turns: int = MAX_TURNS,
) -> dict[str, Any]:
    """Drive tool-use until a terminal tool or turn budget."""
    c = client or _boto_client()
    model = model_id or DEFAULT_MODEL

    state_blob = {
        "pack_id": ctx.pack_id,
        "retakes_remaining": ctx.retakes_remaining,
        "pending_retake_reason": ctx.pending_retake_reason,
        "has_prior_shot": ctx.last_shot_bgr is not None,
    }
    thumb = encode_jpeg_thumb(ctx.working_bgr)
    user_content: list[dict[str, Any]] = [
        {
            "text": (
                "New phone capture for LookAgain.\n"
                f"Session state: {json.dumps(state_blob)}\n"
                "Call triage_frame first, then choose the next tool from its metrics."
            )
        },
        {"image": {"format": "jpeg", "source": {"bytes": thumb}}},
    ]
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]

    model_notes: list[str] = []
    tools_called: list[str] = []

    for _turn in range(max_turns):
        resp = c.converse(
            modelId=model,
            messages=messages,
            system=[{"text": SYSTEM_PROMPT}],
            toolConfig=bedrock_tool_config(),
            inferenceConfig={"maxTokens": 1024, "temperature": 0},
        )
        stop = resp.get("stopReason")
        assistant = resp.get("output", {}).get("message") or {"role": "assistant", "content": []}
        messages.append(assistant)
        text = _assistant_text(assistant)
        if text:
            model_notes.append(text)

        uses = _tool_uses(assistant)
        if not uses:
            # Model ended without a tool — escalate rather than invent
            ctx.terminal = {
                "next_action": "escalate_human",
                "reason": "model_ended_without_tool",
                "stop_reason": stop,
                "model_notes": model_notes,
            }
            break

        tool_result_blocks: list[dict[str, Any]] = []
        for use in uses:
            name = use.get("name") or ""
            tool_use_id = use.get("toolUseId") or "tool"
            inp = use.get("input") or {}
            if not isinstance(inp, dict):
                inp = {}
            result = execute_tool(name, inp, ctx)
            tools_called.append(name)
            safe = json_safe(result)
            tool_result_blocks.append(
                {
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": safe}],
                        "status": "success" if "error" not in result else "error",
                    }
                }
            )
            if name in TERMINAL_TOOLS or ctx.terminal is not None:
                break

        messages.append({"role": "user", "content": tool_result_blocks})

        if ctx.terminal is not None:
            break

    if ctx.terminal is None:
        ctx.terminal = {
            "next_action": "escalate_human",
            "reason": "max_agent_turns",
            "tools_called": tools_called,
        }

    out = dict(ctx.terminal)
    out["agent"] = {
        "backend": "bedrock_converse",
        "model_id": model,
        "tools_called": tools_called,
        "model_notes": model_notes[-3:],
        "vision_drove_tools": len(tools_called) >= 1,
    }
    out["trace"] = ctx.trace
    out["retakes_remaining"] = ctx.retakes_remaining
    return out
