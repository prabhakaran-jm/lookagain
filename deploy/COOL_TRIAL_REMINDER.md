# COOL Marketplace trial stop plan

**Subscribed:** 2026-10-22  
**Trial length:** 7 days  
**Auto-converts to paid:** ~**2026-10-29** (confirm exact end date in Marketplace → Manage subscriptions)

> **DO NOT cancel Marketplace before ~2026-10-29.** Keep the subscription for the free trial week. EC2 was terminated early to stop compute burn; relaunch from AMI when you need COOL again. Cancel only on the hard-stop morning.

## Live instance (launched 2026-10-22)

- **Instance ID:** `i-0f6e85df280826133`
- **Public IP:** `98.92.163.130` (changes after stop/start — check `deploy/cool_instance.txt`)
- **Terminated:** 2026-10-22 (`terminated`) — EC2 half of goal done. To run COOL again before cancel: launch new `c8g.large` from AMI `ami-01db31139bc5615d8` (subscription still active until you cancel).
- **Windows reminders registered:** soft 2026-10-28 09:00 · hard 2026-10-29 08:00
- **AMI:** `ami-01db31139bc5615d8` (`COOL-Graviton4-v2-AMI-prod-k6u24vxijyzvg`)
- **Type:** `c8g.large` · **Region:** `us-east-1`
- **SSH:** `ssh -i ~/.ssh/lookagain-cool.pem ubuntu@98.92.163.130`
- **Tag:** `StopBy=2026-10-29`
- **Profile:** `AWS_PROFILE=lookagain`

```powershell
$env:AWS_PROFILE='lookagain'
.\deploy\stop_cool.ps1            # stop (preferred)
.\deploy\stop_cool.ps1 -Terminate # destroy
# then: Marketplace → Manage subscriptions → cancel COOL
```


## What to stop before paid conversion

1. **Stop or terminate** the LookAgain `c8g.large` COOL instance (Marketplace software fee accrues only while running).  
   - Idle-stopped already on 2026-10-22; on 2026-10-29 run `.\deploy\stop_cool.ps1` again (no-op if stopped) or `-Terminate`.
2. **Cancel** the COOL Marketplace subscription (required — stopping EC2 alone does **not** cancel the sub):  
   https://console.aws.amazon.com/marketplace/home#/subscriptions  
3. Optionally leave a **stock OpenCV** demo on `t4g` (credits cover EC2) for judges through **9 Nov**.
4. Import `deploy/lookagain-cool-reminders.ics` into Outlook/Google Calendar if you want a second reminder channel.
5. Video checklist: `deploy/DEMO_VIDEO_SHOTLIST.md` (do this on **28 Oct** before cancel).

## Probe result (2026-10-22 on this AMI)

- OpenCV reports **`4.14.0-pre`** (build `4.13.0-…`) with **KleidiCV 0.7.0** — **not OpenCV 5**
- **ALIKED / LightGlue: absent** → per plan, **lock SIFT + USAC_MAGSAC on COOL** for `compare_shots`
- Local Windows pin remains OpenCV **5.0.0.93** (has ALIKED); report must state dual-build honestly
- Public `/health`: `http://98.92.163.130:8000/health` (COOL cv2 path verified)
- Bench: see `deploy/bench_summary.md` — stock Arm also has KleidiCV (**parity**, do not inflate)

## Must finish on COOL during the free week

- KleidiCV + COOL `/health` version proof (done path exists)  
- `compare_shots` via **SIFT** on COOL  
- `eval.py --benchmark-loop 50` table (COOL vs stock)  
- Demo video showing COOL path  

## Reminder dates

| When | Action |
|------|--------|
| **2026-10-28** (day 6) | Soft reminder: finish benches/video; plan stop |
| **2026-10-29 morning** | Hard stop: stop/terminate instance; cancel Marketplace if done |
| **2026-11-09** | Judging ends — terminate any leftover demo boxes |
