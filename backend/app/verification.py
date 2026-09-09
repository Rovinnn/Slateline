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


# Payout mechanisms that only exist for statutory entitlements. You claim a
# refundable or transferable credit on a return because a statute says a
# qualifying production SHALL be allowed it; there is no body deciding whether
# you get one. A grant or rebate is the opposite — an agency awards it, and can
# decline.
_ENTITLEMENT_MECHANISMS = frozenset({"refundable", "transferable", "non_refundable"})


def _discretionary_is_credible(rule: JurisdictionRule) -> bool:
    """Whether `is_discretionary=True` survives cross-checking against the
    payout mechanism.

    `is_discretionary` short-circuits compute_benefit() entirely: setting it
    drops the jurisdiction from the ranking with "benefit is not modelable".
    That is a lot of weight for a bare boolean, and Layer 1 got it wrong on
    every live run of Louisiana — a statutory transferable credit reported as
    discretionary, so the jurisdiction the hand-verified seed set ranks FIRST
    refused to compute in production while the docs advertised it as the
    winner.

    Two attempts to fix this by describing the field to the model failed, and
    the second made Texas — a genuinely discretionary competitive grant —
    report as non-discretionary instead. Same lesson as the challenge pass's
    false contradictions: a model boolean is corrected in code, not by asking
    more nicely.

    The cross-check is the payout mechanism, which is extracted independently
    and is far more stable. It also survives the instability that remains:
    Louisiana alternates between "refundable" and "transferable" across runs,
    and both are entitlement mechanisms, so the guard fires either way.
    Texas is a "rebate" and is left alone.
    """
    return rule.credit_type not in _ENTITLEMENT_MECHANISMS


# Whether a program is an entitlement or a discretionary award is readable in
# the text the pipeline already retrieved, so Layer 3 reads it rather than
# taking the model's word. Layer 1 is not stable on the boolean: three
# consecutive live extractions of Texas returned True, False, False, and
# `credit_type` was identical in all three, so the mechanism alone cannot
# separate a by-right rebate from an agency-awarded grant.
#
# The distinction the sources actually draw is what the money IS. A tax credit
# is claimed against a liability because a statute allows it. A cash grant is
# awarded out of an appropriation by a body that can decline. Those are the
# words the statutes and film offices use, and they are what these markers
# match — the model quotes, code decides, which is the same division of labour
# the rest of the pipeline runs on.
_GRANT_MARKERS = (
    "cash grant",
    "grant program",
    "is a grant",
    "grant award",
    "at the discretion",
    "subject to the availability of funds",
    "subject to availability of funds",
)

_ENTITLEMENT_MARKERS = (
    "tax credit",
    "shall be allowed",
    "shall be granted",
    "is entitled to",
    "entitled to a credit",
    "may claim",
    "claimed against",
    "tax liability",
)


def _retrieved_text(rule: JurisdictionRule) -> str:
    """Everything Layer 1 actually quoted, lowercased for matching.

    Only the excerpts and the program's own name — never the jurisdiction
    name, which would make this a lookup table wearing a disguise.
    """
    parts = [rule.program_name or ""]
    parts.extend(s.excerpt or "" for s in rule.sources)
    return " ".join(parts).lower()


def classify_discretion(rule: JurisdictionRule) -> bool | None:
    """Read entitlement-vs-grant out of the retrieved sources.

    Returns True (discretionary), False (entitlement), or None when nothing
    decides it — in which case the caller leaves Layer 1's answer alone.

    The payout mechanism is checked FIRST and settles it on its own for a tax
    credit. Excerpt text is only consulted for rebates, because the excerpts
    are contaminated: a search for one state returns think-pieces comparing
    all of them, so "tax credit" routinely appears in sources for a
    jurisdiction that has no tax credit. That contamination shipped once —
    Texas, a cash-grant program, read as an entitlement off other states'
    credits mentioned in its own source set, and ranked first at $277,658.
    Mechanism is extracted about THIS program and does not have that problem.
    """
    if rule.credit_type in _ENTITLEMENT_MECHANISMS:
        # Claimed against a liability because a statute allows it. No body
        # decides who gets one.
        return False

    # A rebate or grant. Now the words the program uses about itself matter.
    text = _retrieved_text(rule)
    if any(m in text for m in _GRANT_MARKERS):
        return True
    if any(m in text for m in _ENTITLEMENT_MARKERS):
        return False
    return None


def verify_rule(rule: JurisdictionRule, *, today: date | None = None) -> JurisdictionRule:
    """Returns rule with `confidence` recomputed from its sources/conflicts,
    and `is_discretionary` decided from the retrieved text where it says.

    Never alters a figure — only verification-state fields.
    """
    verified = replace(rule, confidence=assess_confidence(rule, today=today))

    from_sources = classify_discretion(verified)
    if from_sources is not None:
        return replace(verified, is_discretionary=from_sources)

    # Sources are silent. Fall back to the payout mechanism, which at least
    # can't credit a statutory claim to somebody's discretion.
    if verified.is_discretionary and not _discretionary_is_credible(verified):
        verified = replace(verified, is_discretionary=False)
    return verified
