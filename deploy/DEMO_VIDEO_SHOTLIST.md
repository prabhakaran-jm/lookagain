# Demo video shot list (≤5 min) — finish by 2026-10-28 soft reminder

Record after `.\deploy\start_cool.ps1` and `bash /tmp/start_cool_app.sh` on the instance.

1. **Face + name** (10s): you, LookAgain, OpenCV AI Competition 2026  
2. **Architecture** (30s): diagram — phone capture → triage/remediate → compare_shots (SIFT) → finalize/HITL; AWS COOL on c8g.large  
3. **Live loop** (2–3 min):  
   - Bad/glared photo → remediate or request retake (show reason)  
   - Retake → `compare_shots` metrics (scale/overlap/inliers) gate inspect  
   - Finalize with **bounded claims** (no “safe to ride” / disease name)  
4. **/health COOL proof** (20s): browser on `/health` showing COOL path + KleidiCV  
5. **Bench honesty** (20s): show `deploy/bench_summary.md` parity table  
6. **Close** (10s): GitHub/repo + “stop COOL by 29 Oct”

Save as `docs/demo.mp4` (or unlisted YouTube) before Marketplace cancel.
