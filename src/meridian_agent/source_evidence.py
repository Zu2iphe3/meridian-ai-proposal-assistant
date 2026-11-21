"""Locate exact source excerpts and check simple field attribution."""

import re
from typing import Literal

_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
_EQUIVALENTS = {" ": r"\s+", '"': '["“”]', "'": "['‘’]"}
_CLAUSE_END = re.compile(r"[.!?](?=\s|$)|;|\n\s*\n")
_FINANCIAL_CUES = {
    "investment_amount": r"\b(?:lump sum|invest(?:ment|ing)?|put in|investment capital)\b",
    "monthly_income": r"\b(?:income|drawdown|draw down|per month|a month|monthly)\b",
    "adviser_fee": r"\b(?:advis[eo]r(?:y)? fee|advice fee)\b",
    "target_return": r"\b(?:target return|CPI|return target)\b",
}
_META_INSTRUCTIONS = re.compile(
    r"\b(?:ignore|override|disregard)\b.{0,50}\b(?:rules|policy|instructions|system prompt)\b",
    re.IGNORECASE,
)
_NO_INCOME = (
    r"\b(?:no (?:monthly )?(?:income|drawdown) (?:is )?(?:required|needed)"
    r"|(?:income|drawdown) (?:is )?not (?:needed|required)"
    r"|(?:does not|do not|won't|will not) (?:need|require) (?:any )?"
    r"(?:monthly )?(?:income|drawdown))\b"
)
_YES_INCOME = r"\b(?:needs? (?:a |monthly )?income|draw an income|(?:required?|wants?) (?:a |monthly )?income|income (?:is )?(?:needed|required))\b"
_AMBIGUOUS_CHOICE = re.compile(
    r"\b(?:if|unless|whether|might|may|possibly|unclear|unknown|unconfirmed|never said|did not say|didn't say|not confirmed)\b",
    re.IGNORECASE,
)
_NUMERIC_WORD = re.compile(
    r"\d|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
    r"forty|fifty|sixty|seventy|eighty|ninety|half)\b|\ba (?:hundred|thousand|million|billion)\b",
    re.IGNORECASE,
)
_VAGUE_NUMBER = re.compile(r"\b(?:few|some|several|unknown|unspecified)\b", re.IGNORECASE)
_APPROXIMATE = re.compile(
    r"\b(?:about|roughly|approximately|around|maybe|call it|circa)\s*$", re.IGNORECASE
)
_NO_REPLACEMENT = r"\b(?:no replacement|not (?:a replacement|replacing))\b"
_YES_REPLACEMENT = r"\b(?:replacement of|replaces?|replacing)\b"
_RECIPIENT = r"\b(?:send|address(?:ed)?|go(?:es)?|greet)\b[^.!?;]{0,70}\bto\b"


# Recognise source text only. Issue #5 owns parsing, units and financial equivalence.
_HEDGE = r"(?:(?:about|roughly|approximately|around|call\s+it|circa)\s+)?"
_DIGITS = r"\d+(?:[.,]\d+)*"
_SPOKEN_WORD = (
    r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    r"|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|and|a|half)"
)
_SPOKEN = rf"{_SPOKEN_WORD}(?:[\s-]+{_SPOKEN_WORD}){{0,7}}"
_SCALE = r"(?:billion|million|thousand)"
_CURRENCY_PREFIX = r"(?:USD|ZAR|GBP|EUR|R|[$£€])"
_MONEY_UNIT = r"(?:rand|dollars|pounds|euros)"
_PERCENT = r"(?:%|percent|per\s+cent)"
_MONTH = r"(?:a|per|each)\s+month|monthly"
_MONEY = (
    rf"{_CURRENCY_PREFIX}\s*{_DIGITS}(?:\s*(?:{_SCALE}|[kmb]))?"
    rf"|{_DIGITS}(?:\s+{_MONEY_UNIT}|\s*{_SCALE}(?:\s+{_MONEY_UNIT})?)"
    rf"|{_SPOKEN}\s+{_SCALE}(?:\s+{_MONEY_UNIT})?"
)
_RATE = (
    rf"{_DIGITS}\s*{_PERCENT}|{_SPOKEN}\s+{_PERCENT}"
    rf"|{_SPOKEN_WORD}\s+point(?:\s+{_SPOKEN_WORD}){{1,5}}"
)
_RETURN = rf"CPI\s*(?:\+|plus\s+)\s*(?:{_DIGITS}|{_SPOKEN})(?:\s*{_PERCENT})?|{_RATE}"
_QUOTED_EXPRESSIONS = {
    "investment_amount": rf"{_HEDGE}(?:{_MONEY})",
    "monthly_income": rf"{_HEDGE}(?:{_MONEY})(?:\s+(?:{_MONTH}))?",
    "adviser_fee": rf"{_HEDGE}(?:{_RATE})",
    "target_return": rf"{_HEDGE}(?:{_RETURN})",
}
_OTHER_FEE = re.compile(
    r"\b(?:management|platform|performance|admin(?:istration)?)\s+fee\b", re.IGNORECASE
)
_NON_MONTHLY = re.compile(
    r"\b(?:annually|annual|yearly|quarterly|per\s+year|a\s+year)\b", re.IGNORECASE
)


