"""Scale/overlap tests for compare_shots (SIFT + ROI projection)."""

from __future__ import annotations

import cv2
import numpy as np

from app.vision.compare_shots import (
    _overlap_fraction,
    _polygon_area,
    _roi_corners,
    compare_shots,
)


def test_projected_roi_scale_from_known_homography():
    """Known 1.5x isotropic scale H → projected ROI scale ≈ 1.5."""
    roi = (100, 80, 200, 160)
    corners = _roi_corners(roi).reshape(-1, 1, 2)
    H = np.array([[1.5, 0, 0], [0, 1.5, 0], [0, 0, 1]], dtype=np.float64)
    projected = cv2.perspectiveTransform(corners, H).reshape(-1, 2)
    area1 = _polygon_area(_roi_corners(roi))
    area2 = _polygon_area(projected)
    scale = float(np.sqrt(area2 / area1))
    assert abs(scale - 1.5) < 1e-6
    overlap = _overlap_fraction(projected, frame_w=800, frame_h=600)
    assert overlap > 0.99


def test_synthetic_sift_zoom_reports_closer_scale():
    """Build shot2 by resizing a textured ROI 1.5x; SIFT must see scale-up."""
    rng = np.random.default_rng(7)
    base = rng.integers(40, 220, (480, 640), dtype=np.uint8)
    # Dense unique blobs for SIFT
    for i in range(40):
        cv2.circle(
            base,
            (int(rng.integers(30, 610)), int(rng.integers(30, 450))),
            int(rng.integers(6, 18)),
            int(rng.integers(0, 255)),
            -1,
        )
    shot1 = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    x, y, w, h = 160, 120, 240, 180
    crop = shot1[y : y + h, x : x + w]
    shot2 = cv2.resize(crop, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)

    result = compare_shots(shot1, shot2, (x, y, w, h), "move_closer", True)
    assert result.matcher == "SIFT+USAC_MAGSAC"
    assert result.inlier_count >= 8, result
    assert result.scale > 1.15, f"expected zoom-in scale, got {result}"


def test_hold_steadier_does_not_require_1_3_zoom():
    shot1 = np.zeros((400, 500, 3), dtype=np.uint8)
    rng = np.random.default_rng(3)
    for i in range(30):
        cv2.rectangle(
            shot1,
            (int(rng.integers(10, 400)), int(rng.integers(10, 300))),
            (int(rng.integers(50, 480)), int(rng.integers(50, 380))),
            (int(rng.integers(50, 255)),) * 3,
            -1,
        )
    shot2 = cv2.convertScaleAbs(shot1, alpha=1.05, beta=5)
    roi = (80, 60, 300, 220)
    result = compare_shots(shot1, shot2, roi, "hold_steadier", True)
    if result.inlier_count >= 12 and result.overlap >= 0.5:
        assert result.passed or result.fail_reason == "scale_not_near_one"
        # Must not fail solely because scale < 1.3
        assert result.fail_reason != "scale_not_increased"
