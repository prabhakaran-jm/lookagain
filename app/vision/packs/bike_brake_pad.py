"""bike_brake_pad — estimate pad thickness indicator from a rotor/pad ROI.

Emits wear-indicator observations only — never 'safe to ride'.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


@dataclass
class BrakeInspectResult:
    pad_region_found: bool
    thickness_px: float
    thickness_ratio: float
    wear_band: str  # thick | medium | thin | unknown
    claims: list[str]
    next_action: str = "finalize_report"
    metrics: dict[str, float] = field(default_factory=dict)
    roi: tuple[int, int, int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pad_region_found": self.pad_region_found,
            "thickness_px": self.thickness_px,
            "thickness_ratio": self.thickness_ratio,
            "wear_band": self.wear_band,
            "claims": self.claims,
            "next_action": self.next_action,
            "metrics": self.metrics,
            "roi": self.roi,
        }


def _pad_mask(bgr: np.ndarray) -> np.ndarray:
    """Dark composite pad material vs brighter rotor/metal."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    # Low-V dark region typical of pad compound
    dark = cv2.inRange(hsv, (0, 0, 0), (180, 120, 90))
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    # Prefer dark regions near strong edges (pad against rotor)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    near_edge = cv2.dilate(edges, kernel, iterations=2)
    mask = cv2.bitwise_and(dark, near_edge)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    return mask


def _thickness_from_mask(mask: np.ndarray) -> tuple[float, tuple[int, int, int, int] | None]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0, None
    h, w = mask.shape[:2]
    min_area = 0.005 * w * h
    best = None
    best_area = 0.0
    for c in contours:
        area = float(cv2.contourArea(c))
        if area < min_area:
            continue
        if area > best_area:
            best_area = area
            best = c
    if best is None:
        return 0.0, None
    x, y, bw, bh = cv2.boundingRect(best)
    # Thickness ≈ smaller axis of the pad blob
    thickness = float(min(bw, bh))
    return thickness, (x, y, bw, bh)


def _wear_band(ratio: float) -> str:
    if ratio <= 0:
        return "unknown"
    if ratio >= 0.12:
        return "thick"
    if ratio >= 0.06:
        return "medium"
    return "thin"


def inspect_bike_brake_pad(
    bgr: np.ndarray,
    roi: tuple[int, int, int, int] | None = None,
) -> BrakeInspectResult:
    h, w = bgr.shape[:2]
    if roi is not None:
        x, y, rw, rh = roi
        x, y = max(0, x), max(0, y)
        crop = bgr[y : y + rh, x : x + rw]
        ox, oy = x, y
    else:
        crop = bgr
        ox, oy = 0, 0

    if crop.size == 0:
        return BrakeInspectResult(
            pad_region_found=False,
            thickness_px=0.0,
            thickness_ratio=0.0,
            wear_band="unknown",
            claims=["Empty frame — retake of the brake caliper/pad area needed."],
            next_action="request_capture",
        )

    mask = _pad_mask(crop)
    thickness, local_roi = _thickness_from_mask(mask)
    ch = crop.shape[0]
    ratio = float(thickness / max(ch, 1))
    band = _wear_band(ratio)

    abs_roi = None
    if local_roi is not None:
        lx, ly, lw, lh = local_roi
        abs_roi = (lx + ox, ly + oy, lw, lh)

    if local_roi is None or thickness < 3:
        return BrakeInspectResult(
            pad_region_found=False,
            thickness_px=thickness,
            thickness_ratio=ratio,
            wear_band="unknown",
            claims=[
                "No clear pad compound region detected — move closer to the pad/rotor gap."
            ],
            next_action="request_capture",
            metrics={"thickness_px": thickness, "thickness_ratio": ratio},
            roi=abs_roi,
        )

    claims = [
        f"Pad wear indicator band: {band} (relative thickness {ratio:.3f} of ROI height).",
        "Visual wear band only — verify with a mechanic before riding; LookAgain does not certify brake safety.",
    ]
    return BrakeInspectResult(
        pad_region_found=True,
        thickness_px=thickness,
        thickness_ratio=ratio,
        wear_band=band,
        claims=claims,
        next_action="finalize_report",
        metrics={
            "thickness_px": thickness,
            "thickness_ratio": ratio,
            "frame_w": float(w),
            "frame_h": float(h),
        },
        roi=abs_roi,
    )
