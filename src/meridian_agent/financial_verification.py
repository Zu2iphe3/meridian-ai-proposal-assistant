"""Verify original note evidence independently of the extraction provider."""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from meridian_agent.extraction import ExtractionResult
from meridian_agent.source_evidence import admissible_anchor as _anchor
from meridian_agent.source_evidence import admissible_clauses as _clauses
from meridian_agent.source_evidence import equivalent_capital, is_approximate, source_quote

FinancialField = Literal[
    "investment_amount", "currency", "adviser_fee", "income_requirement", "income_amount"
]
State = Literal["verified", "missing", "unresolved", "conflict"]
Frequency = Literal["monthly", "quarterly", "annual", "weekly", "one_off"]
_FIELDS: tuple[FinancialField, ...] = (
    "investment_amount",
    "currency",
    "adviser_fee",
    "income_requirement",
    "income_amount",
)


class SourceFinding(BaseModel):
    source_expression: str
    start: int
    end: int
    quote: str
    quote_start: int
    value: str | None = None
    currency: str | None = None
    frequency: Frequency | None = None
    uncertainty: Literal["none", "approximate", "unresolved"] = "none"
    disposition: Literal["current", "superseded"] = "current"


class VerifiedField(BaseModel):
    status: State
    source: Literal["extraction_confirmed", "note_scan"] | None = None
    value: str | None = None
    unit: str | None = None
    frequency: Frequency | None = None
    uncertainty: Literal["none", "approximate", "unresolved"] = "none"
    evidence: list[SourceFinding]
    reason: str | None = None


class ReviewCheck(BaseModel):
    status: State
    value: str | None = None
    quote: str | None = None
    reason: str | None = None


class FinancialVerification(BaseModel):
    fields: dict[FinancialField, VerifiedField]
    mapping_candidates: dict[FinancialField, str]
    excluded_evidence: list[SourceFinding]
    horizon: ReviewCheck
    risk: ReviewCheck
    portfolio: ReviewCheck


