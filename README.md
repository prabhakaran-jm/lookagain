# LookAgain

Agentic visual troubleshooting for the [OpenCV AI Competition 2026](https://opencv26.devpost.com/).

Phone capture → OpenCV 5 triage / remediate / reason-aware `compare_shots` → inspect → bounded finalize or HITL.

## Local (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt   # pins opencv-python==5.0.0.93
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 — use the file input (`capture="environment"` works on phones over HTTP).

Health: http://127.0.0.1:8000/health

Replay mode (when wired): append `?mode=replay` — a **REPLAY** banner must stay visible. Never present recorded traces as live.

## AWS / COOL

See [deploy/aws_thursday.md](deploy/aws_thursday.md). Target: COOL Graviton4 AMI on `c8g.large`, keep through **9 Nov**.

## Packs

Only `appliance_leds`, `bike_brake_pad`, `leaf_spot` may finalize. Any other pack ID → `escalate_human`.
