"""Check the role of the name already proposed by the extraction model."""

import re
from dataclasses import dataclass

from meridian_agent.source_evidence import admissible_anchor, admissible_clauses, source_quote

_OTHER_ROLE = r"(?:advis[eo]r|financial planner|trustee|beneficiary|accountant|analyst)"
_OTHER_BEFORE = re.compile(
    rf"\b(?:{_OTHER_ROLE}[\s:,-]*(?:(?:is|was)\s+)?"
    r"|not\s+(?:the\s+)?client\s*:\s*|client\s+(?:is|was)\s+not\s+)$",
    re.IGNORECASE,
)
_OTHER_AFTER = re.compile(
    rf"^\s*(?:\(\s*{_OTHER_ROLE}\s*\)|"
    rf"(?:(?:is|was|acts|acting|serves|signed)\s+(?:as\s+)?(?:the |an? )?{_OTHER_ROLE}\b)"
    r"|\b(?:is|was)\s+not\s+(?:the\s+)?client\b)",
    re.IGNORECASE,
)
_CLIENT_LABEL = re.compile(
    r"\b(?:client(?: name)?\s*(?::|is\b|was\b)|(?:proposal|draft)\s+(?:(?:is|was)\s+)?for\b)"
    r"""[\s:"'“‘]*""",
    re.IGNORECASE,
)
_ALTERNATIVE_IDENTITY = re.compile(r"^\s*,?\s+or\b", re.IGNORECASE)
_GENERIC_ACTOR = re.compile(
    r"(?:the\s+)?(?:client|customer|investor|trustees?|family trust)", re.IGNORECASE
)


@dataclass(frozen=True)
class NameEvidence:
    value: str
    passage: str
    explicit_client: bool = False
    issue: str | None = None


def client_name_evidence(
    notes: str, proposed_name: str, *, grounded_quote: str | None = None
) -> NameEvidence | None:
    clauses = list(admissible_clauses(notes, identity=True))
    span = admissible_anchor(
        notes, grounded_quote or proposed_name, clauses, unique=grounded_quote is None
    )
    if span is None:
        return None
    excerpt = notes[span[0] : span[1]]
    value = source_quote(excerpt, proposed_name)
    if value is None:
        return None
    start = span[0] + excerpt.index(value)
    end = start + len(value)
    for offset, passage in clauses:
        if offset <= start and end <= offset + len(passage):
            before, after = passage[: start - offset], passage[end - offset :]
            if _OTHER_BEFORE.search(before) or _OTHER_AFTER.match(after):
                return NameEvidence(value, passage, issue="client_name_explicit_nonclient")
            # Explicit labels for a different identity veto auto-recovery. This
            # checks role markers without trying to extract a second name.
            labels = [
                left + match.end()
                for left, clause in clauses
                for match in _CLIENT_LABEL.finditer(clause)
            ]
            labelled = start in labels
            if not labelled and _GENERIC_ACTOR.fullmatch(value):
                return NameEvidence(value, passage, issue="client_name_not_identified")
            if labelled and _ALTERNATIVE_IDENTITY.match(after):
                return NameEvidence(value, passage, issue="provisional_requires_pm_confirmation")
            return NameEvidence(value, passage, explicit_client=labelled and len(labels) == 1)
    return None
