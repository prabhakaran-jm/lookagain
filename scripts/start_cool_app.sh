#!/bin/bash
set -e
fuser -k 8000/tcp 2>/dev/null || true
sleep 1
cd /home/ubuntu/lookagain
export PYTHONPATH="/home/ubuntu/lookagain/.venv/lib/python3.12/site-packages"
source /opt/cool/venvs/python_3.12/bin/activate
python - <<'PY'
import cv2, fastapi
print("cv2", cv2.__version__, cv2.__file__)
print("fastapi", fastapi.__version__)
PY
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/lookagain.log 2>&1 &
sleep 3
curl -s http://127.0.0.1:8000/health
echo