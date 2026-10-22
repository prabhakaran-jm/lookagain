"""COOL vs stock latency micro-bench (triage stage).

Usage on COOL AMI:
  source /opt/cool/venvs/python_3.12/bin/activate
  python scripts/eval_benchmark.py --benchmark-loop 50

Prints Markdown table: median + p95 ms. Warm-up runs excluded.
"""

from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

import cv2
import numpy as np


def triage_laplacian(img: np.ndarray) -> float:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def triage_pipeline(img: np.ndarray) -> dict[str, float]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    resized = cv2.resize(gray, (640, 480), interpolation=cv2.INTER_AREA)
    blur = cv2.GaussianBlur(resized, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    return {"sharpness": sharp, "edge_pixels": float(np.count_nonzero(edges))}


def timed_loop(fn, loops: int, warmup: int = 5) -> list[float]:
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    for _ in range(loops):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-loop", type=int, default=50)
    parser.add_argument("--threads", type=int, default=2)
    args = parser.parse_args()

    cv2.setNumThreads(args.threads)
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8)

    bi = cv2.getBuildInformation()
    samples = timed_loop(lambda: triage_pipeline(img), args.benchmark_loop)
    med = statistics.median(samples)
    p95 = sorted(samples)[max(0, int(0.95 * (len(samples) - 1)))]

    print("## LookAgain triage micro-bench")
    print()
    print(f"- OpenCV: `{cv2.__version__}`")
    print(f"- File: `{cv2.__file__}`")
    print(f"- KleidiCV in build info: `{'kleidi' in bi.lower()}`")
    print(f"- Threads: `{args.threads}` (cv2.setNumThreads)")
    print(f"- Loops: `{args.benchmark_loop}` (+5 warmup)")
    print()
    print("| Stage | median_ms | p95_ms |")
    print("|-------|-----------|--------|")
    print(f"| triage_pipeline | {med:.3f} | {p95:.3f} |")
    print()
    print("_Run once under COOL venv and once under stock venv on the same instance._")

    out = Path("deploy/bench_last.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"# triage_pipeline\nmedian_ms={med:.3f}\np95_ms={p95:.3f}\n"
        f"cv2={cv2.__version__}\nkleidicv={'kleidi' in bi.lower()}\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