_SMALL = dict(
    zip(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
        ],
        range(20),
        strict=True,
    )
)
_TENS = dict(
    zip(
        ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"],
        range(20, 100, 10),
        strict=True,
    )
)
_INT_WORDS = "|".join((*_SMALL, *_TENS, "hundred", "thousand", "and", "a", "half"))
_WORD_NUMBER = (
    rf"(?:{'|'.join((*_SMALL, *_TENS, 'a'))})"
    rf"(?:[\s-]+(?:{_INT_WORDS})){{0,7}}(?<!\band)(?<!\ba)"
    r"|a(?=\s+(?:hundred|thousand|million|billion)\b)"
)
_DIGITS = r"(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)*)"
_MAGNITUDES = {
    "k": 1000,
    "thousand": 1000,
    "m": 1000000,
    "million": 1000000,
    "b": 1000000000,
    "billion": 1000000000,
}
_CURRENCIES = {
    "r": "ZAR",
    "rand": "ZAR",
    "zar": "ZAR",
    "usd": "USD",
    "us dollars": "USD",
    "us$": "USD",
    "gbp": "GBP",
    "£": "GBP",
    "pounds": "GBP",
    "sterling": "GBP",
    "eur": "EUR",
    "€": "EUR",
    "euros": "EUR",
    "$": None,
    "dollars": None,
}
_CURRENCY = r"US dollars|US\$|ZAR|USD|GBP|EUR|sterling|rand|dollars|pounds|euros|R|[$£€]"
_TIMING = {
    "monthly": r"monthly|(?:a|per|each|every)\s+month",
    "quarterly": r"quarterly|(?:a|per|each|every)\s+quarter",
    "annual": r"annually|annual|yearly|(?:a|per|each|every)\s+year",
    "weekly": r"weekly|(?:a|per|each|every)\s+week",
    "one_off": r"one[- ]off|once only",
}
_FREQUENCIES: tuple[tuple[Frequency, re.Pattern[str]], ...] = (
    ("monthly", re.compile(rf"\b(?:{_TIMING['monthly']})\b", re.IGNORECASE)),
    ("quarterly", re.compile(rf"\b(?:{_TIMING['quarterly']})\b", re.IGNORECASE)),
    ("annual", re.compile(rf"\b(?:{_TIMING['annual']})\b", re.IGNORECASE)),
    ("weekly", re.compile(rf"\b(?:{_TIMING['weekly']})\b", re.IGNORECASE)),
    ("one_off", re.compile(rf"\b(?:{_TIMING['one_off']})\b", re.IGNORECASE)),
)
_TIME = "|".join(_TIMING.values())
_HEDGE = r"about|around|roughly|approximately|circa|maybe(?:\s*\.\.\.)?|call\s+it|nearly"
_EXPRESSION = re.compile(
    rf"(?<![\w.,])(?P<sign>[+\-−])?(?:(?P<hedge>{_HEDGE})\s+)?"
    rf"(?:(?P<prefix>{_CURRENCY})\s*(?=[\d])|(?P<word_prefix>{_CURRENCY})\s+)?"
    rf"(?P<number>{_DIGITS}|half|(?:{_WORD_NUMBER})(?:\s+point(?:\s+(?:{'|'.join(_SMALL)})){{1,6}})?)"
    r"(?:\s*(?P<scale>billion|million|thousand|[kmb]))?"
    rf"(?:\s*(?P<percent>%|(?:a\s+)?(?:per\s+cent|percent))|[ ,]+(?P<suffix>{_CURRENCY}))?"
    rf"(?:\s+(?P<frequency>{_TIME}))?(?!\w|[.,]\d)",
    re.IGNORECASE,
)
_ADVICE = (
    r"(?:(?:our |annual |agreed |current |separate |revised |corrected |earlier |updated )*"
    r"(?:advis[eo]r(?:y)? (?:fees?|charges?)|advice fees?|(?:charge|fee) for (?:our |the )?advice))"
)
_CAPITAL_BEFORE = (
    r"(?:\b(?:capital|amount|sum|money|figure)(?:\s+(?:earmarked|set aside))?"
    r"\s+(?:for investment|to invest|to (?:place|put) in(?:to)? (?:the )?(?:mandate|portfolio))"
    r"|\b(?:investment (?:capital|amount|figure)|capital commitment|lump sum)"
    r"|\b(?:earmarked|set aside|to invest|will invest|investing|invest|commit(?:s|ted)?|"
    r"allocate(?:s|d)?|deploy(?:s|ed)?|put(?:ting)?)"
    r"|\b(?:capital|amount)\s*:)"
    r"[\s:\"'“”‘’]*(?:(?:is|was|will be|of|at|from|initially|either|between|the sum of)\s+)*"
    rf"(?:(?:{_HEDGE})\s+)?$"
)
_CAPITAL_AFTER = (
    r"^[\s\"'“”‘’]*(?:(?:is\s+|was\s+)?(?:available|earmarked|allocated|committed|set aside)\s+for\s+"
    r"(?:investment|(?:the|this)\s+(?:mandate|portfolio))\b"
    r"|(?:investment|investable)\s+(?:figure|capital|amount)\b"
    r"|(?:to|for)\s+(?:invest(?:ment|ing)?\b|put\s+in\b|(?:the|this|a new|new)\s+(?:mandate|investment|portfolio)\b)"
    r"|into\s+(?:the|this|a new)\s+(?:mandate|investment|portfolio)\b)"
)
_FEE_BEFORE = (
    rf"\b{_ADVICE}[\s:,]*(?:(?:is|was|will be|agreed|agreed at|of|at|to|the usual|now|either)\s+)*$"
)
_FEE_AFTER = (
    r"^[\s,]*(?:(?:is|was)\s+)?(?:(?:also|separately)\s+)?"
    r"(?:(?:quoted|recorded|listed|proposed|mentioned)\s+)?"
    rf"(?:(?:as|for)\s+(?:(?:the|an?|our)\s+)?)?{_ADVICE}\b"
)
_OTHER_FEE = re.compile(
    r"\b(?:management|performance|platform|administration|admin|brokerage|custody)\s+(?:fee|charge)\b",
    re.IGNORECASE,
)
_DRAW_BEFORE = (
    r"\b(?:(?:monthly|quarterly|annual|weekly)\s+(?:income|draw(?:down)?|withdrawal|payout)"
    r"|(?:monthly\s+)?(?:income|drawdown|withdrawals?|distributions?|payouts?)"
    r"|(?:need|needs|require|requires|withdraw|draw|take|pay out)(?:\s+to\s+(?:take|draw|withdraw))?)"
    r"[\s:]*(?:(?:of|is|was|at|the amount of)\s+)*$"
)
_DRAW_AFTER = r"^[\s,]*(?:as\s+(?:income|a drawdown)|(?:in|of)\s+(?:monthly\s+)?income|for (?:income|living expenses))\b"
_NO_INCOME = re.compile(
    r"\b(?:no\s+(?:(?:monthly|regular|ongoing)\s+)?(?:income|drawdown|withdrawals?|distributions?|cash)"
    r"\s+(?:(?:will be|is|are|being|to be)\s+)?(?:required|needed|paid(?: out)?|taken)"
    r"|(?:income|drawdown|income withdrawals)\s*:?\s+(?:is\s+|are\s+)?not\s+(?:needed|required)"
    r"|(?:nothing|no cash)\s+(?:is\s+)?to be\s+(?:withdrawn for income|paid out)"
    r"|no need for (?:(?:any|monthly|regular)\s+)*(?:income|withdrawals?|drawdown)"
    r"|(?:does not|do not|doesn['’]t|don['’]t|won['’]t|will not)\s+(?:need|require)\s+"
    r"(?:(?:a|any|monthly|regular|ongoing)\s+)*(?:income|withdrawals?|drawdown))\b",
    re.IGNORECASE,
)
_YES_INCOME = re.compile(
    r"\b(?:(?:wants?|needs?|requires?|will)\s+(?:(?:a|regular|monthly|quarterly|annual)\s+)*"
    r"(?:income|drawdown|withdrawals?)|(?:wants?|needs?)\s+to\s+draw\s+an\s+income"
    r"|(?:income|drawdown|withdrawal)\s+(?:is\s+)?(?:needed|required|essential))\b",
    re.IGNORECASE,
)
_CONDITIONAL = re.compile(
    r"\b(?:if|unless|otherwise|depending on|subject to|might|possibly|whether)\b", re.IGNORECASE
)
_NEGATED = re.compile(
    r"\b(?:not|never|no|neither|exclude[ds]?|wrong|incorrect|rejected)\b", re.IGNORECASE
)
_UNCERTAIN = re.compile(
    r"\b(?:either|unconfirmed|undecided|not (?:yet )?(?:chosen|confirmed|settled|agreed)"
    r"|(?:still |yet )?to be confirmed|between|up to|at least|more than|less than)\b",
    re.IGNORECASE,
)
_VAGUE = re.compile(
    r"""\b(?:a few|several|some)\s+(?:hundred|thousand|million|billion)(?:[\s,"'“”]+(?:rand|pounds|euros|dollars))?\b""",
    re.IGNORECASE,
)
_CURRENCY_LABEL = re.compile(
    r"\b(?:investment\s+currency|currency)\s*(?::|is)\s*(?P<token>[a-z]{3,}|[$£€])(?!\w)",
    re.IGNORECASE,
)
_NON_PROPOSAL_ROLE = re.compile(
    r"^\s*(?:(?:to|for|in)\s+(?:the\s+|an?\s+)?)?"
    r"(?:pay|cover|repay|reserve|emergency|operating|equipment|debt|rent|salary|property purchase)\b",
    re.IGNORECASE,
)
_OTHER_AMOUNT = re.compile(
    r"\b(?:reserve|buffer|turnover|revenue|cost|salary|budget|management fee|target return"
    r"|(?:regular|monthly|quarterly|annual)\s+contribution|contributions?\s+from\s+\w+)"
    r"(?:\s+(?:is|was|of|at|totals?))*[\s:]*$",
    re.IGNORECASE,
)
_RESERVE_AFTER = re.compile(
    r"^[\s,]*(?:(?:is|was|will)\s+)?(?:(?:held|kept|retained|reserved|set aside|remain)\s+)?"
    r"(?:separately\s+)?(?:as|for|in)\s+(?:(?:a|an|the|her|his|their)\s+)?"
    r"(?:emergency|reserve|cash buffer|(?:operating|savings) account|equipment|budget)\b",
    re.IGNORECASE,
)
_DENOMINATION = re.compile(
    rf"\b(?:mandate|portfolio|investment|capital)\b[^.;!?]{{0,45}}?\b"
    rf"(?:denominated|to be invested)\s+in\s+(?P<token>{_CURRENCY})(?!\w)",
    re.IGNORECASE,
)
_MONEY_ROLES = ("investment_amount", "income_amount", "adviser_fee")
_CAPITAL_CONTEXT = re.compile(r"\b(?:invest(?:ment|ing|s|ed)?|capital|mandate)\b", re.IGNORECASE)
_BARE_CURRENCY = re.compile(r"\b(?:rand|pounds|euros|dollars)\b", re.IGNORECASE)
_RESERVE_CURRENCY = re.compile(
    r"^\s+(?:for|of|in)\s+(?:(?:an?|the)\s+)?(?:operating|emergency|cash)\s+reserve\b",
    re.IGNORECASE,
)
_EXCLUDED_AMOUNT = re.compile(r"\bexclud(?:ing|es?)\s+(?:the\s+)?$", re.IGNORECASE)
_OTHER_FEE_BEFORE = re.compile(
    r"\b(?:(?:management|platform|brokerage|custody|admin(?:istration)?|performance|target return)"
    r"(?:\s+(?:charge|fee|is|was|of|at|discussed|quoted))*|CPI\s*(?:\+|plus))[\s:]*$",
    re.IGNORECASE,
)


