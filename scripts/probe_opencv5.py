"""Thursday probe: OpenCV 5 features available for compare_shots.

Run on Windows with pinned 5.0.0.93 AND on COOL AMI (/opt/cool/venvs).
ALIKED.create requires modelPath — locate weights or lock SIFT by Thu night.
"""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path


def main() -> int:
    import cv2

    report = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "cv2_version": cv2.__version__,
        "cv2_file": cv2.__file__,
        "has_aliked": hasattr(cv2, "ALIKED") or hasattr(cv2, "ALIKED_create"),
        "has_lightglue": hasattr(cv2, "LightGlueMatcher")
        or hasattr(cv2, "LightGlueMatcher_create"),
        "has_sift": hasattr(cv2, "SIFT_create"),
        "has_usac_magsac": hasattr(cv2, "USAC_MAGSAC"),
        "cool_path_exists": Path("/opt/cool").exists(),
    }

    bi = cv2.getBuildInformation()
    report["kleidicv_in_build_info"] = "kleidi" in bi.lower()
    report["dnn_in_modules"] = "dnn" in bi.lower()

    # Try to discover ALIKED default model hints from docs/strings if any
    aliked_ok = False
    aliked_error = None
    try:
        if hasattr(cv2, "ALIKED_create"):
            # Will fail without modelPath — capture the requirement
            cv2.ALIKED_create("")  # type: ignore[arg-type]
            aliked_ok = True
        elif hasattr(cv2, "ALIKED"):
            cv2.ALIKED.create(modelPath="")
            aliked_ok = True
    except Exception as exc:  # noqa: BLE001
        aliked_error = str(exc)
        aliked_ok = False

    report["aliked_create_empty_path"] = {"ok": aliked_ok, "error": aliked_error}
    print(json.dumps(report, indent=2))
    return 0 if report["has_sift"] or report["has_aliked"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
