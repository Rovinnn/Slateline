"""Derives JurisdictionRule.constraint_gaps — BUILD_BRIEF.md section 7:
"Constraint toggle chips; enabling one greys out failing jurisdictions with
a hover reason." Applied uniformly to seed and live-searched jurisdictions
alike (see main.py), unlike the rest of a rule, this is never extracted by
Layer 1: "does this state touch the ocean" or "is there a stage over
20,000 sq ft here" isn't stated on a tax-incentive source page the way
base_rate is, so it can't be sourced/quoted the same way. It's reference
data, kept here once.

coastline is fully enumerable — a state either touches an ocean/the Gulf or
it doesn't — so every non-coastal state is confidently marked as a gap.
spring_only is derived live from the rule's own sunset_date/pool_status, so
it works for any jurisdiction, seed or searched, with no lookup table at
all. large_soundstage is deliberately NOT evaluated here: absence of
evidence isn't evidence of absence, and unlike coastline there is no
complete, confident list of which states lack one — several jurisdictions
have built large stages specifically chasing incentive business, so
guessing would risk greying out a real, usable jurisdiction on no real
evidence. It needs an actual facilities data source before it can grey
anything out; until then it's simply never in the returned dict, same
"leave it null rather than guess" policy extraction/agent.py follows for
sourced figures.
"""

from __future__ import annotations

from datetime import date

from .models import JurisdictionRule

# Ocean/Gulf coastline only — the constraint's label (frontend/src/data/
# constraints.ts) says "ocean coastline", so Great-Lakes-only states
# (Michigan, Illinois, Ohio, Wisconsin, Minnesota, ...) don't count.
COASTAL_STATES: frozenset[str] = frozenset(
    {
        "Maine",
        "New Hampshire",
        "Massachusetts",
        "Rhode Island",
        "Connecticut",
        "New York",
        "New Jersey",
        "Delaware",
        "Maryland",
        "Virginia",
        "North Carolina",
        "South Carolina",
        "Georgia",
        "Florida",
        "Alabama",
        "Mississippi",
        "Louisiana",
        "Texas",
        "California",
        "Oregon",
        "Washington",
        "Alaska",
        "Hawaii",
    }
)

# "Cast available spring 2027 only" is really asking whether the program
# will still be funded that far out — tied to this one hardcoded window
# because the constraint's own label is.
_SPRING_2027_START = date(2027, 3, 1)


def constraint_gaps_for(rule: JurisdictionRule) -> dict[str, str]:
    """Constraint keys this rule fails, each with a hover-ready reason. An
    absent key means "satisfies it" or "unknown" — never a guess.
    """
    gaps: dict[str, str] = {}

    if rule.jurisdiction not in COASTAL_STATES:
        gaps["coastline"] = f"{rule.jurisdiction} has no ocean or Gulf coastline."

    if rule.sunset_date is not None and rule.sunset_date < _SPRING_2027_START:
        gaps["spring_only"] = f"{rule.program_name} sunsets {rule.sunset_date.isoformat()}, before spring 2027."
    elif rule.pool_status == "closed":
        gaps["spring_only"] = f"{rule.program_name}'s funding pool is currently closed."

    return gaps