def _pattern(excerpt: str, *, currency: bool = False) -> str:
    canonical = " ".join(excerpt.translate(_QUOTES).split())
    if not canonical:
        return r"(?!)"
    start = r"(?<!\w)" if canonical[0].isalnum() else ""
    end = r"(?!\w)" if canonical[-1].isalnum() else ""
    if currency and canonical == "R":
        end = r"(?:(?!\w)|(?=\d))"
    if canonical[0].isdigit():
        start += r"(?<!\d[.,])"
    if canonical[-1].isdigit():
        end += r"(?![.,]\d)"
    body = "".join(_EQUIVALENTS.get(char, re.escape(char)) for char in canonical)
    return start + body + end


def source_quote(notes: str, quote: str | None) -> str | None:
    match = re.search(_pattern(quote or ""), notes)
    return match.group() if match else None


def _local_clause(notes: str, start: int, end: int) -> str:
    lower, upper = max(0, start - 160), min(len(notes), end + 160)
    for separator in _CLAUSE_END.finditer(notes, lower, upper):
        if separator.end() <= start:
            lower = separator.end()
        elif separator.start() >= end:
            upper = separator.end()
            break
    return notes[lower:upper].strip()


def _nearest_cue(clause: str, value: str) -> set[str]:
    match = re.search(_pattern(value), clause)
    if match is None:
        return set()
    cues = [
        (max(match.start() - cue.end(), cue.start() - match.end(), 0), field)
        for field, pattern in _FINANCIAL_CUES.items()
        for cue in re.finditer(pattern, clause, re.IGNORECASE)
    ]
    if not cues:
        return set()
    nearest = min(distance for distance, _ in cues)
    return {field for distance, field in cues if distance == nearest and distance <= 65}


def financial_source(
    notes: str,
    field: str,
    value: str,
    quote: str | None,
    *,
    allow_recovery: bool,
) -> tuple[str, str] | None:
    """Recover source-form value and evidence without converting or calculating a number."""
    if field == "currency" and not re.fullmatch(
        r"[A-Z]{3}|R|\$|£|€|rand|rands|dollars|pounds|euros", value
    ):
        return None
    if field != "currency" and (not _NUMERIC_WORD.search(value) or _VAGUE_NUMBER.search(value)):
        return None
    pattern = _pattern(value, currency=field == "currency")
    quoted_value = re.search(pattern, quote or "")
    if quoted_value and quote:
        # Only contextualise a quote that is itself uniquely located.
        locations = list(re.finditer(_pattern(quote), notes))
        if len(locations) == 1:
            start = locations[0].start() + quoted_value.start()
            end = start + len(quoted_value.group())
            clause = _local_clause(notes, start, end)
            if not _META_INSTRUCTIONS.search(clause):
                if field == "currency":
                    return quoted_value.group(), quote
                if _nearest_cue(clause, quoted_value.group()) == {field}:
                    evidence = (
                        quote if _nearest_cue(quote, quoted_value.group()) == {field} else clause
                    )
                    return quoted_value.group(), evidence
    if not allow_recovery:
        return None

    occurrences = list(re.finditer(pattern, notes))
    if len(occurrences) != 1:
        return None
    match = occurrences[0]
    clause = _local_clause(notes, match.start(), match.end())
    if _META_INSTRUCTIONS.search(clause):
        return None
    if field == "currency" or _nearest_cue(clause, match.group()) == {field}:
        return match.group(), clause
    return None


