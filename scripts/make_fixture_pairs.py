"""Generate demo fixture pairs: glare→clean and far→closer (SIFT-friendly).

Writes under docs/fixtures/ and app/static/fixtures/ (UI can fetch /static/fixtures/...).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import cv2
import numpy as np

from app.vision.compare_shots import compare_shots
from app.vision.remediate import remediate_frame
from app.vision.triage import triage_frame


ROOT = Path(__file__).resolve().parents[1]
OUT_DIRS = [ROOT / "docs" / "fixtures", ROOT / "app" / "static" / "fixtures"]


def _base_scene(seed: int = 11, h: int = 480, w: int = 640) -> np.ndarray:
    """Textured panel with two LEDs — dense blobs for SIFT + triage pass."""
    rng = np.random.default_rng(seed)
    # Mid-grey base so exposure triage passes
    gray = rng.integers(70, 160, (h, w), dtype=np.uint8)
    for _ in range(120):
        cv2.circle(
            gray,
            (int(rng.integers(15, w - 15)), int(rng.integers(15, h - 15))),
            int(rng.integers(5, 18)),
            int(rng.integers(30, 230)),
            -1,
        )
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    # Large appliance panel (keeps ROI area fraction above triage minimum)
    cv2.rectangle(bgr, (80, 80), (560, 400), (90, 95, 105), -1)
    for _ in range(40):
        cv2.circle(
            bgr,
            (int(rng.integers(100, 540)), int(rng.integers(100, 380))),
            int(rng.integers(4, 12)),
            (int(rng.integers(40, 200)),) * 3,
            -1,
        )
    cv2.rectangle(bgr, (80, 80), (560, 400), (50, 50, 55), 3)
    # Green + red status LEDs
    cv2.circle(bgr, (240, 240), 18, (35, 210, 45), -1)
    cv2.circle(bgr, (400, 240), 18, (35, 40, 220), -1)
    return bgr


def _add_glare(bgr: np.ndarray) -> np.ndarray:
    """Glare that still fails triage after remediate (inpaint alone is not enough)."""
    out = bgr.copy()
    # Specular wash over most of the panel
    out[100:380, 120:520] = (255, 255, 255)
    # Residual motion blur — software recovery should not fully clear the frame
    out = cv2.GaussianBlur(out, (25, 25), 0)
    return out


def _far_scene(seed: int = 21) -> tuple[np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    """shot1 = distant panel (gray LED placeholders → inspect move_closer); shot2 = close color LEDs."""
    panel = _base_scene(seed=seed)
    closer = panel
    # Far: same geometry/texture, but LEDs are dull gray (no HSV color hit)
    far_panel = panel.copy()
    cv2.circle(far_panel, (240, 240), 18, (75, 75, 75), -1)
    cv2.circle(far_panel, (400, 240), 18, (75, 75, 75), -1)
    h, w = 480, 640
    scale = 0.55
    small = cv2.resize(far_panel, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    far = np.full((h, w, 3), 40, dtype=np.uint8)
    rng = np.random.default_rng(seed + 3)
    for _ in range(60):
        cv2.circle(
            far,
            (int(rng.integers(10, w - 10)), int(rng.integers(10, h - 10))),
            int(rng.integers(4, 12)),
            (int(rng.integers(50, 120)),) * 3,
            -1,
        )
    x = (w - sw) // 2
    y = (h - sh) // 2
    far[y : y + sh, x : x + sw] = small
    roi = (x, y, sw, sh)
    return far, closer, roi


def write_pair(name: str, shot1: np.ndarray, shot2: np.ndarray) -> None:
    for d in OUT_DIRS:
        d.mkdir(parents=True, exist_ok=True)
        pair = d / name
        pair.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(pair / "shot1.jpg"), shot1)
        cv2.imwrite(str(pair / "shot2.jpg"), shot2)
        (pair / "README.txt").write_text(
            f"Pair: {name}\nshot1 = first capture\nshot2 = guided retake\n",
            encoding="utf-8",
        )


def main() -> int:
    scene = _base_scene()
    glare = _add_glare(scene)
    clean = scene.copy()

    t_glare = triage_frame(glare)
    t_clean = triage_frame(clean)
    rem = remediate_frame(glare, t_glare)
    print("triage glare:", t_glare.passed, t_glare.retake_reason, t_glare.fail_reasons)
    print("remediate still fails:", not rem.passed_after, rem.retake_reason, rem.steps_applied)
    print("triage clean:", t_clean.passed, t_clean.retake_reason)
    if rem.passed_after:
        print("WARNING: glare fixture recovers via remediate — agent may skip request_capture")

    reason = t_glare.retake_reason or "less_glare"
    if reason not in {"move_closer", "hold_steadier", "less_glare", "blur"}:
        reason = "less_glare"
    roi = t_glare.roi or (80, 80, 480, 320)
    cmp_glare = compare_shots(
        glare, clean, roi, reason, triage_shot2_passed=t_clean.passed  # type: ignore[arg-type]
    )
    print(
        f"compare {reason}:",
        cmp_glare.passed,
        f"scale={cmp_glare.scale:.3f}",
        f"inliers={cmp_glare.inlier_count}",
        cmp_glare.fail_reason,
    )

    write_pair("leds_glare_retake", glare, clean)
    # Record expected reason for demos / tests
    for d in OUT_DIRS:
        (d / "leds_glare_retake" / "expected_reason.txt").write_text(reason + "\n", encoding="utf-8")

    far, closer, far_roi = _far_scene()
    t_far = triage_frame(far)
    t_close = triage_frame(closer)
    from app.vision.packs.appliance_leds import inspect_appliance_leds

    ins_far = inspect_appliance_leds(far, t_far.roi)
    ins_close = inspect_appliance_leds(closer, t_close.roi)
    print("far inspect:", ins_far.led_count, ins_far.next_action)
    print("close inspect:", ins_close.led_count, ins_close.next_action, ins_close.color_counts)
    cmp_zoom = compare_shots(far, closer, far_roi, "move_closer", triage_shot2_passed=t_close.passed)
    print(
        "compare move_closer:",
        cmp_zoom.passed,
        f"scale={cmp_zoom.scale:.3f}",
        f"inliers={cmp_zoom.inlier_count}",
        cmp_zoom.fail_reason,
    )
    write_pair("leds_closer_retake", far, closer)
    for d in OUT_DIRS:
        (d / "leds_closer_retake" / "expected_reason.txt").write_text("move_closer\n", encoding="utf-8")

    # Convenience copies at fixtures root (single-file picker)
    for d in OUT_DIRS:
        shutil.copy(d / "leds_glare_retake" / "shot1.jpg", d / "leds_glare.jpg")
        shutil.copy(d / "leds_glare_retake" / "shot2.jpg", d / "leds_clean.jpg")
        blur = cv2.GaussianBlur(scene, (31, 31), 0)
        cv2.imwrite(str(d / "leds_blur.jpg"), blur)

    manifest = ROOT / "docs" / "fixtures" / "MANIFEST.md"
    manifest.write_text(
        """# Demo fixture pairs (no props needed)

## `leds_glare_retake/` — glare → retake → pass
1. Upload **shot1.jpg** (washed panel) → expect `request_capture` / `less_glare` (after remediate).
2. Upload **shot2.jpg** (same pose, clean) → `compare_shots` then `inspect_pack` → `finalize_report`.

## `leds_closer_retake/` — move closer
1. **shot1.jpg** full panel frame.
2. **shot2.jpg** ~1.55× crop of the LED ROI → compare scale ≥ 1.3.

Also: `leds_glare.jpg`, `leds_clean.jpg`, `leds_blur.jpg` at this folder root.

Regenerate: `python scripts/make_fixture_pairs.py`
""",
        encoding="utf-8",
    )
    print("wrote", OUT_DIRS)
    if not cmp_glare.passed:
        print("WARNING: less_glare compare did not pass — adjust texture/glare")
        return 1
    if not cmp_zoom.passed:
        print("WARNING: move_closer compare did not pass")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
