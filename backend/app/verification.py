"""Layer 3: rule-based verification. No model calls — cross-checks and labels
what Layer 1 already retrieved; never guesses a number.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from .models import Confidence, JurisdictionRule

STALE_AFTER_DAYS = 180


def assess_confidence(rule: JurisdictionRule, *, today: date | None = None) -> Confidence:
    today = today or date.today()
    if rule.conflicts:
        return "conflicting"
    if not rule.sources:
        return "unverified"
    if any((today - s.retrieved).days > STALE_AFTER_DAYS for s in rule.sources):
        return "stale"
    if any(s.is_primary for s in rule.sources):
        return "primary_source"
    return "official_secondary"


def verify_rule(rule: JurisdictionRule, *, today: date | None = None) -> JurisdictionRule:
    """Returns rule with `confidence` recomputed from its sources/conflicts.
    Never alters a figure — only the verification-state field.
    """
    return replace(rule, confidence=assess_confidence(rule, today=today))