def quoted_financial_expressions(
    notes: str, field: str, quote: str
) -> list[str] | Literal["ambiguous"]:
    """Return original expressions in a uniquely anchored quote with a clear field cue."""
    expression = _QUOTED_EXPRESSIONS.get(field)
    if expression is None:
        return []
    locations = list(re.finditer(_pattern(quote), notes))
    if len(locations) != 1:
        return []
    results: list[str] = []
    for match in re.finditer(rf"(?<![\w+\-])(?:{expression})(?!\w|[.,]\d)", quote, re.IGNORECASE):
        start, end = locations[0].start() + match.start(), locations[0].start() + match.end()
        clause = _local_clause(notes, start, end)
        value = match.group()
        if _META_INSTRUCTIONS.search(clause) or _AMBIGUOUS_CHOICE.search(clause):
            continue
        if field == "adviser_fee" and _OTHER_FEE.search(clause):
            continue
        if field == "monthly_income" and (
            not re.search(rf"\b(?:{_MONTH})\b", clause, re.IGNORECASE)
            or _NON_MONTHLY.search(clause)
        ):
            continue
        if _nearest_cue(clause, value) != {field}:
            continue
        # A range endpoint cannot stand alone. Leave the quote available for review.
        previous = notes[max(0, start - 14) : start]
        following = notes[end : end + 24]
        if re.search(r"\d[\w%]*\s*(?:[-–]|\bto)\s*$", previous, re.IGNORECASE) or re.match(
            r"\s*(?:[-–]|\bto\b)\s*(?:USD|ZAR|GBP|EUR|R|[$£€])?\s*\d",
            following,
            re.IGNORECASE,
        ):
            return "ambiguous"
        results.append(value)
    return results


def is_approximate(quote: str, value: str) -> bool:
    match = re.search(_pattern(value), quote)
    if not match:
        return False
    return bool(
        _APPROXIMATE.search(quote[: match.start()])
        or re.match(r"(?i)^(?:about|roughly|approximately|around|maybe|call it|circa)\b", value)
    )


def explicit_choice(field: str, value: str | bool, quote: str) -> bool:
    quote = " ".join(quote.split())
    if _META_INSTRUCTIONS.search(quote) or _AMBIGUOUS_CHOICE.search(quote):
        return False
    if field == "income_requirement":
        cleaned, no = re.subn(_NO_INCOME, "", quote, flags=re.IGNORECASE)
        yes = bool(re.search(_YES_INCOME, cleaned, re.IGNORECASE))
        return (no > 0 and not yes) if value == "none" else (yes and not no)
    if field == "is_replacement":
        cleaned, no = re.subn(_NO_REPLACEMENT, "", quote, flags=re.IGNORECASE)
        yes = bool(re.search(_YES_REPLACEMENT, cleaned, re.IGNORECASE))
        return (no > 0 and not yes) if value is False else (yes and not no)
    direction = re.search(_RECIPIENT, quote, re.IGNORECASE)
    if not direction:
        return False
    recipient = quote[direction.end() :]
    term = r"\badvis[eo]r\b" if value == "advisor" else r"\bclient\b"
    match = re.search(term, recipient, re.IGNORECASE)
    return bool(match and not re.search(r"\bnot\b", recipient[: match.start()], re.IGNORECASE))


def income_quote_supports(notes: str, value: str | bool, quote: str) -> bool:
    locations = list(re.finditer(_pattern(quote), notes))
    for match in locations:
        end = match.end() - (1 if match.group()[-1] in ".!?;" else 0)
        clause = _local_clause(notes, match.start(), end)
        if not explicit_choice("income_requirement", value, clause):
            return False
    return bool(locations)


def no_income_findings(notes: str) -> list[tuple[str, str]]:
    """Find direct negative income statements and any explicitly competing requirement."""
    findings: list[tuple[str, str]] = []
    for clause in _CLAUSE_END.split(notes):
        quote = clause.strip()
        normal = " ".join(quote.split())
        if _META_INSTRUCTIONS.search(normal) or _AMBIGUOUS_CHOICE.search(normal):
            continue
        without_no, no_matches = re.subn(_NO_INCOME, "", normal, flags=re.IGNORECASE)
        if no_matches:
            findings.append(("none", quote))
        if re.search(_YES_INCOME, without_no, re.IGNORECASE):
            findings.append(("required", quote))
    return findings if any(value == "none" for value, _ in findings) else []
