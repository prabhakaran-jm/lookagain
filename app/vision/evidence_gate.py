"""Evidence-gate: block forbidden finalize claims before they leave the agent.

Pack allowlist already gates which scenarios may finalize; this validator
strips / rejects absolute safety and disease-name language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Absolute / liability language — never emit in finalize_report.
FORBIDDEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("safe_to_ride", re.compile(r"\bsafe\s+to\s+ride\b", re.I)),
    ("safe_to_use", re.compile(r"\bsafe\s+to\s+(?:use|operate)\b", re.I)),
    ("disease_name", re.compile(
        r"\b(?:powdery\s+mildew|downy\s+mildew|anthracnose|leaf\s+blight|"
        r"bacterial\s+spot|early\s+blight|late\s+blight|rust\s+fungus|"
        r"phytophthora|fusarium)\b",
        re.I,
    )),
    ("medical_diagnosis", re.compile(
        r"\b(?:diagnos(?:e|is|ed)|you\s+have|confirmed\s+disease)\b", re.I
    )),
    ("guaranteed_fix", re.compile(
        r"\b(?:guaranteed|definitely\s+fixed|100%\s+safe)\b", re.I
    )),
]

# Soft replacements when we can salvage a claim.
REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsafe\s+to\s+ride\b", re.I), "pad wear indicator visible — verify with a mechanic"),
    (re.compile(r"\bsafe\s+to\s+(?:use|operate)\b", re.I), "visual pattern matches pack guide — confirm on-device"),
]


@dataclass
class GateResult:
    allowed: bool
    claims: list[str]
    blocked: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "claims": self.claims,
            "blocked": self.blocked,
            "reasons": self.reasons,
        }


def validate_claims(claims: list[str], *, sanitize: bool = True) -> GateResult:
    """Return allowed claims; drop or sanitize forbidden ones.

    If any claim remains forbidden after sanitize, allowed=False and finalize
    must escalate_human instead of emitting the report.
    """
    kept: list[str] = []
    blocked: list[str] = []
    reasons: list[str] = []

    for raw in claims:
        text = raw.strip()
        if not text:
            continue
        hit_ids = [cid for cid, pat in FORBIDDEN_PATTERNS if pat.search(text)]
        if not hit_ids:
            kept.append(text)
            continue

        if sanitize:
            sanitized = text
            for pat, repl in REPLACEMENTS:
                sanitized = pat.sub(repl, sanitized)
            still = [cid for cid, pat in FORBIDDEN_PATTERNS if pat.search(sanitized)]
            if not still:
                kept.append(sanitized)
                reasons.append(f"sanitized:{','.join(hit_ids)}")
                continue

        blocked.append(text)
        reasons.extend(hit_ids)

    # Must keep at least one claim to finalize; empty → not allowed
    allowed = len(blocked) == 0 and len(kept) > 0
    return GateResult(allowed=allowed, claims=kept, blocked=blocked, reasons=reasons)
