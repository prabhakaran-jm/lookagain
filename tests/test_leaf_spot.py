"""Synthetic leaf-spot detection without disease naming."""

from __future__ import annotations

import cv2
import numpy as np

from app.vision.evidence_gate import validate_claims
from app.vision.packs.leaf_spot import inspect_leaf_spot


def test_green_leaf_with_brown_spots():
    img = np.zeros((300, 400, 3), dtype=np.uint8)
    # Green leaf ellipse (BGR)
    cv2.ellipse(img, (200, 150), (150, 100), 0, 0, 360, (40, 140, 40), -1)
    cv2.circle(img, (160, 130), 12, (20, 60, 140), -1)  # brown-ish
    cv2.circle(img, (230, 170), 10, (30, 80, 160), -1)
    result = inspect_leaf_spot(img)
    assert result.leaf_found, result
    assert result.spot_count >= 1
    assert result.severity_band in {"low", "moderate", "high"}
    assert result.next_action == "finalize_report"
    gate = validate_claims(result.claims)
    assert gate.allowed
    joined = " ".join(gate.claims).lower()
    assert "mildew" not in joined
    assert "blight" not in joined


def test_no_leaf_requests_closer():
    img = np.full((240, 320, 3), 40, dtype=np.uint8)
    result = inspect_leaf_spot(img)
    assert not result.leaf_found
    assert result.next_action == "request_capture"
