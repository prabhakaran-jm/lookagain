"""Bedrock tool-use loop with a fake Converse client (no AWS calls)."""

from __future__ import annotations

import json

import cv2
import numpy as np
import pytest

from app.agent.bedrock_loop import json_safe, run_bedrock_agent
from app.agent.session import Session, run_step
from app.agent.tools import ToolContext, execute_tool


def _led_image() -> np.ndarray:
    img = np.full((240, 320, 3), 30, dtype=np.uint8)
    cv2.circle(img, (80, 120), 12, (40, 220, 40), -1)
    cv2.circle(img, (200, 120), 12, (40, 40, 220), -1)
    return img


def _jpeg(bgr: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", bgr)
    assert ok
    return bytes(buf)


class ScriptedBedrock:
    """Returns a fixed sequence of toolUse responses."""

    def __init__(self, script: list[str]):
        self.script = list(script)
        self.calls = 0
        self.messages_seen: list = []

    def converse(self, **kwargs):
        self.messages_seen.append(kwargs.get("messages"))
        self.calls += 1
        if not self.script:
            return {
                "stopReason": "end_turn",
                "output": {"message": {"role": "assistant", "content": [{"text": "done"}]}},
            }
        name = self.script.pop(0)
        inp: dict = {}
        if name == "request_capture":
            inp = {"reason": "less_glare"}
        if name == "escalate_human":
            inp = {"reason": "test"}
        return {
            "stopReason": "tool_use",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": f"t{self.calls}",
                                "name": name,
                                "input": inp,
                            }
                        }
                    ],
                }
            },
        }


def test_scripted_bedrock_path_finalize():
    img = _led_image()
    # Sharp textured bg helps triage pass on synthetic LEDs
    rng = np.random.default_rng(1)
    noise = rng.integers(0, 40, img.shape, dtype=np.uint8)
    img = cv2.add(img, noise)

    ctx = ToolContext(pack_id="appliance_leds", working_bgr=img, retakes_remaining=3)
    client = ScriptedBedrock(
        ["triage_frame", "inspect_pack", "finalize_report"]
    )
    out = run_bedrock_agent(ctx, client=client, max_turns=6)
    assert out["next_action"] == "finalize_report", out
    assert out["agent"]["backend"] == "bedrock_converse"
    assert out["agent"]["tools_called"] == [
        "triage_frame",
        "inspect_pack",
        "finalize_report",
    ]
    assert out["claims"]


def test_scripted_bedrock_retake_after_glare_tools():
    img = np.full((240, 320, 3), 255, dtype=np.uint8)  # full glare wash
    ctx = ToolContext(pack_id="appliance_leds", working_bgr=img, retakes_remaining=3)
    client = ScriptedBedrock(
        ["triage_frame", "remediate_frame", "request_capture"]
    )
    out = run_bedrock_agent(ctx, client=client, max_turns=6)
    assert out["next_action"] == "request_capture", out
    assert "remediate_frame" in out["agent"]["tools_called"]
    assert out["retakes_remaining"] == 2


def test_heuristic_still_finalizes_leds(monkeypatch):
    monkeypatch.setenv("LOOKAGAIN_AGENT", "heuristic")
    session = Session(
        session_id="s1",
        pack_id="appliance_leds",
        correlation_id="c1",
    )
    img = _led_image()
    rng = np.random.default_rng(2)
    img = cv2.add(img, rng.integers(0, 50, img.shape, dtype=np.uint8))
    out = run_step(session, _jpeg(img))
    assert out["agent"]["backend"] == "heuristic"
    assert out["next_action"] in {"finalize_report", "request_capture"}


def test_execute_tool_unknown():
    ctx = ToolContext(pack_id="appliance_leds", working_bgr=_led_image(), retakes_remaining=1)
    out = execute_tool("not_a_tool", {}, ctx)
    assert "error" in out


def test_json_safe_converts_roi_tuple():
    raw = {"roi": (96, 72, 128, 96), "ok": True, "n": np.float64(1.5)}
    safe = json_safe(raw)
    assert safe["roi"] == [96, 72, 128, 96]
    assert isinstance(safe["roi"], list)
    assert safe["n"] == pytest.approx(1.5)
    # Must be acceptable to Bedrock document encoder
    json.dumps(safe)
