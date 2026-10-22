# COOL vs stock triage bench (same c8g.large, 2026-10-22)

Honest result: stock OpenCV 4.13 Arm wheel also reports KleidiCV ???????? near parity.

| Env | OpenCV | KleidiCV | median_ms | p95_ms |
|-----|--------|----------|-----------|--------|
| COOL `/opt/cool` | 4.14.0-pre | yes | 6.225 | 6.296 |
| stock venv | 4.13.0 | yes | 5.668 | 5.749 |

Story for report: verified COOL-supported Graviton build; no inflated speedup claim.
