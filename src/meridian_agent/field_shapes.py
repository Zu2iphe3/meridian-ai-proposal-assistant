"""Narrow text-field exclusions, not general semantic or financial validation."""

import re

from meridian_agent.source_evidence import source_quote

_NUMBER = r"(?:\d[\d,.]*(?:\s*(?:million|billion|thousand|[kmb]))?|(?:\w+[ -]){0,8}(?:hundred|thousand|million|billion))"
_MONEY = re.compile(
    rf"(?<!\w)(?:(?:USD|ZAR|GBP|EUR|R|[$£€])\s*\d[\d,.]*"
    rf"(?:\s*(?:million|billion|thousand|[kmb]))?|{_NUMBER}\s+(?:rand|dollars|pounds|euros))\b",
    re.IGNORECASE,
)
_HEDGE = re.compile(
    r"\b(?:maybe|perhaps|possibly|might|tentative|provisional|unconfirmed|undecided)\b"
    r"|\b[\w]+-ish\b|\b(?:still )?to be confirmed\b|\bno (?:portfolio )?decision\b",
    re.IGNORECASE,
)
_RETURN = re.compile(r"^(?:target return\s*:?\s*)?CPI\s*(?:\+|plus\b)", re.IGNORECASE)
_ROLE_LABEL = re.compile(
    r"^\s*(?:target return|return target|advis[eo]r(?:y)? (?:fee|charge))\b", re.IGNORECASE
)
_RATE_ONLY = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|percent|per cent)", re.IGNORECASE)


def text_field_context(notes: str, quote: str, value: str) -> str:
    """Include an adjacent hedge when the model supplies a shortened quote."""
    located = source_quote(notes, quote)
    if located is None or notes.count(located) != 1:
        return quote
    text = source_quote(located, value)
    if text is None:
        return quote
    position = notes.index(located) + located.index(text)
    end = position + len(text)
    left = max((notes.rfind(mark, 0, position) + 1 for mark in ".!?;\n"), default=0)
    right = min((p for mark in ".!?;\n" if (p := notes.find(mark, end)) >= 0), default=len(notes))
    return notes[left:right]


def text_field_issue(field: str, value: str, quote: str, notes: str) -> str | None:
    if field == "client_name" and _MONEY.search(value):
        return "money_expression_as_client_name"
    if field == "portfolio_preference":
        # Percentages with asset descriptions are allowed; a fee elsewhere in
        # the evidence is not a veto on an otherwise valid allocation.
        if _MONEY.fullmatch(value.strip()) or _RETURN.match(value.strip()):
            return "financial_expression_as_portfolio"
        if _ROLE_LABEL.match(value.strip()) or (
            _RATE_ONLY.fullmatch(value.strip()) and _ROLE_LABEL.match(quote.strip())
        ):
            return "financial_expression_as_portfolio"
    if field in {"portfolio_preference", "risk", "horizon"} and _HEDGE.search(
        text_field_context(notes, quote, value)
    ):
        return "provisional_requires_pm_confirmation"
    return None
