"""appliance_leds — detect colored status LEDs and emit bounded claims."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import cv2
import numpy as np

# HSV ranges (OpenCV H: 0–179) for common appliance indicator colors.
LED_RANGES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "red": ((0, 80, 80), (10, 255, 255)),
    "red2": ((170, 80, 80), (179, 255, 255)),
    "amber": ((12, 80, 80), (28, 255, 255)),
    "green": ((40, 60, 60), (90, 255, 255)),
    "blue": ((95, 60, 60), (130, 255, 255)),
}


@dataclass
class LedBlob:
    color: str
    cx: int
    cy: int
    area: float
    bbox: tuple[int, int, int, int]


@dataclass
class LedInspectResult:
    led_count: int
    leds: list[LedBlob]
    color_counts: dict[str, int]
    claims: list[str]
    next_action: str = "finalize_report"
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "led_count": self.led_count,
            "leds": [asdict(x) for x in self.leds],
            "color_counts": self.color_counts,
            "claims": self.claims,
            "next_action": self.next_action,
            "metrics": self.metrics,
        }


def _mask_color(hsv: np.ndarray, lo: tuple[int, int, int], hi: tuple[int, int, int]) -> np.ndarray:
    return cv2.inRange(hsv, np.array(lo), np.array(hi))


def inspect_appliance_leds(
    bgr: np.ndarray,
    roi: tuple[int, int, int, int] | None = None,
) -> LedInspectResult:
    """Find bright colored blobs consistent with panel LEDs."""
    h, w = bgr.shape[:2]
    if roi is not None:
        x, y, rw, rh = roi
        x, y = max(0, x), max(0, y)
        crop = bgr[y : y + rh, x : x + rw]
        offset = (x, y)
    else:
        crop = bgr
        offset = (0, 0)

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    blobs: list[LedBlob] = []
    min_area = max(12.0, 0.0002 * crop.shape[0] * crop.shape[1])

    color_masks: dict[str, np.ndarray] = {}
    red = _mask_color(hsv, *LED_RANGES["red"])
    red2 = _mask_color(hsv, *LED_RANGES["red2"])
    color_masks["red"] = cv2.bitwise_or(red, red2)
    for name in ("amber", "green", "blue"):
        color_masks[name] = _mask_color(hsv, *LED_RANGES[name])

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    for color, mask in color_masks.items():
        clean = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = float(cv2.contourArea(c))
            if area < min_area:
                continue
            bx, by, bw, bh = cv2.boundingRect(c)
            # Prefer compact blobs (LED-like) over long strips
            aspect = max(bw, bh) / max(min(bw, bh), 1)
            if aspect > 3.5:
                continue
            m = cv2.moments(c)
            if m["m00"] <= 1e-6:
                continue
            cx = int(m["m10"] / m["m00"]) + offset[0]
            cy = int(m["m01"] / m["m00"]) + offset[1]
            blobs.append(
                LedBlob(
                    color=color,
                    cx=cx,
                    cy=cy,
                    area=area,
                    bbox=(bx + offset[0], by + offset[1], bw, bh),
                )
            )

    counts: dict[str, int] = {}
    for b in blobs:
        counts[b.color] = counts.get(b.color, 0) + 1

    claims: list[str] = []
    if not blobs:
        claims.append(
            "No distinct colored LED blobs detected in view — retake closer to the indicator panel."
        )
        next_action = "request_capture"
    else:
        parts = [f"{n} {c}" for c, n in sorted(counts.items())]
        claims.append(
            "Detected " + ", ".join(parts) + " indicator blob(s) matching pack color bands."
        )
        claims.append(
            "Compare observed pattern to the appliance status legend; LookAgain does not assert device health."
        )
        next_action = "finalize_report"

    return LedInspectResult(
        led_count=len(blobs),
        leds=blobs,
        color_counts=counts,
        claims=claims,
        next_action=next_action,
        metrics={
            "frame_w": float(w),
            "frame_h": float(h),
            "led_count": float(len(blobs)),
        },
    )
