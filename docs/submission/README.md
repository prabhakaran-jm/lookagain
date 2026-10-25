# LookAgain — Devpost submission package

OpenCV AI Competition 2026 ([Devpost](https://opencv26.devpost.com/)).  
Paths: **Agentic Vision** and **Best Use of COOL** (modest claims).

| Document | Purpose |
|----------|---------|
| [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) | Problem, users, architecture, OpenCV 5, AWS, evaluation, limits, responsible use |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System + agent diagrams (OpenCV 5, Bedrock, optional COOL) |
| [AGENTIC_TRACE.md](AGENTIC_TRACE.md) | Workflow diagram + captured traces where vision changes the next tool |
| [COOL_EVIDENCE.md](COOL_EVIDENCE.md) | COOL version, Graviton config, reproducible baseline (near-parity) |
| [JUDGE_DEMO.md](JUDGE_DEMO.md) | Screen-share primary demo; optional public redeploy checklist |

## Devpost checklist

- [ ] Technical report linked
- [ ] Judge-accessible repo (this project)
- [ ] Pinned deps: `requirements.txt` / `requirements-cool.txt`
- [ ] Architecture diagram(s)
- [ ] Working demo: screen-share (primary) and/or optional public URL
- [ ] ≤5 min video (team-owned — see suggested beats in JUDGE_DEMO)
- [ ] Agentic extras: workflow + trace
- [ ] COOL extras: version, instance, baseline (if claiming that award)
- [ ] Evaluation / failure cases noted in the report

## Reproduce agentic demos locally

```bash
python -m venv .venv && source .venv/bin/activate   # or Windows Activate.ps1
pip install -r requirements.txt
export LOOKAGAIN_AGENT=heuristic
uvicorn app.main:app --host 127.0.0.1 --port 8000
# UI: open / and click demo-pair buttons
# or: curl -F pair_id=leds_glare_retake -F pack_id=appliance_leds http://127.0.0.1:8000/api/demo/run_pair
```
