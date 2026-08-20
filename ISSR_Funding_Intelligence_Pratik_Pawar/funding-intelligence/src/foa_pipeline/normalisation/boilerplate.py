"""
Removal of administrative boilerplate from FOA text before semantic tagging.

An FOA is two kinds of text glued together: what the program actually funds,
and the agency's standard administrative template (submission rules, deadline
tables, eligibility legalese, policy cross-references). The tagger previously
scanned both as one blob, so calendar text and submission instructions were
matched against research concepts.

Measured examples of what that produced on the evaluation set:

    "Deadline date First Wednesday in November, Annually Thereafter 2027..."
        -> tagged "Partnerships for the Goals" (cosine 0.35)
    "please refer to PAPPG Chapter II.E.9. *Who May Submit Proposals..."
        -> tagged "International Affairs" (cosine 0.34)

Both are noise with no research content. The embedding scores tell the story:
they sit barely above the category thresholds, because text with no semantic
content lands in the mushy zone where any vague concept matches as well as any
other.

Patterns are grouped so each group's contribution can be measured
independently, and so a reviewer can see exactly what is being discarded.
Groups are conservative by design: it is better to leave some boilerplate in
than to strip real programme description and lose true positives.

Measured impact on the 20-FOA gold set (baseline F1 0.500), each group applied
alone:

    markup        +0.007
    deadlines     +0.002
    eligibility   -0.005
    procedural    -0.005
    all together  +0.000

Only ``markup`` is enabled in the tagging pipeline (see DEFAULT_GROUPS). The
text-level groups are kept because the negative result is worth preserving —
they are correct about what is boilerplate, they just don't improve tagging,
and the reason is structural rather than a flaw in the patterns:

TaggerPipeline emits up to N tags per category regardless of how much noise is
removed. Deleting the text that triggered a false positive doesn't reduce the
tag count, it just promotes the next candidate into the freed slot — which is
frequently also wrong. Across the whole eval set, stripping every group moved
false positives only 75 -> 69 while costing two true positives.

So input cleaning cannot fix over-tagging on its own; the emission controls
have to change too. Anyone revisiting these patterns should re-measure them
against whatever capping strategy is in place at the time, not against this
baseline.
"""

import logging
import re
from typing import Dict, Iterable, List, Optional, Pattern, Tuple

logger = logging.getLogger(__name__)

# If stripping would remove more than this fraction of the text, the result is
# discarded and the original returned. Tagging an over-stripped record silently
# costs recall, which is harder to notice than leaving boilerplate in.
MAX_STRIP_RATIO = 0.85

# Below this length the remaining text is too short to tag meaningfully, so the
# original is kept instead.
MIN_RESULT_CHARS = 120


def _c(pattern: str) -> Pattern:
    return re.compile(pattern, re.IGNORECASE | re.DOTALL)


