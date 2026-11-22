"""Locate exact source excerpts and check simple field attribution."""

import re
from collections.abc import Iterator
from decimal import Decimal
from typing import Literal

_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
_EQUIVALENTS = {" ": r"\s+", '"': '["“”]', "'": "['‘’]"}
_CLAUSE_END = re.compile(r"[.!?](?=\s|$)|;|\n\s*\n")
_SPLIT = re.compile(
    r";|\r?\n[ \t]*\r?\n|\r?\n(?=[ \t]*[A-Za-z][A-Za-z ]{0,32}:)|[!?](?=\s|$)|(?<!\.)\.(?=\s|$)(?!\s*\.)"
)
_EXTERNAL = re.compile(
    r"\b(?:pasted|copied|unrelated|external|example|sample|hypothetical|illustrative|template)\b"
    r"|\b(?:ignore|disregard|override|forget)\b"
    r"|\b(?:system prompt|extraction policy|instructions?|do not report|assistant should)\b"
    r"|</?(?:system|assistant|user)\b|\[(?:/?INST|/?SYS)\]|^[ \t]*>",
    re.IGNORECASE,
)
_COMMAND = re.compile(
    r"(?:^|[:,])\s*['\"“‘]?(?:(?:please|then|now)\s+)?"
    r"(?:set|report|return|output|mark|pretend|insert|fabricate|enter|display|print|"
    r"record|use|write|state|treat|replace|choose|fill)\b"
    r"[^.!?;]{0,38}\b(?:capital|investment amount|advis[eo]r fee|currency|income)\b"
    r"|\b(?:tell|force|ask)\s+(?:the\s+)?(?:model|assistant|system)\b",
    re.IGNORECASE,
)
_IDENTITY_COMMAND = re.compile(
    r"(?:^|[:,])\s*[\"'“‘]?(?:please\s+)?(?:set|report|output|mark|fabricate|enter|"
    r"record|say|return|pretend|write|use|choose|insert|replace)\b[^.!?;]{0,35}"
    r"\b(?:client name|client identity|as (?:the )?client)\b",
    re.IGNORECASE,
)
_IDENTITY_EXTERNAL = re.compile(
    r"""^["'“‘]?(?:pasted|copied|external)\s+(?:message|instructions?|text)\s*:|"""
    r"</?(?:system|assistant|user)\b|\[(?:/?INST|/?SYS)\]|^>",
    re.IGNORECASE,
)
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
    r"|no need for (?:any )?(?:monthly )?(?:income|drawdown)"
    r"|(?:does not|do not|doesn['’]t|don['’]t|won['’]t|will not) (?:need|require) (?:any )?"
    r"(?:monthly )?(?:income|drawdown))\b"
)
_YES_INCOME = r"\b(?:needs? (?:a |monthly )?income|draw an income|(?:requires?|wants?) (?:a |monthly )?income|income (?:is )?(?:needed|required))\b"
_AMBIGUOUS_CHOICE = re.compile(
    r"\b(?:if|unless|whether|might|may|possibly|unclear|unknown|unconfirmed|never said"
    r"|did not say|didn['’]t say|does not say|doesn['’]t say|not confirmed)\b",
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
_DIGITS = r"(?:\d{1,3}(?:[ \u00a0\u202f]+\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)*)"
_SPOKEN_WORD = (
    r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
    r"|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|and|a|half)"
)
_SPOKEN = rf"{_SPOKEN_WORD}(?:[\s-]+{_SPOKEN_WORD}){{0,7}}"
_SCALE = r"(?:billion|million|thousand)"
_CURRENCY_PREFIX = r"(?:USD|ZAR|GBP|EUR|R|[$£€])"
_AMOUNT_CURRENCY = re.compile(rf"^{_HEDGE}({_CURRENCY_PREFIX})\s*(?=\d)", re.IGNORECASE)
_CAPITAL_NUMBER = re.compile(
    rf"^{_HEDGE}(?P<currency>{_CURRENCY_PREFIX})?\s*"
    r"(?P<number>(?:\d{1,3}(?:,\d{3})+|\d{1,3}(?:[ \u00a0\u202f]+\d{3})+|\d+)(?:\.\d+)?)"
    r"\s*(?P<scale>thousand|million|billion|[kmb])?$",
    re.IGNORECASE,
)
_SCALE_POWER = {"k": 3, "thousand": 3, "m": 6, "million": 6, "b": 9, "billion": 9}
_VAGUE_CAPITAL = re.compile(
    r"\b(?:a few|some|several)\s+(?:hundred|thousand|million|billion)\b"
    r"|\b(?:amount|capital|figure)\s+(?:is\s+)?(?:unknown|undecided|unconfirmed|not yet set)\b",
    re.IGNORECASE,
)
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
_DURATION_UNIT = re.compile(
    r"\b(?:years?|yrs?|months?|mos?|weeks?|wks?|days?|hours?|hrs?|decades?)\b", re.IGNORECASE
)
_DURATION_SUFFIX = re.compile(rf"^[\s+-]+{_DURATION_UNIT.pattern}", re.IGNORECASE)
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
    if currency and re.fullmatch(_CURRENCY_PREFIX, canonical, re.IGNORECASE):
        end = r"(?:(?!\w)|(?=\d))"
    if canonical[0].isdigit():
        start += r"(?<!\d[.,])"
    if canonical[-1].isdigit():
        end += r"(?![.,]\d|[ \u00a0\u202f]+\d{3}\b)"
    body = "".join(_EQUIVALENTS.get(char, re.escape(char)) for char in canonical)
    return "(?i)" + start + body + end


def source_quote(notes: str, quote: str | None) -> str | None:
    match = re.search(_pattern(quote or ""), notes)
    if match:
        return match.group()
    # Only tolerate changed terminal punctuation, preserving decimals and internal punctuation.
    trimmed = (quote or "").strip().rstrip(".,;!?")
    if trimmed and trimmed != (quote or "").strip():
        match = re.search(_pattern(trimmed) + r"[.,;!?]?", notes)
    return match.group() if match else None


def admissible_clauses(notes: str, *, identity: bool = False) -> Iterator[tuple[int, str]]:
    start = 0
    external_block = False
    external, command = (
        (_IDENTITY_EXTERNAL, _IDENTITY_COMMAND) if identity else (_EXTERNAL, _COMMAND)
    )
    # An explicitly imported block remains untrusted until a paragraph boundary.
    for delimiter in (*_SPLIT.finditer(notes), None):
        end = delimiter.start() if delimiter else len(notes)
        clause = notes[start:end].strip()
        if clause:
            if external.search(clause) or (identity and _META_INSTRUCTIONS.search(clause)):
                external_block = True
            if not external_block and not command.search(clause):
                yield start + len(notes[start:end]) - len(notes[start:end].lstrip()), clause
        if delimiter and delimiter.group().count("\n") == 2:
            external_block = False
        start = delimiter.end() if delimiter else len(notes)


def admissible_anchor(
    notes: str, quote: str, safe_clauses: list[tuple[int, str]], *, unique: bool = True
) -> tuple[int, int] | None:
    located = source_quote(notes, quote)
    if located is None:
        return None
    start = notes.index(located)
    end = start + len(located)
    if unique and source_quote(notes[end:], quote) is not None:
        return None
    # A multi-sentence quote may include punctuation removed by the scan.
    # Every substantive character must be in a trusted source segment.
    cursor = start
    for offset, clause in safe_clauses:
        right = offset + len(clause)
        if right <= cursor or offset >= end:
            continue
        if notes[cursor:offset].strip(" \t\r\n.!?;"):
            return None
        cursor = max(cursor, right)
        if cursor >= end:
            return start, end
    return (start, end) if not notes[cursor:end].strip(" \t\r\n.!?;") else None


def amount_currency_prefix(amount: str) -> str | None:
    match = _AMOUNT_CURRENCY.match(amount)
    return match.group(1) if match else None


def equivalent_capital(proposed: str, source: str) -> bool:
    """Compare bounded digit forms without converting currency or returning a new value."""
    left = _CAPITAL_NUMBER.fullmatch(proposed.strip())
    right = _CAPITAL_NUMBER.fullmatch(source.strip())
    if not left or not right:
        return False
    left_currency, right_currency = left["currency"], right["currency"]
    if left_currency and (
        not right_currency or left_currency.casefold() != right_currency.casefold()
    ):
        return False

    def magnitude(match: re.Match[str]) -> Decimal | None:
        number = re.sub(r"[, \u00a0\u202f]", "", match["number"])
        if len(number) > 18:
            return None
        return Decimal(number).scaleb(_SCALE_POWER.get((match["scale"] or "").lower(), 0))

    expected = magnitude(right)
    return expected is not None and magnitude(left) == expected


def vague_capital(notes: str, quote: str, value: str | bool | None) -> bool:
    if not _VAGUE_CAPITAL.search(quote):
        return False
    if value is not None and (not isinstance(value, str) or not source_quote(quote, value)):
        return False
    matches = list(re.finditer(_pattern(quote), notes))
    if len(matches) != 1:
        return False
    match = matches[0]
    clause = _local_clause(notes, match.start(), match.end())
    return bool(
        re.search(
            _FINANCIAL_CUES["investment_amount"] + r"|\b(?:amount|capital)\b", clause, re.IGNORECASE
        )
        and not _META_INSTRUCTIONS.search(clause)
    )


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


def has_duration_unit(value: str) -> bool:
    return bool(_DURATION_UNIT.search(value))


def _is_money_span(value: str, notes: str, end: int) -> bool:
    return bool(
        re.fullmatch(_QUOTED_EXPRESSIONS["investment_amount"], value, re.IGNORECASE)
        and not _DURATION_SUFFIX.match(notes[end:])
    )


def financial_source(
    notes: str,
    field: str,
    value: str,
    quote: str,
) -> tuple[str, str] | None:
    """Recover source-form value and evidence without converting or calculating a number."""
    if field == "currency" and not (
        re.fullmatch(r"[A-Z]{3}", value)
        or re.fullmatch(rf"{_CURRENCY_PREFIX}|rands?|dollars|pounds|euros", value, re.IGNORECASE)
    ):
        return None
    if field != "currency" and (not _NUMERIC_WORD.search(value) or _VAGUE_NUMBER.search(value)):
        return None
    if field == "investment_amount" and not re.fullmatch(
        _QUOTED_EXPRESSIONS["investment_amount"], value, re.IGNORECASE
    ):
        return None
    pattern = _pattern(value, currency=field == "currency")
    quoted_value = re.search(pattern, quote)
    if quoted_value:
        # Only contextualise a quote that is itself uniquely located.
        locations = list(re.finditer(_pattern(quote), notes))
        if len(locations) == 1:
            start = locations[0].start() + quoted_value.start()
            end = start + len(quoted_value.group())
            clause = _local_clause(notes, start, end)
            if not _META_INSTRUCTIONS.search(clause) and (
                field != "investment_amount" or _is_money_span(quoted_value.group(), notes, end)
            ):
                if field == "currency":
                    return quoted_value.group(), quote
                if _nearest_cue(clause, quoted_value.group()) == {field}:
                    evidence = (
                        quote if _nearest_cue(quote, quoted_value.group()) == {field} else clause
                    )
                    return quoted_value.group(), evidence
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
    boundary = r"(?!\w|[.,]\d|[ \u00a0\u202f]+\d{3}\b)"
    for match in re.finditer(rf"(?<![\w+\-])(?:{expression}){boundary}", quote, re.IGNORECASE):
        start, end = locations[0].start() + match.start(), locations[0].start() + match.end()
        clause = _local_clause(notes, start, end)
        value = match.group()
        if field == "investment_amount" and not _is_money_span(value, notes, end):
            continue
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