def _whole(words: list[str]) -> int | None:
    if len(words) == 1:
        return 1 if words[0] == "a" else _SMALL.get(words[0], _TENS.get(words[0]))
    if words.count("hundred") == 1 and words[1] == "hundred":
        hundreds = _whole(words[:1])
        tail = words[2:]
        rest = _whole(tail[1:] if tail[:1] == ["and"] else tail) if tail else 0
        if hundreds is not None and 1 <= hundreds <= 9 and rest is not None and rest < 100:
            return hundreds * 100 + rest
    if len(words) == 2 and words[0] in _TENS and 1 <= _SMALL.get(words[1], 0) <= 9:
        return _TENS[words[0]] + _SMALL[words[1]]
    return None


def _number(raw: str, *, rate: bool = False) -> Decimal | None:
    if raw[0].isdecimal():
        compact = raw.replace("\u00a0", " ").replace("\u202f", " ")
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+\.\d+|\d{1,3}(?:,\d{3})+", compact) and not (
            rate and compact.count(",") == 1 and "." not in compact
        ):
            compact = compact.replace(",", "")
        elif re.fullmatch(r"\d{1,3}(?: \d{3})+(?:\.\d+)?", compact):
            compact = compact.replace(" ", "")
        elif rate and re.fullmatch(r"\d+,\d{1,2}", compact):
            compact = compact.replace(",", ".")
        if re.fullmatch(r"\d{1,18}(?:\.\d{1,8})?", compact):
            return Decimal(compact)
        return None
    if raw.casefold() == "half":
        return Decimal("0.5")
    words = re.split(r"[\s-]+", raw.casefold())
    if "point" in words:
        index = words.index("point")
        lead, tail = _whole(words[:index]), words[index + 1 :]
        if lead is not None and tail and all(0 <= _SMALL.get(word, 10) < 10 for word in tail):
            return Decimal(str(lead) + "." + "".join(str(_SMALL[word]) for word in tail))
        return None
    if words[-3:] == ["and", "a", "half"]:
        whole = _whole(words[:-3])
        return Decimal(whole) + Decimal("0.5") if whole is not None else None
    if "thousand" in words:
        index = words.index("thousand")
        lead = _whole(words[:index])
        tail = words[index + 1 :]
        rest = _whole(tail[1:] if tail[:1] == ["and"] else tail) if tail else 0
        if lead is not None and rest is not None and "thousand" not in tail:
            return Decimal(lead * 1000 + rest)
    whole = _whole(words)
    return Decimal(whole) if whole is not None else None


