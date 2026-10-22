"""Synthetic LED blob detection for appliance_leds pack."""

from __future__ import annotations

import cv2
import numpy as np

from app.vision.packs.appliance_leds import inspect_appliance_leds


def test_detects_green_and_red_leds():
    img = np.full((240, 320, 3), 30, dtype=np.uint8)
    # BGR: green and red bright disks
    cv2.circle(img, (80, 120), 12, (40, 220, 40), -1)
    cv2.circle(img, (200, 120), 12, (40, 40, 220), -1)
    result = inspect_appliance_leds(img)
    assert result.led_count >= 2, result
    assert result.color_counts.get("green", 0) >= 1
    assert result.color_counts.get("red", 0) >= 1
    assert result.next_action == "finalize_report"
    assert result.claims


def test_no_leds_requests_closer_shot():
    img = np.full((240, 320, 3), 40, dtype=np.uint8)
    result = inspect_appliance_leds(img)
    assert result.led_count == 0
    assert result.next_action == "request_capture"
