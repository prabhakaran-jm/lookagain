# Thursday AWS checklist (LookAgain)

## Blocker on this machine (2026-10-22)

Active credentials are `arn:aws:iam::905418051670:user/relayguard-deploy` — **no EC2 / Bedrock / S3**.
SSO profiles (`archon`, `aics`, `incidentpilot`, `stepclear`) are **expired**.

### Unblock (do this first)

1. Refresh SSO for an admin/builder profile, e.g.:
   ```powershell
   aws sso login --profile archon
   # or whichever profile has EC2 + Bedrock + Marketplace
   ```
2. Confirm:
   ```powershell
   aws sts get-caller-identity --profile archon
   aws ec2 describe-regions --profile archon --region us-east-1 --query "length(Regions)"
   aws bedrock list-foundation-models --profile archon --region us-east-1 --query "length(modelSummaries)"
   ```
3. Re-run `deploy/launch_cool.ps1` with that profile.

## COOL subscribe

Marketplace product: [Cloud Optimized OpenCV For AWS Graviton4](https://aws.amazon.com/marketplace/pp/prodview-fdvbfiewzuehs)

- Free trial: 7 days, then converts to paid — **budget through 9 Nov judging**
- Instance families: **c8g, m8g, r8g** only
- Target: **c8g.large**, region prefer **us-east-1** (or where Bedrock Claude is enabled)

Subscribe via Console “Continue to Subscribe” / Try for free, then launch from Marketplace.

## After launch

```bash
ssh -i <key.pem> ubuntu@<public-ip>
source /opt/cool/venvs/python_3.12/bin/activate
python3 -c "import cv2; print(cv2.__version__, cv2.__file__); print(cv2.getBuildInformation())"
# Look for KleidiCV / NEON lines; note has_aliked / DNN
```

Deploy app:

```bash
sudo apt-get update && sudo apt-get install -y git
# scp or git clone lookagain
cd lookagain
source /opt/cool/venvs/python_3.12/bin/activate
pip install -r requirements-cool.txt   # fastapi stack only; cv2 from COOL
uvicorn app.main:app --host 0.0.0.0 --port 8000
curl http://127.0.0.1:8000/health
```

Open security group: TCP **8000** (or 80 behind nginx) from your IP / judges as needed.

## Bedrock

In the same region as the instance (or configured cross-region):

- Enable model access for Claude (tool-use capable)
- Prefer **instance role** with `bedrock:InvokeModel` — no access keys on disk

## Security baseline (cloud delivery points)

- Instance role (no long-lived keys)
- Private S3 bucket for frames/traces
- IMDSv2 required on the instance
- Correlation ID already emitted by the app (`X-Correlation-ID`)
