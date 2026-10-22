"""leaf_spot — detect discolored leaf spots without naming a disease.

Bounded claims only — no powdery mildew / blight / diagnosis language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


@dataclass
class LeafSpotResult:
    leaf_found: bool
    spot_count: int
    spot_area_frac: float
    severity_band: str  # none | low | moderate | high | unknown
    claims: list[str]
    next_action: str = "finalize_report"
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "leaf_found": self.leaf_found,
            "spot_count": self.spot_count,
            "spot_area_frac": self.spot_area_frac,
            "severity_band": self.severity_band,
            "claims": self.claims,
            "next_action": self.next_action,
            "metrics": self.metrics,
        }


def _leaf_mask(bgr: np.ndarray) -> np.ndarray:
    """Filled leaf silhouette from green tissue (spots inside still count)."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, (25, 40, 40), (95, 255, 255))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, kernel, iterations=2)
    green = cv2.morphologyEx(green, cv2.MORPH_OPEN, kernel, iterations=1)
    contours, _ = cv2.findContours(green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(green)
    if not contours:
        return filled
    largest = max(contours, key=cv2.contourArea)
    cv2.drawContours(filled, [largest], -1, 255, thickness=cv2.FILLED)
    # Close holes so lesions inside the silhouette remain in-leaf
    filled = cv2.morphologyEx(filled, cv2.MORPH_CLOSE, kernel, iterations=3)
    return filled


def _spot_mask(bgr: np.ndarray, leaf: np.ndarray) -> np.ndarray:
    """Brown / yellow / dark lesions inside the leaf silhouette."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    brown = cv2.inRange(hsv, (0, 40, 40), (25, 255, 220))
    yellow = cv2.inRange(hsv, (20, 60, 60), (40, 255, 255))
    dark = cv2.inRange(hsv, (0, 0, 0), (180, 255, 55))
    spots = cv2.bitwise_or(brown, yellow)
    spots = cv2.bitwise_or(spots, dark)
    spots = cv2.bitwise_and(spots, leaf)
    # Remove near-green healthy tissue false positives
    healthy = cv2.inRange(hsv, (35, 50, 50), (85, 255, 255))
    spots = cv2.bitwise_and(spots, cv2.bitwise_not(healthy))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    spots = cv2.morphologyEx(spots, cv2.MORPH_OPEN, kernel, iterations=1)
    return spots


def _severity(frac: float, count: int) -> str:
    if count == 0 or frac < 0.005:
        return "none"
    if frac < 0.03 and count <= 5:
        return "low"
    if frac < 0.10:
        return "moderate"
    return "high"


def inspect_leaf_spot(
    bgr: np.ndarray,
    roi: tuple[int, int, int, int] | None = None,
) -> LeafSpotResult:
    if roi is not None:
        x, y, rw, rh = roi
        x, y = max(0, x), max(0, y)
        crop = bgr[y : y + rh, x : x + rw]
    else:
        crop = bgr

    if crop.size == 0:
        return LeafSpotResult(
            leaf_found=False,
            spot_count=0,
            spot_area_frac=0.0,
            severity_band="unknown",
            claims=["Empty frame — retake of the leaf needed."],
            next_action="request_capture",
        )

    leaf = _leaf_mask(crop)
    leaf_area = float(np.count_nonzero(leaf))
    if leaf_area < 0.05 * crop.shape[0] * crop.shape[1]:
        return LeafSpotResult(
            leaf_found=False,
            spot_count=0,
            spot_area_frac=0.0,
            severity_band="unknown",
            claims=["No clear leaf region detected — move closer and fill the frame with the leaf."],
            next_action="request_capture",
            metrics={"leaf_area_frac": leaf_area / max(crop.size / 3, 1)},
        )

    spots = _spot_mask(crop, leaf)
    spot_px = float(np.count_nonzero(spots))
    frac = float(spot_px / max(leaf_area, 1.0))
    contours, _ = cv2.findContours(spots, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_spot = max(8.0, 0.0005 * leaf_area)
    count = sum(1 for c in contours if cv2.contourArea(c) >= min_spot)
    band = _severity(frac, count)

    claims = [
        f"Discolored spot count={count}, covering ~{frac * 100:.1f}% of detected leaf area "
        f"(severity band: {band}).",
        "Visual spot summary only — consult a local plant guide or extension service; "
        "LookAgain does not name diseases or prescribe treatment.",
    ]
    return LeafSpotResult(
        leaf_found=True,
        spot_count=count,
        spot_area_frac=frac,
        severity_band=band,
        claims=claims,
        next_action="finalize_report",
        metrics={
            "spot_count": float(count),
            "spot_area_frac": frac,
            "leaf_area_px": leaf_area,
        },
    )
