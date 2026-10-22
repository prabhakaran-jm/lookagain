"""Unit tests for triage_frame and remediate_frame."""

from __future__ import annotations

import cv2
import numpy as np

from app.vision.remediate import remediate_frame
from app.vision.triage import triage_frame


def _textured(h: int = 480, w: int = 640, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    gray = rng.integers(60, 200, (h, w), dtype=np.uint8)
    for _ in range(50):
        cv2.circle(
            gray,
            (int(rng.integers(20, w - 20)), int(rng.integers(20, h - 20))),
            int(rng.integers(4, 16)),
            int(rng.integers(0, 255)),
            -1,
        )
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def test_sharp_textured_frame_passes():
    img = _textured()
    result = triage_frame(img)
    assert result.passed, result
    assert result.roi is not None
    assert result.retake_reason is None


def test_blurry_frame_requests_retake():
    img = _textured()
    blurry = cv2.GaussianBlur(img, (31, 31), 0)
    result = triage_frame(blurry)
    assert not result.passed
    assert result.retake_reason in {"blur", "hold_steadier"}
    assert "blur" in result.fail_reasons


def test_glare_blob_requests_less_glare():
    img = _textured()
    # Specular wash large enough to exceed GLARE_FRAC_MAX (8%)
    img[40:280, 60:420] = (255, 255, 255)
    result = triage_frame(img)
    assert result.glare_fraction > 0.08, result.glare_fraction
    assert not result.passed
    assert result.retake_reason == "less_glare"
    assert "glare" in result.fail_reasons


def test_remediate_improves_underexposed():
    img = _textured()
    dark = (img.astype(np.float32) * 0.25).astype(np.uint8)
    before = triage_frame(dark)
    rem = remediate_frame(dark, before)
    assert "clahe_lab" in rem.steps_applied
    assert rem.metrics["sharpness_after"] >= rem.metrics["sharpness_before"] * 0.9
    # CLAHE should lift mean V
    assert rem.triage_after["mean_v"] > rem.triage_before["mean_v"]
