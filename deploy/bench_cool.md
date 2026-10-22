## LookAgain triage micro-bench

- OpenCV: `4.14.0-pre`
- File: `/opt/cool/python_3.12/site-packages/cv2/python-3.12/cv2.cpython-312-aarch64-linux-gnu.so`
- KleidiCV in build info: `True`
- Threads: `2` (cv2.setNumThreads)
- Loops: `50` (+5 warmup)

| Stage | median_ms | p95_ms |
|-------|-----------|--------|
| triage_pipeline | 6.225 | 6.296 |

_Run once under COOL venv and once under stock venv on the same instance._
