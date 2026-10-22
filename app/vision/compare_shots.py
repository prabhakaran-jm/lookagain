"""Reason-aware compare_shots: register shot2 to shot1 ROI via SIFT + USAC_MAGSAC.

Scale/overlap come from projecting the shot-1 ROI polygon — not det(H[:2,:2]).
ALIKED unavailable on current COOL AMI → SIFT is the locked matcher.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

RetakeReason = Literal["move_closer", "hold_steadier", "less_glare", "blur"]

MAX_RETAKES = 3
MIN_INLIERS = 12
CLOSER_SCALE_MIN = 1.3
SAME_SCALE_LO = 0.85
SAME_SCALE_HI = 1.15


@dataclass
class CompareResult:
    passed: bool
    retake_reason: str
    scale: float
    overlap: float
    inlier_count: int
    matcher: str
    fail_reason: str | None = None
    metrics: dict[str, float] | None = None


def _roi_corners(roi: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = roi
    return np.array(
        [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
        dtype=np.float64,
    )


def _polygon_area(pts: np.ndarray) -> float:
    return float(abs(cv2.contourArea(pts.astype(np.float32))))


def _overlap_fraction(projected: np.ndarray, frame_w: int, frame_h: int) -> float:
    """Fraction of projected polygon area that lies inside the frame."""
    frame = np.array(
        [[0, 0], [frame_w, 0], [frame_w, frame_h], [0, frame_h]],
        dtype=np.float32,
    )
    proj = projected.astype(np.float32).reshape(-1, 2)
    # OpenCV 5: (area: float, intersection_pts: ndarray)
    result = cv2.intersectConvexConvex(proj, frame)
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], float):
        inter_area = abs(float(result[0]))
    else:
        inter_pts = result[0] if isinstance(result, tuple) else result
        if inter_pts is None or len(inter_pts) == 0:
            return 0.0
        inter_area = abs(cv2.contourArea(np.asarray(inter_pts, dtype=np.float32)))
    proj_area = abs(cv2.contourArea(proj.reshape(-1, 1, 2)))
    if proj_area <= 1e-6:
        return 0.0
    return float(inter_area / proj_area)


def _find_homography_sift(
    img1: np.ndarray, img2: np.ndarray
) -> tuple[np.ndarray | None, int]:
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY) if img1.ndim == 3 else img1
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY) if img2.ndim == 3 else img2
    sift = cv2.SIFT_create()
    k1, d1 = sift.detectAndCompute(gray1, None)
    k2, d2 = sift.detectAndCompute(gray2, None)
    if d1 is None or d2 is None or len(k1) < 8 or len(k2) < 8:
        return None, 0
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    knn = matcher.knnMatch(d1, d2, k=2)
    good = []
    for pair in knn:
        if len(pair) != 2:
            continue
        m, n = pair
        if m.distance < 0.75 * n.distance:
            good.append(m)
    if len(good) < 8:
        return None, 0
    pts1 = np.float32([k1[m.queryIdx].pt for m in good])
    pts2 = np.float32([k2[m.trainIdx].pt for m in good])
    H, mask = cv2.findHomography(pts1, pts2, cv2.USAC_MAGSAC, 3.0)
    if H is None or mask is None:
        return None, 0
    return H, int(mask.ravel().sum())


def compare_shots(
    shot1_bgr: np.ndarray,
    shot2_bgr: np.ndarray,
    roi_shot1: tuple[int, int, int, int],
    retake_reason: RetakeReason,
    triage_shot2_passed: bool = True,
) -> CompareResult:
    """Gate shot2 against shot1 using reason-aware scale + overlap + inliers.

    Homography maps shot1 → shot2 (pts_shot1 src, pts_shot2 dst).
    """
    H, inliers = _find_homography_sift(shot1_bgr, shot2_bgr)
    if H is None:
        return CompareResult(
            passed=False,
            retake_reason=retake_reason,
            scale=0.0,
            overlap=0.0,
            inlier_count=inliers,
            matcher="SIFT+USAC_MAGSAC",
            fail_reason="homography_failed",
            metrics={"inlier_count": float(inliers)},
        )

    corners = _roi_corners(roi_shot1).reshape(-1, 1, 2)
    projected = cv2.perspectiveTransform(corners, H).reshape(-1, 2)
    area1 = max(_polygon_area(_roi_corners(roi_shot1)), 1.0)
    area2 = max(_polygon_area(projected), 1e-6)
    scale = float(np.sqrt(area2 / area1))
    h2, w2 = shot2_bgr.shape[:2]
    overlap = _overlap_fraction(projected, w2, h2)

    metrics = {
        "scale": scale,
        "overlap": overlap,
        "inlier_count": float(inliers),
    }

    if inliers < MIN_INLIERS:
        return CompareResult(
            False, retake_reason, scale, overlap, inliers, "SIFT+USAC_MAGSAC",
            "insufficient_inliers", metrics,
        )
    if overlap < 0.5:
        return CompareResult(
            False, retake_reason, scale, overlap, inliers, "SIFT+USAC_MAGSAC",
            "roi_out_of_frame", metrics,
        )

    if retake_reason == "move_closer":
        ok = scale >= CLOSER_SCALE_MIN
        fail = None if ok else "scale_not_increased"
    else:
        # hold_steadier / less_glare / blur: same distance, better quality
        ok = SAME_SCALE_LO <= scale <= SAME_SCALE_HI and triage_shot2_passed
        fail = None if ok else (
            "triage_failed" if not triage_shot2_passed else "scale_not_near_one"
        )

    return CompareResult(
        passed=ok,
        retake_reason=retake_reason,
        scale=scale,
        overlap=overlap,
        inlier_count=inliers,
        matcher="SIFT+USAC_MAGSAC",
        fail_reason=fail,
        metrics=metrics,
    )
