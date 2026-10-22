#!/bin/bash
set -e
cd ~/lookagain
python3 -m venv .venv
source .venv/bin/activate
pip install -q -r requirements-cool.txt
# stock opencv for baseline on same box
pip install -q "opencv-python-headless==4.13.0.90" || pip install -q opencv-python-headless
python - <<'PY'
import cv2, statistics, time, numpy as np
cv2.setNumThreads(2)
img = np.random.default_rng(0).integers(0,255,(720,1280,3), dtype=np.uint8)
def triage(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cv2.Laplacian(g, cv2.CV_64F).var()
    r = cv2.resize(g,(640,480))
    b = cv2.GaussianBlur(r,(5,5),0)
    cv2.Canny(b,50,150)
for _ in range(5): triage(img)
samples=[]
for _ in range(50):
    t0=time.perf_counter(); triage(img); samples.append((time.perf_counter()-t0)*1000)
med=statistics.median(samples); p95=sorted(samples)[int(0.95*(len(samples)-1))]
bi=cv2.getBuildInformation()
open('deploy/bench_stock.md','w').write(f"""## LookAgain triage micro-bench (stock)

- OpenCV: `{cv2.__version__}`
- File: `{cv2.__file__}`
- KleidiCV in build info: `{'kleidi' in bi.lower()}`
- Threads: `2`
- Loops: `50` (+5 warmup)

| Stage | median_ms | p95_ms |
|-------|-----------|--------|
| triage_pipeline | {med:.3f} | {p95:.3f} |
""")
print(open('deploy/bench_stock.md').read())
PY
export PYTHONPATH=/opt/cool/python_3.12/site-packages
pkill -f 'uvicorn app.main' || true
nohup env PYTHONPATH=/opt/cool/python_3.12/site-packages /home/ubuntu/lookagain/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/lookagain.log 2>&1 &
sleep 3
curl -s http://127.0.0.1:8000/health
echo