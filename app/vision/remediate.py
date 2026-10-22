"""remediate_frame — software recovery before asking for a retake.

Applies CLAHE, bilateral denoise, glare inpaint, and mild unsharp.
Re-triages; if still failing, caller should request_capture(reason).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from app.vision.triage import TriageResult, _glare_mask, triage_frame


@dataclass
class RemediateResult:
    improved: bool
    passed_after: bool
    steps_applied: list[str]
    triage_before: dict[str, Any]
    triage_after: dict[str, Any]
    image_bgr: np.ndarray
    retake_reason: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self, include_image: bool = False) -> dict[str, Any]:
        d = {
            "improved": self.improved,
            "passed_after": self.passed_after,
            "steps_applied": self.steps_applied,
            "triage_before": self.triage_before,
            "triage_after": self.triage_after,
            "retake_reason": self.retake_reason,
            "metrics": self.metrics,
        }
        if include_image:
            d["image_bgr"] = self.image_bgr
        return d


def _clahe_lab(bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)


def _inpaint_glare(bgr: np.ndarray) -> np.ndarray:
    mask = _glare_mask(bgr)
    if np.count_nonzero(mask) == 0:
        return bgr
    # Dilate so inpaint covers halo
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.dilate(mask, kernel, iterations=1)
    return cv2.inpaint(bgr, mask, 3, cv2.INPAINT_TELEA)


def _unsharp(bgr: np.ndarray, amount: float = 0.6) -> np.ndarray:
    blur = cv2.GaussianBlur(bgr, (0, 0), 1.2)
    sharp = cv2.addWeighted(bgr, 1.0 + amount, blur, -amount, 0)
    return np.clip(sharp, 0, 255).astype(np.uint8)


def remediate_frame(bgr: np.ndarray, triage: TriageResult | None = None) -> RemediateResult:
    """Attempt recovery; return remediated image + post-triage status."""
    before = triage or triage_frame(bgr)
    steps: list[str] = []
    out = bgr.copy()

    if before.underexposed_frac > 0.15 or before.mean_v < 90:
        out = _clahe_lab(out)
        steps.append("clahe_lab")

    if before.glare_fraction > 0.02:
        out = _inpaint_glare(out)
        steps.append("inpaint_glare")

    # Light denoise always — cheap and helps hold_steadier cases
    out = cv2.bilateralFilter(out, d=5, sigmaColor=40, sigmaSpace=40)
    steps.append("bilateral")

    if before.sharpness < 120 or "blur" in before.fail_reasons:
        out = _unsharp(out)
        steps.append("unsharp")

    after = triage_frame(out)
    improved = (
        after.sharpness > before.sharpness * 1.05
        or after.glare_fraction < before.glare_fraction * 0.85
        or (after.passed and not before.passed)
    )

    return RemediateResult(
        improved=improved,
        passed_after=after.passed,
        steps_applied=steps,
        triage_before=before.to_dict(),
        triage_after=after.to_dict(),
        image_bgr=out,
        retake_reason=None if after.passed else after.retake_reason,
        metrics={
            "sharpness_before": before.sharpness,
            "sharpness_after": after.sharpness,
            "glare_before": before.glare_fraction,
            "glare_after": after.glare_fraction,
        },
    )