# (group, description, pattern). Order matters only in that markup is removed
# first, so later text patterns match against clean prose.
BOILERPLATE_PATTERNS: List[Tuple[str, str, Pattern]] = [
    # ── markup ────────────────────────────────────────────────────────────
    # Descriptions are stored with raw HTML. Tag names and attribute values
    # ("disc", "circle", href URLs) are tokens the taggers would otherwise see.
    ("markup", "HTML tags", _c(r"<[^>]{0,400}?>")),
    ("markup", "HTML entities", _c(r"&(?:nbsp|amp|lt|gt|quot|#\d{1,5});")),

    # ── eligibility ───────────────────────────────────────────────────────
    # The NSF "Who May Submit" block appears in 46 of 131 FOAs and is pure
    # submission legalese. It also causes a conceptual error: eligibility says
    # who may *apply*, while the population category is about who the research
    # serves (Documentation/ONTOLOGY.md 2.3). Tagging populations from it is wrong by
    # definition, not merely noisy.
    ("eligibility", "Who May Submit header", _c(r"\*?\s*Who May Submit Proposals\s*:")),
    ("eligibility", "Submitter enumeration lead-in",
     _c(r"Proposals may only be submitted by(?: the following)?\s*:?")),
    ("eligibility", "IHE / non-profit / museum enumerations", _c(
        r"-?\s*(?:Institutions of Higher Education \(IHEs\)|"
        r"Non-profit,?\s*non-academic organizations|"
        r"Two-\s*and four-year IHEs[^.]{0,200}\.|"
        r"Independent museums, observatories, research laboratories[^.]{0,200}\.|"
        r"Special Instructions for International Branch Campuses[^:]{0,80}:)"
    )),
    ("eligibility", "Accreditation / association clause",
     _c(r"that are directly associated with educational or research activities\.")),

    # ── deadlines ─────────────────────────────────────────────────────────
    # Date tables flattened into prose. Matched as a run so the whole table
    # goes, rather than leaving orphaned fragments behind.
    ("deadlines", "Due-date table run", _c(
        r"(?:Upcoming due dates?|Full proposal(?: window| deadline)?)?[^.]{0,80}?"
        r"(?:\d{4}\s+\w+\s+\d{1,2}\s+\d{4}\s*-?\s*)?Deadline date"
        r"(?:[^.]{0,120}?(?:Annually Thereafter|\d{4}))+"
    )),
    ("deadlines", "Submission cutoff time",
     _c(r"Due by\s*\d{1,2}\s*[ap]\.?m\.?[^.]{0,60}local time\.?")),
    ("deadlines", "Local-time clause",
     _c(r"\d{1,2}\s*[ap]\.?m\.?\s*submitting organization'?s local time\.?")),

    # ── procedural ────────────────────────────────────────────────────────
    ("procedural", "PAPPG cross-reference",
     _c(r"(?:please\s+)?refer to (?:the\s+)?PAPPG[^.]{0,80}\.")),
    ("procedural", "PAPPG chapter citation",
     _c(r"PAPPG\s+Chapter\s+[IVXLC]+\.?[A-Z]?\.?\d*\.?\d*")),
    ("procedural", "Cognizant program officer block",
     _c(r"Cognizant Program Officer\(?s?\)?[^.]{0,200}\.")),
    ("procedural", "Proposal preparation pointer",
     _c(r"For (?:conference|travel|EAGER|RAPID) proposals[^.]{0,120}\.")),
]

ALL_GROUPS: Tuple[str, ...] = ("markup", "eligibility", "deadlines", "procedural")

# What the tagging pipeline actually applies. Only markup earned its place on
# the gold set; see the module docstring for the per-group measurements.
DEFAULT_GROUPS: Tuple[str, ...] = ("markup",)


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s{2,}", " ", text).strip()


def strip_boilerplate(
    text: Optional[str],
    groups: Optional[Iterable[str]] = None,
) -> str:
    """
    Remove administrative boilerplate from FOA text.

    `groups` selects which pattern families to apply. Defaults to
    DEFAULT_GROUPS — the ones measured to help — rather than every pattern
    defined here. Pass an explicit list (or ALL_GROUPS) to audit or re-measure
    the others.

    Falls back to the original text if stripping removed implausibly much — see
    MAX_STRIP_RATIO and MIN_RESULT_CHARS.
    """
    if not text:
        return ""

    enabled = set(groups) if groups is not None else set(DEFAULT_GROUPS)
    original = text
    result = text

    for group, _description, pattern in BOILERPLATE_PATTERNS:
        if group in enabled:
            result = pattern.sub(" ", result)

    result = _collapse_whitespace(result)

    if not result:
        return _collapse_whitespace(original)

    removed_ratio = 1.0 - (len(result) / max(len(original), 1))
    if removed_ratio > MAX_STRIP_RATIO or len(result) < MIN_RESULT_CHARS:
        # Only worth warning about when there was substantial text to begin
        # with; short records legitimately fall under the floor.
        if len(original) >= MIN_RESULT_CHARS:
            logger.warning(
                "Boilerplate stripping removed %.0f%% of a %d-char record; "
                "keeping the original to avoid losing recall.",
                removed_ratio * 100,
                len(original),
            )
        return _collapse_whitespace(original)

    return result


def boilerplate_stats(text: Optional[str]) -> Dict[str, int]:
    """
    Characters each group would remove, for auditing what a pattern is doing.

    Groups are measured independently against the original text, so overlapping
    matches are counted under each group that claims them and the totals may
    exceed the reduction achieved by applying all groups together.
    """
    if not text:
        return {group: 0 for group in ALL_GROUPS}

    stats: Dict[str, int] = {}
    for group in ALL_GROUPS:
        stripped = strip_boilerplate(text, groups=[group])
        stats[group] = max(len(text) - len(stripped), 0)
    return stats