def _decimal(number: Decimal) -> str:
    text = format(number, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _frequency(text: str) -> Frequency | None:
    matches = [name for name, pattern in _FREQUENCIES if pattern.search(text)]
    return matches[0] if len(matches) == 1 else None


def _finding(
    offset: int,
    clause: str,
    match: re.Match[str],
    *,
    value: str | None = None,
    currency: str | None = None,
    frequency: Frequency | None = None,
    uncertainty: Literal["none", "approximate", "unresolved"] = "none",
    disposition: Literal["current", "superseded"] = "current",
) -> SourceFinding:
    return SourceFinding(
        source_expression=match.group(),
        start=offset + match.start(),
        end=offset + match.end(),
        quote=clause,
        quote_start=offset,
        value=value,
        currency=currency,
        frequency=frequency,
        uncertainty=uncertainty,
        disposition=disposition,
    )


def _attach_currency(offset: int, clause: str, match: re.Match[str]) -> SourceFinding | None:
    tokens = [name for name in ("prefix", "word_prefix", "suffix") if match[name]]
    if not tokens:
        return None
    values = [_CURRENCIES.get(match[name].casefold()) for name in tokens]
    token = tokens[-1]
    return SourceFinding(
        source_expression=match[token],
        start=offset + match.start(token),
        end=offset + match.end(token),
        quote=clause,
        quote_start=offset,
        value=values[-1] if len(set(values)) == 1 else None,
        uncertainty="none" if len(set(values)) == 1 and values[-1] else "unresolved",
    )


@dataclass(frozen=True)
class Expression:
    evidence: SourceFinding
    role: FinancialField | None
    money: bool
    rate: bool
    currency: SourceFinding | None


def _scan(
    clauses: list[tuple[int, str]],
) -> tuple[list[Expression], list[SourceFinding], dict[FinancialField, list[SourceFinding]]]:
    expressions: list[Expression] = []
    excluded: list[SourceFinding] = []
    direct: dict[FinancialField, list[SourceFinding]] = {field: [] for field in _FIELDS}
    for offset, clause in clauses:
        uncertain = bool(_CONDITIONAL.search(clause) or _UNCERTAIN.search(clause))
        for match in _EXPRESSION.finditer(clause):
            before, after = clause[: match.start()], clause[match.end() :]
            currency = _attach_currency(offset, clause, match)
            money = bool(currency or match["scale"])
            rate = bool(match["percent"])
            advice = bool(
                re.search(_FEE_BEFORE, before, re.IGNORECASE)
                or re.match(_FEE_AFTER, after, re.IGNORECASE)
            )
            if not (money or rate or advice):
                continue
            numeric = _number(match["number"], rate=rate)
            if numeric is not None:
                numeric *= _MAGNITUDES.get((match["scale"] or "").casefold(), 1)
                if match["sign"] or (rate and numeric > 100):
                    numeric = None
            frequency = _frequency(match["frequency"] or before[-38:])
            finding = _finding(
                offset,
                clause,
                match,
                value=_decimal(numeric) if numeric is not None else None,
                currency=currency.value if currency else None,
                frequency=frequency,
                uncertainty="unresolved"
                if uncertain or numeric is None
                else ("approximate" if match["hedge"] else "none"),
            )
            if (
                _OTHER_AMOUNT.search(before)
                or _OTHER_FEE.match(after.lstrip())
                or _RESERVE_AFTER.match(after)
                or _NON_PROPOSAL_ROLE.match(after)
                or (money and _EXCLUDED_AMOUNT.search(before))
                or (rate and _OTHER_FEE_BEFORE.search(before))
            ):
                excluded.append(finding)
                continue
            role: FinancialField | None = None
            if advice and not money:
                role = "adviser_fee"
                if not rate:
                    finding.uncertainty = "unresolved"
            elif money and re.match(
                r"^\s*[- ]?(?:years?|months?|weeks?|days?|decades?)\b", after, re.IGNORECASE
            ):
                continue
            elif money and (
                re.search(_CAPITAL_BEFORE, before, re.IGNORECASE)
                or re.match(_CAPITAL_AFTER, after, re.IGNORECASE)
            ):
                role = "investment_amount"
                if match["frequency"] or numeric == 0:
                    finding.uncertainty = "unresolved"
            elif money and (
                re.match(_DRAW_AFTER, after, re.IGNORECASE)
                or (
                    re.search(_DRAW_BEFORE, before, re.IGNORECASE)
                    and (
                        frequency
                        or re.search(
                            r"\b(?:income|drawdown|withdrawal|payout|distribution)\b",
                            before[-45:],
                            re.IGNORECASE,
                        )
                    )
                )
            ):
                role = "income_amount"
                direct["income_requirement"].append(
                    finding.model_copy(update={"value": "required"})
                )
            expressions.append(Expression(finding, role, money, rate, currency))

        # These literal statements are eligible for review even without a model proposal.
        negatives = list(_NO_INCOME.finditer(clause))
        for match in negatives:
            direct["income_requirement"].append(
                _finding(
                    offset,
                    clause,
                    match,
                    value="none",
                    uncertainty="unresolved" if uncertain else "none",
                )
            )
        for match in _YES_INCOME.finditer(clause):
            if not any(
                n.start() <= match.start() < n.end() for n in negatives
            ) and not _NEGATED.search(clause[max(0, match.start() - 30) : match.start()]):
                direct["income_requirement"].append(
                    _finding(
                        offset,
                        clause,
                        match,
                        value="required",
                        uncertainty="unresolved" if uncertain else "none",
                    )
                )
        for match in (*_CURRENCY_LABEL.finditer(clause), *_DENOMINATION.finditer(clause)):
            token = match["token"]
            finding = SourceFinding(
                source_expression=token,
                start=offset + match.start("token"),
                end=offset + match.end("token"),
                quote=clause,
                quote_start=offset,
                value=_CURRENCIES.get(token.casefold()),
                uncertainty="none" if _CURRENCIES.get(token.casefold()) else "unresolved",
            )
            if _RESERVE_CURRENCY.match(clause[match.end("token") :]):
                excluded.append(finding)
            else:
                direct["currency"].append(finding)
        if re.fullmatch(r"ZAR|GBP|EUR|USD", clause, re.IGNORECASE):
            direct["currency"].append(
                SourceFinding(
                    source_expression=clause,
                    start=offset,
                    end=offset + len(clause),
                    quote=clause,
                    quote_start=offset,
                    value=clause.upper(),
                )
            )
        if _CAPITAL_CONTEXT.search(clause):
            for match in _VAGUE.finditer(clause):
                direct["investment_amount"].append(
                    _finding(offset, clause, match, uncertainty="unresolved")
                )
                for token in _BARE_CURRENCY.finditer(match.group()):
                    direct["currency"].append(
                        _finding(
                            offset + match.start(),
                            match.group(),
                            token,
                            value=_CURRENCIES.get(token.group().casefold()),
                        ).model_copy(update={"quote": clause, "quote_start": offset})
                    )
        if uncertain:
            # A separately stated unresolved field is a veto, not a value.
            labels: tuple[tuple[FinancialField, str], ...] = (
                ("adviser_fee", _ADVICE),
                (
                    "investment_amount",
                    r"\b(?:investment (?:amount|figure|capital)|capital to invest)\b",
                ),
            )
            for name, label in labels:
                if not any(
                    item.role == name and item.evidence.quote_start == offset
                    for item in expressions
                ):
                    found = re.search(label, clause, re.IGNORECASE)
                    if found:
                        direct[name].append(
                            _finding(offset, clause, found, uncertainty="unresolved")
                        )
    return expressions, excluded, direct


@dataclass(frozen=True)
class Proposal:
    quote: str
    value: str | None
    eligible: bool


def _grounded_proposals(
    notes: str, field: FinancialField, extraction: ExtractionResult
) -> list[Proposal]:
    proposals: list[Proposal] = []
    if field != "income_amount":
        for candidate in (extraction.fields[field], *extraction.conflicts.get(field, [])):
            if candidate.quote:
                proposals.append(
                    Proposal(
                        candidate.quote,
                        candidate.value if isinstance(candidate.value, str) else None,
                        candidate.uncertainty != "unresolved",
                    )
                )
    model_field = "monthly_income" if field == "income_amount" else field
    for item in extraction.review_candidates:
        if item.proposed.field != model_field:
            continue
        quote = item.verified_quote or source_quote(notes, item.proposed.quote)
        value = item.proposed.value if isinstance(item.proposed.value, str) else None
        if quote is None:
            if value and item.reason_code in {"quote_not_found", "quote_missing"}:
                proposals.append(Proposal(value, value, False))
            continue
        # A matching financial span can recover a semantic-only rejection.
        # A contradictory value, missing quote or unsafe field shape grants no authority.
        if item.reason_code in {
            "unsupported_financial_value",
            "ambiguous_source_expression",
            "noncore_suggestion",
        }:
            proposals.append(Proposal(quote, value, True))
        elif item.reason_code in {"source_does_not_support_choice", "value_not_supported_by_quote"}:
            proposals.append(Proposal(quote, value, False))
    return proposals


def _proposal_matches(field: FinancialField, expression: SourceFinding, value: str) -> bool:
    if field == "currency":
        return _CURRENCIES.get(value.casefold()) == expression.value
    if field == "income_requirement":
        return value.casefold() == expression.value
    if source_quote(expression.source_expression, value):
        return True
    if expression.value is None:
        return False
    if field == "adviser_fee":
        # Sources such as "half a percent" and "0.50%" can express the same rate.
        match = _EXPRESSION.fullmatch(value)
        return bool(
            match
            and match["percent"]
            and _number(match["number"], rate=True) == Decimal(expression.value)
        )
    return field == "investment_amount" and equivalent_capital(value, expression.source_expression)


def _compatible(field: FinancialField, item: Expression) -> bool:
    if item.role is not None:
        return item.role == field
    if field == "adviser_fee":
        return item.rate
    return item.money and (
        field == "investment_amount"
        or (field == "income_amount" and item.evidence.frequency is not None)
    )


def _evidence_key(
    field: FinancialField, item: SourceFinding
) -> tuple[str | None, str | None, Frequency | None]:
    return (
        item.value,
        item.currency if field in ("investment_amount", "income_amount") else None,
        item.frequency if field == "income_amount" else None,
    )


def _resolve(
    field: FinancialField,
    notes: str,
    clauses: list[tuple[int, str]],
    extraction: ExtractionResult,
    expressions: list[Expression],
    direct: list[SourceFinding],
    excluded: list[SourceFinding],
) -> VerifiedField:
    compatible = [item for item in expressions if _compatible(field, item)]
    direct = [*direct, *(item.evidence for item in compatible if item.role == field)]
    anchored: list[tuple[Proposal, tuple[int, int]]] = [
        (proposal, span)
        for proposal in _grounded_proposals(notes, field, extraction)
        if (span := _anchor(notes, proposal.quote, clauses)) is not None
    ]
    proposed: list[SourceFinding] = []
    review: list[SourceFinding] = []
    for proposal, (start, end) in anchored:
        matched = [
            item
            for item in [*direct, *(item.evidence for item in compatible)]
            if start <= item.start
            and item.end <= end
            and proposal.value
            and _proposal_matches(field, item, proposal.value)
            and item.value is not None
        ]
        if matched and proposal.eligible:
            proposed.extend(matched)
        elif field == "currency" and any(
            start <= item.start
            and item.end <= end
            and proposal.value is not None
            and _proposal_matches(field, item, proposal.value)
            for item in excluded
        ):
            # Keep explicitly excluded denominations in the ledger without making
            # them candidates for the investable capital's currency.
            continue
        elif (
            not proposal.eligible
            or proposal.value is None
            or (proposal.value is not None and source_quote(notes[start:end], proposal.value))
        ):
            # Keep a grounded but unnormalisable range, pending choice, or
            # currency without a usable unit visible for review.
            marker = source_quote(notes[start:end], proposal.value) if proposal.value else None
            text = notes[start:end]
            if marker or not proposal.eligible or proposal.value is None:
                pos = text.index(marker) if marker else 0
                review.append(
                    SourceFinding(
                        source_expression=marker or text,
                        start=start + pos,
                        end=start + pos + len(marker or text),
                        quote=text,
                        quote_start=start,
                        uncertainty="unresolved",
                    )
                )

    eligible = proposed or direct
    evidence = {(item.start, item.end): item for item in [*review, *direct, *proposed]}
    # An unattributed expression may block a proposal but cannot establish a value.
    if field in _MONEY_ROLES:
        for item in compatible:
            if item.role is not None:
                continue
            finding = item.evidence
            if (field == "investment_amount" and _CAPITAL_CONTEXT.search(finding.quote)) or bool(
                eligible or review
            ):
                key = finding.start, finding.end
                if key not in evidence or evidence[key].value is None:
                    evidence[key] = finding.model_copy(update={"uncertainty": "unresolved"})
    proposed_spans = {(item.start, item.end) for item in proposed}
    ordered = sorted(
        evidence.values(),
        key=lambda item: ((item.start, item.end) not in proposed_spans, item.start, item.end),
    )
    if not ordered:
        return VerifiedField(status="missing", evidence=[])
    usable = [
        item for item in eligible if item.value is not None and item.uncertainty != "unresolved"
    ]
    keys = {_evidence_key(field, item) for item in ordered if item.value is not None}
    if len(keys) > 1 and (field == "adviser_fee" or bool(usable) and field != "investment_amount"):
        return VerifiedField(
            status="conflict",
            evidence=ordered,
            uncertainty="unresolved",
            reason="pm_confirm_source_backed_proposal"
            if proposed
            else "competing_source_statements",
        )
    blockers = [
        item
        for item in ordered
        if item.uncertainty == "unresolved"
        and (
            item.value is None
            or _evidence_key(field, item)
            not in {_evidence_key(field, finding) for finding in usable}
        )
    ]
    # A review quote covering only the expressions already independently accounted
    # for adds context. An unresolved statement about their applicability is a veto.
    blockers = [
        item
        for item in blockers
        if not (
            item in review
            and item.value is None
            and any(item.start <= finding.start and finding.end <= item.end for finding in usable)
            and not (_UNCERTAIN.search(item.quote) or _CONDITIONAL.search(item.quote))
        )
    ]
    if not usable or blockers or len(keys) > 1:
        return VerifiedField(
            status="unresolved",
            evidence=ordered,
            uncertainty="unresolved",
            reason="pm_confirm_source_backed_proposal"
            if proposed or anchored
            else "source_role_units_or_value_need_confirmation",
        )
    selected = max(usable, key=lambda item: item.frequency is not None)
    return VerifiedField(
        status="verified",
        value=selected.value,
        unit="%" if field == "adviser_fee" else selected.currency,
        frequency=selected.frequency,
        uncertainty="approximate"
        if all(item.uncertainty == "approximate" for item in usable)
        else "none",
        evidence=ordered,
        source="extraction_confirmed" if proposed else "note_scan",
    )


_RISK = {
    name.casefold(): name
    for name in (
        "Conservative",
        "Moderately Conservative",
        "Moderate",
        "Moderately Aggressive",
        "Aggressive",
    )
}
_HORIZON = re.compile(
    rf"(?:(?:at least|no less than)\s+)?(?P<number>{_DIGITS}|{_WORD_NUMBER})\+?[\s-]+"
    r"(?P<unit>years?|months?)"
    r"(?:\+|\s+plus|\s+or longer)?",
    re.IGNORECASE,
)
_HORIZON_RANGE = re.compile(
    rf"(?P<low>{_DIGITS}|{_WORD_NUMBER})\s*(?:\bto\b|[-–—])\s*"
    rf"(?P<high>{_DIGITS}|{_WORD_NUMBER})[\s-]+(?P<unit>years?|months?)",
    re.IGNORECASE,
)
_ASSETS = {
    "sa equity": "sa-equity",
    "local equity": "sa-equity",
    "international equity": "intl-equity",
    "global equity": "intl-equity",
    "fixed interest": "fixed-interest",
    "bonds": "bonds",
    "property": "property",
    "cash": "cash",
    "other": "other",
}
_ALLOCATION = re.compile(
    r"(?<![\d.,])([+-]?\d+(?:[.,]\d+)?)\s*%\s*([a-z -]+?)(?=\s*[/,;]|\s+and\s+|$)", re.IGNORECASE
)


def _review_checks(
    extraction: ExtractionResult, notes: str, clauses: list[tuple[int, str]]
) -> tuple[ReviewCheck, ReviewCheck, ReviewCheck]:
    horizon, risk, portfolio = (
        extraction.fields["horizon"],
        extraction.fields["risk"],
        extraction.fields["portfolio_preference"],
    )
    raw = horizon.value if isinstance(horizon.value, str) else ""

    def bucket(amount: Decimal | None, unit: str) -> str | None:
        months = amount if amount is None or unit.casefold().startswith("month") else amount * 12
        return next(
            (
                f"{bound} year{'s' if bound > 1 else ''}+"
                for bound in (5, 3, 1)
                if months is not None and months >= bound * 12
            ),
            None,
        )

    duration = _HORIZON.fullmatch(raw.strip())
    bounds = _HORIZON_RANGE.fullmatch(raw.strip())
    horizon_label = bucket(_number(duration["number"]), duration["unit"]) if duration else None
    if bounds:
        low, high = _number(bounds["low"]), _number(bounds["high"])
        if low is not None and high is not None and low <= high:
            low_label = bucket(low, bounds["unit"])
            if low_label == bucket(high, bounds["unit"]):
                horizon_label = low_label
    if horizon.quote and is_approximate(horizon.quote, raw):
        horizon_label = None
    risk_text = " ".join(re.split(r"[\s\-‐‑]+", str(risk.value).casefold()))
    risk_label = _RISK.get(risk_text.removesuffix(" risk appetite").removesuffix(" risk"))
    preference = str(portfolio.value) if portfolio.value is not None else ""
    allocation = _ALLOCATION.findall(preference)
    weights = [
        _number(number, rate=True) if number[0].isdigit() else None for number, _ in allocation
    ]

    def asset_key(label: str) -> str | None:
        asset = " ".join(label.lower().replace("-", " ").split()).replace("equities", "equity")
        return _ASSETS.get(asset)

    keys = [asset_key(label) for _, label in allocation]
    valid = bool(
        allocation
        and len(allocation) == preference.count("%")
        and None not in keys
        and len(set(keys)) == len(keys)
        and all(weight is not None and 0 <= weight <= 100 for weight in weights)
        and sum(weight for weight in weights if weight is not None) == 100
    )

    def review(
        name: Literal["horizon", "risk", "portfolio_preference"], value: str | None, reason: str
    ) -> ReviewCheck:
        candidate = extraction.fields[name]
        if name in extraction.conflicts:
            return ReviewCheck(status="conflict", reason="conflicting_candidates")
        if value:
            return ReviewCheck(status="verified", value=value, quote=candidate.quote)
        if candidate.value is not None or candidate.uncertainty == "unresolved":
            return ReviewCheck(status="unresolved", quote=candidate.quote, reason=reason)
        if name in {"risk", "horizon"}:
            for item in extraction.review_candidates:
                raw = item.proposed.value
                if (
                    item.proposed.field == name
                    and isinstance(raw, str)
                    and item.reason_code in {"quote_not_found", "quote_missing"}
                    and (span := _anchor(notes, raw, clauses))
                ):
                    return ReviewCheck(
                        status="unresolved", quote=notes[span[0] : span[1]], reason=item.reason_code
                    )
        return ReviewCheck(status="missing")

    return (
        review("horizon", horizon_label, "unsupported_horizon"),
        review("risk", risk_label, "unsupported_risk_category"),
        review(
            "portfolio_preference",
            preference if valid else None,
            "invalid_or_unsupported_allocation"
            if "%" in preference
            else "confirm_model_or_allocation",
        ),
    )


def verify_financials(notes: str, extraction: ExtractionResult) -> FinancialVerification:
    clauses = list(_clauses(notes))
    expressions, excluded, direct = _scan(clauses)
    capital_proposals = [
        (proposal.value, span)
        for proposal in _grounded_proposals(notes, "investment_amount", extraction)
        if proposal.eligible
        and proposal.value is not None
        and (span := _anchor(notes, proposal.quote, clauses)) is not None
    ]
    # Keep denomination evidence independent of the capital amount decision.
    for item in expressions:
        if item.currency and (
            item.role == "investment_amount"
            or (item.role is None and _CAPITAL_CONTEXT.search(item.evidence.quote))
            or (
                item.role is None
                and any(
                    start <= item.evidence.start
                    and item.evidence.end <= end
                    and _proposal_matches("investment_amount", item.evidence, value)
                    for value, (start, end) in capital_proposals
                )
            )
        ):
            direct["currency"].append(item.currency)
    fields = {
        field: _resolve(field, notes, clauses, extraction, expressions, direct[field], excluded)
        for field in _FIELDS
    }
    draw = fields["income_amount"]
    need = fields["income_requirement"]
    currency = fields["currency"]
    if draw.status == "verified" and (
        need.status in ("conflict", "unresolved") or (need.value == "none" and draw.value != "0")
    ):
        fields["income_amount"] = VerifiedField(
            status="unresolved",
            evidence=draw.evidence,
            uncertainty="unresolved",
            reason="income_requirement_needs_confirmation",
        )
    elif (
        draw.status == "verified"
        and currency.status == "verified"
        and draw.unit
        and (draw.unit != currency.value)
    ):
        fields["income_amount"] = VerifiedField(
            status="unresolved",
            evidence=draw.evidence,
            uncertainty="unresolved",
            reason="income_currency_differs_from_investment_currency",
        )
    horizon, risk, portfolio = _review_checks(extraction, notes, clauses)
    mapping = {
        field: item.value
        for field, item in fields.items()
        if item.status == "verified"
        and item.value is not None
        and (
            field != "investment_amount"
            or (item.value.isdecimal() and currency.status == "verified")
        )
        and (
            field != "income_amount"
            or (
                item.value.isdecimal()
                and item.frequency == "monthly"
                and need.status == "verified"
                and need.value == "required"
                and currency.status == "verified"
                and item.unit == currency.value
            )
        )
    }
    return FinancialVerification(
        fields=fields,
        mapping_candidates=mapping,
        excluded_evidence=excluded,
        horizon=horizon,
        risk=risk,
        portfolio=portfolio,
    )
