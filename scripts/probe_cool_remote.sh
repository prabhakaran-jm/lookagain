#!/usr/bin/env bash
set -euo pipefail
if [[ -f /opt/cool/venvs/python_3.12/bin/activate ]]; then
  # shellcheck disable=SC1091
  source /opt/cool/venvs/python_3.12/bin/activate
elif ls /opt/cool/venvs/*/bin/activate >/dev/null 2>&1; then
  # shellcheck disable=SC1090
  source "$(ls -1 /opt/cool/venvs/*/bin/activate | head -1)"
fi
python3 <<'PY'
import cv2, json, os, platform
bi = cv2.getBuildInformation()
print(json.dumps({
  "platform": platform.platform(),
  "machine": platform.machine(),
  "cv2_version": cv2.__version__,
  "cv2_file": cv2.__file__,
  "cool_path": os.path.exists("/opt/cool"),
  "has_aliked": hasattr(cv2, "ALIKED") or hasattr(cv2, "ALIKED_create"),
  "has_lightglue": hasattr(cv2, "LightGlueMatcher"),
  "has_sift": hasattr(cv2, "SIFT_create"),
  "has_usac_magsac": hasattr(cv2, "USAC_MAGSAC"),
  "kleidicv_in_build_info": "kleidi" in bi.lower(),
  "build_excerpt": "\n".join(
    l for l in bi.splitlines()
    if any(k in l.lower() for k in ("version control", "kleidi", "to be built", "cpu/hw", "dnn"))
  )[:1500],
}, indent=2))
PY
