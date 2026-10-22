"""triage_frame — sharpness, glare, exposure, candidate ROI.

Decides pass vs request_capture(reason). Reasons feed compare_shots gates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

import cv2
import numpy as np

RetakeReason = Literal["move_closer", "hold_steadier", "less_glare", "blur"]

# Tuned for phone captures at ~720p; unit tests use synthetic extremes.
LAPLACIAN_MIN = 80.0
TENENGRAD_MIN = 500.0
GLARE_FRAC_MAX = 0.08
UNDEREXPOSED_MAX = 0.35
OVEREXPOSED_MAX = 0.25
MIN_ROI_AREA_FRAC = 0.04


@dataclass
class TriageResult:
    passed: bool
    retake_reason: RetakeReason | None
    sharpness: float
    tenengrad: float
    glare_fraction: float
    mean_v: float
    underexposed_frac: float
    overexposed_frac: float
    roi: tuple[int, int, int, int] | None
    fail_reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _laplacian_var(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _tenengrad(gray: np.ndarray) -> float:
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    return float((gx * gx + gy * gy).mean())


def _glare_mask(bgr: np.ndarray) -> np.ndarray:
    """Specular / washed-out pixels: high V, low S."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    return ((v > 245) & (s < 40)).astype(np.uint8) * 255


def _exposure_stats(bgr: np.ndarray) -> tuple[float, float, float]:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2].astype(np.float32)
    mean_v = float(v.mean())
    underexposed = float((v < 40).mean())
    overexposed = float((v > 245).mean())
    return mean_v, underexposed, overexposed


def _candidate_roi(bgr: np.ndarray, glare: np.ndarray) -> tuple[int, int, int, int]:
    """Largest high-edge / non-glare blob; fallback to centered crop."""
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    edges[glare > 0] = 0
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_area = 0.0
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        area = float(cw * ch)
        if area < 0.01 * w * h or area > 0.85 * w * h:
            continue
        if area > best_area:
            best_area = area
            best = (x, y, cw, ch)
    if best is not None:
        return best
    # Centered fallback (~40% of frame)
    rw, rh = int(w * 0.4), int(h * 0.4)
    return ((w - rw) // 2, (h - rh) // 2, rw, rh)


def triage_frame(bgr: np.ndarray) -> TriageResult:
    """Score a capture and optionally request a guided retake."""
    if bgr is None or bgr.size == 0:
        return TriageResult(
            passed=False,
            retake_reason="hold_steadier",
            sharpness=0.0,
            tenengrad=0.0,
            glare_fraction=1.0,
            mean_v=0.0,
            underexposed_frac=1.0,
            overexposed_frac=0.0,
            roi=None,
            fail_reasons=["empty_frame"],
        )

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    if bgr.ndim == 2:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)

    sharp = _laplacian_var(gray)
    ten = _tenengrad(gray)
    glare = _glare_mask(bgr)
    glare_frac = float(np.count_nonzero(glare) / glare.size)
    mean_v, under, over = _exposure_stats(bgr)
    roi = _candidate_roi(bgr, glare)
    h, w = bgr.shape[:2]
    roi_frac = float(roi[2] * roi[3]) / float(w * h)

    fails: list[str] = []
    reason: RetakeReason | None = None

    # Priority: glare → blur/steadiness → exposure → zoom
    if glare_frac > GLARE_FRAC_MAX:
        fails.append("glare")
        reason = "less_glare"
    if sharp < LAPLACIAN_MIN or ten < TENENGRAD_MIN:
        fails.append("blur")
        if reason is None:
            reason = "blur" if sharp < LAPLACIAN_MIN * 0.5 else "hold_steadier"
    if under > UNDEREXPOSED_MAX or over > OVEREXPOSED_MAX:
        fails.append("exposure")
        if reason is None:
            reason = "hold_steadier"
    if roi_frac < MIN_ROI_AREA_FRAC:
        fails.append("roi_too_small")
        if reason is None:
            reason = "move_closer"

    passed = len(fails) == 0
    metrics = {
        "sharpness": sharp,
        "tenengrad": ten,
        "glare_fraction": glare_frac,
        "mean_v": mean_v,
        "underexposed_frac": under,
        "overexposed_frac": over,
        "roi_area_frac": roi_frac,
    }
    return TriageResult(
        passed=passed,
        retake_reason=None if passed else reason,
        sharpness=sharp,
        tenengrad=ten,
        glare_fraction=glare_frac,
        mean_v=mean_v,
        underexposed_frac=under,
        overexposed_frac=over,
        roi=roi,
        fail_reasons=fails,
        metrics=metrics,
    )
