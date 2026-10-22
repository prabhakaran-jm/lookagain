"""Evidence-gate must block absolute safety / disease claims."""

from __future__ import annotations

from app.vision.evidence_gate import validate_claims


def test_allows_bounded_led_claims():
    gate = validate_claims(
        [
            "Detected 2 green indicator blob(s) matching pack color bands.",
            "Compare observed pattern to the appliance status legend; LookAgain does not assert device health.",
        ]
    )
    assert gate.allowed
    assert len(gate.claims) == 2
    assert gate.blocked == []


def test_blocks_safe_to_ride():
    gate = validate_claims(["Brake pads look safe to ride."], sanitize=True)
    # Sanitized to mechanic verification language
    assert gate.allowed
    assert "safe to ride" not in gate.claims[0].lower()
    assert any("sanitized" in r for r in gate.reasons)


def test_blocks_disease_name_without_salvage():
    gate = validate_claims(["This is powdery mildew on the leaf."], sanitize=True)
    assert not gate.allowed
    assert gate.blocked
    assert "disease_name" in gate.reasons


def test_empty_claims_not_allowed():
    gate = validate_claims([])
    assert not gate.allowed
