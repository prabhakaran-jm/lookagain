"""Fixture pairs must support glare→retake→compare pass without props."""

from __future__ import annotations

from pathlib import Path

import cv2

from app.vision.compare_shots import compare_shots
from app.vision.triage import triage_frame

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "docs" / "fixtures"


def test_glare_retake_pair_compare_passes():
    shot1 = cv2.imread(str(FIX / "leds_glare_retake" / "shot1.jpg"))
    shot2 = cv2.imread(str(FIX / "leds_glare_retake" / "shot2.jpg"))
    assert shot1 is not None and shot2 is not None
    t1 = triage_frame(shot1)
    t2 = triage_frame(shot2)
    assert not t1.passed
    assert t1.retake_reason == "less_glare"
    assert t2.passed
    assert t1.roi is not None
    cmp = compare_shots(shot1, shot2, t1.roi, "less_glare", triage_shot2_passed=True)
    assert cmp.passed, cmp


def test_closer_retake_pair_compare_passes():
    shot1 = cv2.imread(str(FIX / "leds_closer_retake" / "shot1.jpg"))
    shot2 = cv2.imread(str(FIX / "leds_closer_retake" / "shot2.jpg"))
    assert shot1 is not None and shot2 is not None
    t1 = triage_frame(shot1)
    assert t1.roi is not None
    cmp = compare_shots(shot1, shot2, t1.roi, "move_closer", triage_shot2_passed=True)
    assert cmp.passed, cmp
    assert cmp.scale >= 1.3


def test_agent_demo_pairs_ok():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    for pair_id, reason in (
        ("leds_glare_retake", None),
        ("leds_closer_retake", "move_closer"),
    ):
        res = client.post(
            "/api/demo/run_pair",
            data={"pair_id": pair_id, "pack_id": "appliance_leds"},
        )
        assert res.status_code == 200, pair_id
        body = res.json()
        assert body["step1"]["next_action"] == "request_capture", body["step1"]
        if reason:
            assert body["step1"].get("retake_reason") == reason
        assert body["demo_ok"] is True, body
        assert body["step2"]["next_action"] == "finalize_report"
        assert "compare_shots" in (body["step2"].get("agent") or {}).get("tools_called", [])
