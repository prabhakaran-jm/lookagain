# LookAgain — Technical Report

**OpenCV AI Competition 2026 (AWS)**  
**Paths:** Agentic Vision; Best Use of COOL (verified Graviton deployment, modest performance claims)  
**Repo package:** [docs/submission/](README.md)

## 1. Problem

Phone photos of small physical indicators (appliance LEDs, bike brake pads, leaf spots) are often unusable: glare, blur, wrong distance, or ambiguous framing. Users then guess, over-trust a single model caption, or get unsafe absolute advice (“safe to ride”, a disease name).

LookAgain treats capture as an **active perception** loop: measure quality with OpenCV 5, remediate when possible, request a guided retake when not, verify the retake geometrically, then emit **bounded** observations—or escalate to a human.

## 2. Users and impact

| User | Need | LookAgain behavior |
|------|------|--------------------|
| Home / DIY | Read panel LEDs without a manual in hand | Color-band LED blobs + “check legend” disclaimer |
| Cyclist / mechanic-assist | Pad wear **indicator** visibility | Wear-band language only — never “safe to ride” |
| Grower / garden | Spot severity on a leaf | Severity bands — never disease diagnosis |
| Judges / operators | Auditable agent decisions | Full tool `trace` + correlation IDs |

Real-world impact is safer **visual troubleshooting**: better evidence before action, and explicit HITL when evidence is weak.

## 3. Architecture summary

Phone/browser UI → FastAPI → session → **agent** (Bedrock Converse or heuristic) → **OpenCV 5 tools** → pack inspectors → evidence gate.

Diagrams: [ARCHITECTURE.md](ARCHITECTURE.md).  
Optional Arm path: same app under COOL on Graviton ([COOL_EVIDENCE.md](COOL_EVIDENCE.md)).

### OpenCV 5 implementation (substantive vision)

| Stage | Module | Techniques |
|-------|--------|------------|
| Triage | `app/vision/triage.py` | Laplacian / Tenengrad sharpness, HSV glare mask, exposure fractions, edge-based ROI |
| Remediate | `app/vision/remediate.py` | CLAHE (Lab), glare inpaint, bilateral, unsharp; re-triage |
| Compare | `app/vision/compare_shots.py` | SIFT + USAC_MAGSAC; reason-aware scale/overlap gates |
| Packs | `app/vision/packs/*` | HSV LED blobs; dark pad mask + thickness; leaf silhouette + lesion mask |
| Gate | `app/vision/evidence_gate.py` | Regex blocklist / sanitize for liability and diagnosis language |

### AWS

- **Amazon Bedrock** Runtime Converse with toolConfig ([`app/agent/bedrock_loop.py`](../../app/agent/bedrock_loop.py)). Default model env: `BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0`.
- Agent modes: `LOOKAGAIN_AGENT=auto|bedrock|heuristic` — `auto` falls back to heuristic on auth failures.
- **COOL on Graviton** (optional featured path): run uvicorn with COOL-provided `cv2` ([`requirements-cool.txt`](../../requirements-cool.txt)).

A chatbot that only explains a fixed vision result would **not** qualify; here vision JSON selects the next tool ([AGENTIC_TRACE.md](AGENTIC_TRACE.md)).

## 4. Agent tools

`triage_frame` → `remediate_frame` → `compare_shots` → `inspect_pack` → `request_capture` | `finalize_report` | `escalate_human`

Terminal tools end the upload step. Max three guided retakes. Only allowlisted packs may finalize.

## 5. Evaluation

### Automated tests

`pytest` under [`tests/`](../../tests/): triage/remediate, compare_shots, evidence gate, three packs, fixture pairs (`demo_ok`), Bedrock loop with scripted client.

### No-prop demo pairs (judge-friendly)

| Pair | Story | Observed (heuristic, OpenCV 5.0.0) |
|------|-------|-------------------------------------|
| `leds_glare_retake` | Bad quality → remediate → retake → compare → LEDs | `demo_ok=true`; compare scale ≈ 1.0, 17 inliers |
| `leds_closer_retake` | No LEDs → move_closer → scale gate → LEDs | `demo_ok=true`; compare scale ≈ 1.82, 114 inliers |

Endpoint: `POST /api/demo/run_pair`. Details: [AGENTIC_TRACE.md](AGENTIC_TRACE.md).

### COOL vs stock latency

On `c8g.large` (2026-10-22), triage micro-bench median ≈ **6.2 ms** (COOL) vs **5.7 ms** (stock Arm). Near parity; see [COOL_EVIDENCE.md](COOL_EVIDENCE.md).

## 6. Limitations

- Three packs only; other `pack_id` values escalate by design.
- Synthetic / fixture demos are not a substitute for diverse field photos; ROI and LED HSV ranges can miss uncommon panels.
- `compare_shots` depends on texture for SIFT; featureless glare washes can fail homography → another retake or HITL.
- ALIKED was unavailable on the evaluated COOL AMI; matcher is locked to SIFT+USAC_MAGSAC.
- Sessions are in-memory (single process); not a multi-tenant production store.
- Bedrock adds latency/cost and can mis-order tools; heuristic is the reproducible fallback. Evidence gate is last-line defense on claims text.
- Phone `capture="environment"` needs HTTPS or LAN HTTP depending on browser policy.

## 7. Responsible use

- **No absolute safety or medical/disease claims** in finalize output (evidence gate + pack claim templates).
- **Human escalation** when retakes are exhausted, packs are unknown, the gate blocks, or the model ends without a tool.
- **Correlation IDs** on responses for support/audit (`X-Correlation-ID`).
- **Replay banner** when `?mode=replay` so recorded demos are not presented as live.
- Upload size capped (8 MB) in the API.
- Competition cloud instances should be stopped/terminated after use; Marketplace trial cancel per AWS/OpenCV rules.

## 8. Build and run

See root [README.md](../../README.md) and [JUDGE_DEMO.md](JUDGE_DEMO.md).

```bash
pip install -r requirements.txt
export LOOKAGAIN_AGENT=heuristic
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 9. Submission pointers

| Requirement | Where |
|-------------|--------|
| Technical report | This file |
| Architecture diagram | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Agentic workflow + trace | [AGENTIC_TRACE.md](AGENTIC_TRACE.md) |
| COOL version / baseline | [COOL_EVIDENCE.md](COOL_EVIDENCE.md) |
| Live demo | Screen-share primary — [JUDGE_DEMO.md](JUDGE_DEMO.md) |
| Video (≤5 min) | Team-owned; suggested beats in JUDGE_DEMO |
| Code + pinned deps | Repository root |
