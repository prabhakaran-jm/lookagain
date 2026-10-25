# Best Use of COOL — evidence (modest claims)

**Claim we make:** LookAgain’s core triage workload **ran on AWS Graviton under COOL**. We **do not** claim a large latency win versus a stock Arm OpenCV wheel on the same instance.

**Claim we do not make:** “COOL is X× faster than stock.” Same-day benches showed near parity (stock slightly faster on this micro-bench).

## Deployment configuration (2026-10-22)

| Item | Value |
|------|--------|
| Instance | `c8g.large` (Graviton / Arm64) |
| Workload path | COOL AMI Python 3.12 venv at `/opt/cool/venvs/python_3.12` |
| OpenCV (COOL) | `4.14.0-pre` from `/opt/cool/.../cv2...aarch64-linux-gnu.so` |
| KleidiCV | Mentioned in COOL build info (`True`) |
| Matcher in product | **SIFT + USAC_MAGSAC** (ALIKED unavailable on that AMI — locked in code comments) |
| App deps on COOL | [`requirements-cool.txt`](../../requirements-cool.txt) — **do not** `pip install opencv-python` on the COOL path |
| Start script | [`scripts/start_cool_app.sh`](../../scripts/start_cool_app.sh) |

Local / Devpost pin for OpenCV 5 development: `opencv-python==5.0.0.93` in [`requirements.txt`](../../requirements.txt). COOL AMI build was the Graviton cloud path under evaluation; document both.

## Reproducible micro-bench

Script: [`scripts/eval_benchmark.py`](../../scripts/eval_benchmark.py)

```bash
# On COOL AMI
source /opt/cool/venvs/python_3.12/bin/activate
cd /path/to/lookagain
python scripts/eval_benchmark.py --benchmark-loop 50 --threads 2

# Same instance, stock Arm venv (baseline)
source .venv/bin/activate
python scripts/eval_benchmark.py --benchmark-loop 50 --threads 2
```

**Input:** synthetic 720×1280 RGB noise (`numpy` RNG seed 0).  
**Stage:** `triage_pipeline` — Laplacian sharpness + resize + GaussianBlur + Canny (representative of triage cost).  
**Threads:** `cv2.setNumThreads(2)`. Warm-up 5, then 50 timed loops → median and p95.

## Results (same `c8g.large`, 2026-10-22)

Source tables: [`deploy/bench_cool.md`](../../deploy/bench_cool.md), [`deploy/bench_stock.md`](../../deploy/bench_stock.md), [`deploy/bench_summary.md`](../../deploy/bench_summary.md).

| Env | OpenCV | KleidiCV | median_ms | p95_ms |
|-----|--------|----------|-----------|--------|
| COOL `/opt/cool` | 4.14.0-pre | yes | **6.225** | 6.296 |
| stock Arm venv | 4.13.0 | yes | **5.668** | 5.749 |

### Interpretation for judges

1. **Verified COOL on Graviton:** core image ops executed via COOL’s Arm OpenCV build.
2. **Honest baseline:** stock OpenCV 4.13 Arm wheel also reported KleidiCV; latency was near parity (stock slightly lower on this micro-bench).
3. **Product value of COOL path:** deployable Graviton AMI + Marketplace-aligned stack for the competition cloud story — not an inflated speedup narrative.
4. **Core app workload** beyond the micro-bench also includes SIFT/USAC `compare_shots` and pack HSV morphology; those run on the same `cv2` binding when the app is started under COOL.

## Instance lifecycle note

The trial Graviton instance used for benches was later **terminated** (ops audit). For judging, prefer the [screen-share demo](JUDGE_DEMO.md). Optional redeploy steps are listed there if Marketplace/AMI access remains active during the judging window.
