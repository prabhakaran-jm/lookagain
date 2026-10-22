# LookAgain

Agentic visual troubleshooting for the [OpenCV AI Competition 2026](https://opencv26.devpost.com/).

Phone capture → OpenCV 5 triage / remediate / reason-aware `compare_shots` → inspect → bounded finalize or HITL.

## Local (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt   # pins opencv-python==5.0.0.93
$env:AWS_PROFILE='lookagain'     # Bedrock tool-use (optional)
$env:LOOKAGAIN_AGENT='auto'      # auto | bedrock | heuristic
$env:BEDROCK_MODEL_ID='us.anthropic.claude-haiku-4-5-20251001-v1:0'
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```


Open http://127.0.0.1:8000 — use the file input (`capture="environment"` works on phones over HTTP).

Health: http://127.0.0.1:8000/health — includes `agent.mode` and tool list.

**Agentic loop:** Bedrock Converse picks the next tool from OpenCV tool results (`triage_frame` → `remediate_frame` / `request_capture` → `compare_shots` → `inspect_pack` → `finalize_report`). `LOOKAGAIN_AGENT=heuristic` forces the local policy (no LLM). `auto` falls back to heuristic if Bedrock is unavailable.

Replay mode: append `?mode=replay` — a **REPLAY** banner must stay visible. Never present recorded traces as live.

## AWS / COOL

See [deploy/aws_thursday.md](deploy/aws_thursday.md). Target: COOL Graviton4 AMI on `c8g.large`, keep through **9 Nov**.

## Packs

Only `appliance_leds`, `bike_brake_pad`, `leaf_spot` may finalize. Any other pack ID → `escalate_human`.
