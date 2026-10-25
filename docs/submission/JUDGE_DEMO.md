# Judge demo — screen-share (primary) + optional redeploy

**Primary delivery for judges:** arranged live screen-share of a local (or private) `uvicorn` session.  
**Optional:** short-lived public URL on COOL/Graviton if AWS Marketplace access is still available.

## A. Screen-share demo (recommended)

### Setup

```bash
git clone <this-repo> && cd lookagain
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
source .venv/bin/activate
pip install -r requirements.txt
export LOOKAGAIN_AGENT=heuristic   # reliable without Bedrock
# Optional Bedrock:
# export LOOKAGAIN_AGENT=auto
# export AWS_PROFILE=lookagain
# export BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000  

Health: http://127.0.0.1:8000/health — confirm `opencv.version`, `agent.mode`, `approved_packs`.

### Demo script (~5 minutes live)

1. Show pack selector (`appliance_leds`).
2. Click **Glare → clean retake** demo pair — expect step1 `request_capture`, step2 `finalize_report` (`demo_ok`).
3. Expand / show JSON: triage metrics → remediate → `compare_shots` → claims ([AGENTIC_TRACE.md](AGENTIC_TRACE.md)).
4. Click **Closer crop** demo pair — inspect `led_count=0` → `move_closer` → scale ≥ 1.3 → finalize.
5. Optional: upload a phone photo via file input (`capture="environment"`).
6. Mention evidence gate: no “safe to ride” / disease names; unknown packs escalate.

### API-only smoke

```bash
curl -s http://127.0.0.1:8000/health | jq .
curl -s -F pair_id=leds_glare_retake -F pack_id=appliance_leds \
  http://127.0.0.1:8000/api/demo/run_pair | jq '{demo_ok, step1: .step1.next_action, step2: .step2.next_action}'
```

Expected: `demo_ok=true`, step1 `request_capture`, step2 `finalize_report`.

### Replay mode

UI `?mode=replay` shows a **REPLAY** banner. Never present recorded traces as live capture.

---

## B. Optional public endpoint (COOL / Graviton)

Only if you still have COOL Marketplace / AMI access during judging.

1. Launch Graviton (e.g. `c8g.large`) from the COOL AMI used in benches.
2. Clone repo; install [`requirements-cool.txt`](../../requirements-cool.txt) **inside** `/opt/cool/venvs/python_3.12` (do not pip-install `opencv-python`).
3. Start with [`scripts/start_cool_app.sh`](../../scripts/start_cool_app.sh) (binds `0.0.0.0:8000`).
4. Open security group for judge IPs or use SSH tunnel / SSM port forward.
5. Verify: `curl http://<host>:8000/health` shows COOL `cv2` path / version.
6. Tear down after the session — Marketplace cancel per your trial rules.

Probes: [`scripts/probe_cool_remote.sh`](../../scripts/probe_cool_remote.sh), [`scripts/probe_opencv5.py`](../../scripts/probe_opencv5.py).

---

## C. Video (team-owned)

Judges need a ≤5 minute public/unlisted video. Suggested beats (you record/edit):

| Time | Beat |
|------|------|
| 0:00 | Team face + one-line problem |
| 0:30 | Live UI: glare demo pair + tool trace |
| 2:00 | Architecture slide from [ARCHITECTURE.md](ARCHITECTURE.md) |
| 3:00 | Results: agentic loop + COOL near-parity bench |
| 4:00 | Limits + responsible use (gate / HITL / pack allowlist) |
| ≤5:00 | End |

Link the video on Devpost; keep this repo free of large `.mp4` binaries (gitignored).
