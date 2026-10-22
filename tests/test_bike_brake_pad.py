"""Synthetic brake-pad thickness indicator tests."""

from __future__ import annotations

import cv2
import numpy as np

from app.vision.evidence_gate import validate_claims
from app.vision.packs.bike_brake_pad import inspect_bike_brake_pad


def test_detects_dark_pad_strip():
    img = np.full((240, 320, 3), 180, dtype=np.uint8)  # bright rotor-like bg
    # Dark pad compound strip with edge contrast
    img[90:150, 140:200] = (25, 25, 25)
    cv2.rectangle(img, (140, 90), (199, 149), (60, 60, 60), 1)
    result = inspect_bike_brake_pad(img)
    assert result.pad_region_found, result
    assert result.thickness_px > 0
    assert result.wear_band in {"thick", "medium", "thin"}
    assert result.next_action == "finalize_report"
    gate = validate_claims(result.claims)
    assert gate.allowed
    assert all("safe to ride" not in c.lower() for c in gate.claims)


def test_empty_pad_requests_closer():
    img = np.full((240, 320, 3), 200, dtype=np.uint8)
    result = inspect_bike_brake_pad(img)
    assert not result.pad_region_found
    assert result.next_action == "request_capture"
