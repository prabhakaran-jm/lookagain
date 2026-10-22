"""Generate a silent demo preview MP4 for soft-reminder (local OpenCV 5)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.vision.compare_shots import compare_shots


def main() -> int:
    out_dir = Path("docs")
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "demo_preview.mp4"
    width, height = 1280, 720
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(out), fourcc, 2.0, (width, height))

    def slide(title: str, lines: list[str], color=(20, 24, 32)) -> None:
        img = np.full((height, width, 3), color, np.uint8)
        cv2.putText(
            img, title, (60, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (230, 235, 240), 2, cv2.LINE_AA
        )
        y = 180
        for line in lines:
            cv2.putText(
                img, line, (60, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (180, 190, 200), 2, cv2.LINE_AA
            )
            y += 50
        for _ in range(6):
            vw.write(img)

    rng = np.random.default_rng(7)
    base = rng.integers(40, 220, (480, 640), dtype=np.uint8)
    for _ in range(40):
        cv2.circle(
            base,
            (int(rng.integers(30, 610)), int(rng.integers(30, 450))),
            int(rng.integers(6, 18)),
            int(rng.integers(0, 255)),
            -1,
        )
    shot1 = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    x, y, rw, rh = 160, 120, 240, 180
    crop = shot1[y : y + rh, x : x + rw]
    shot2 = cv2.resize(crop, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    result = compare_shots(shot1, shot2, (x, y, rw, rh), "move_closer", True)

    slide(
        "LookAgain",
        [
            "OpenCV AI Competition 2026",
            "Agentic visual troubleshooting",
            "COOL instance terminated 2026-10-22",
            "Cancel Marketplace subscription to finish cost goal",
        ],
    )
    slide(
        "Agent loop",
        [
            "1 triage_frame",
            "2 remediate_frame OR request_capture(reason)",
            "3 compare_shots (SIFT + USAC_MAGSAC) gates inspect",
            "4 finalize_report (bounded claims) OR escalate_human",
        ],
    )

    canvas = np.full((height, width, 3), 16, np.uint8)
    s1 = cv2.resize(shot1, (560, 420))
    s2 = cv2.resize(shot2, (560, 420))
    canvas[140:560, 40:600] = s1
    canvas[140:560, 680:1240] = s2
    cv2.putText(canvas, "shot1", (40, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
    cv2.putText(canvas, "shot2 zoom", (680, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
    msg = (
        f"compare: pass={result.passed} scale={result.scale:.2f} "
        f"inliers={result.inlier_count} overlap={result.overlap:.2f}"
    )
    cv2.putText(canvas, msg, (40, 680), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 220, 140), 2)
    for _ in range(10):
        vw.write(canvas)

    slide(
        "COOL bench (honest)",
        [
            "COOL 4.14.0-pre median 6.225 ms",
            "stock Arm 4.13.0 median 5.668 ms",
            "Both report KleidiCV — parity, no inflated claim",
            "See deploy/bench_summary.md",
        ],
    )
    slide(
        "Next",
        [
            "User: cancel COOL in Marketplace subscriptions",
            "Then reply: canceled",
            "Full face+live video: deploy/DEMO_VIDEO_SHOTLIST.md",
        ],
    )
    vw.release()
    print("wrote", out, "bytes", out.stat().st_size)
    print("compare", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
