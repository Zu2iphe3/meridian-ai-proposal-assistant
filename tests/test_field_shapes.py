import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from meridian_agent.extraction import extract
from meridian_agent.ollama import OllamaProvider


def run_awaitable(coroutine):
    # Playwright may own the main thread event loop during a combined test run.
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(coroutine)).result()


class Provider:
    def __init__(self, field, value, quote):
        self.raw = json.dumps({"candidates": [{"field": field, "value": value, "quote": quote}]})

    async def generate(self, policy, notes, schema):
        return self.raw


@pytest.mark.parametrize(
    "field,value,quote,code,disposition",
    [
        (
            "client_name",
            "R900,000 or R1.3 million",
            "Considering either R900,000 or R1.3 million.",
            "money_expression_as_client_name",
            "rejected",
        ),
        (
            "portfolio_preference",
            "CPI plus three",
            "Target return: CPI plus three.",
            "financial_expression_as_portfolio",
            "rejected",
        ),
        (
            "portfolio_preference",
            "Balanced-ish",
            "Balanced-ish feel",
            "provisional_requires_pm_confirmation",
            "provisional",
        ),
        (
            "portfolio_preference",
            "Portfolio and adviser charges",
            "Portfolio and adviser charges still to be confirmed.",
            "provisional_requires_pm_confirmation",
            "provisional",
        ),
        (
            "client_name",
            "two million rand",
            "Capital: two million rand.",
            "money_expression_as_client_name",
            "rejected",
        ),
        (
            "portfolio_preference",
            "USD 82,000",
            "Investment: USD 82,000.",
            "financial_expression_as_portfolio",
            "rejected",
        ),
        (
            "portfolio_preference",
            "0.60%",
            "Adviser fee 0.60%.",
            "financial_expression_as_portfolio",
            "rejected",
        ),
        (
            "portfolio_preference",
            "5%",
            "Target return: 5%.",
            "financial_expression_as_portfolio",
            "rejected",
        ),
    ],
)
def test_incompatible_or_provisional_candidates_remain_reviewable(
    field, value, quote, code, disposition
):
    result = run_awaitable(extract(quote, Provider(field, value, quote)))
    assert result.fields[field].value is None
    assert result.fields[field].uncertainty == (
        "unresolved" if disposition == "provisional" else "none"
    )
    assert result.withheld_count == 1
    review = result.review_candidates[0]
    assert review.proposed.value == value
    assert review.proposed.quote == quote
    assert review.verified_quote in quote
    assert review.reason_code == code
    assert review.disposition == disposition


@pytest.mark.parametrize(
    "field,value,quote",
    [
        ("client_name", "Studio 54 Trust", "Client: Studio 54 Trust."),
        ("client_name", "R2D2 Holdings", "Client: R2D2 Holdings."),
        ("client_name", "2024 Family Trust", "Client: 2024 Family Trust."),
        ("client_name", "Rand Family Trust", "Client: Rand Family Trust."),
        ("portfolio_preference", "60% equities / 40% bonds", "Use 60% equities / 40% bonds."),
        (
            "portfolio_preference",
            "60% equity / 40% bonds",
            "Use 60% equity / 40% bonds; adviser fee 0.7%.",
        ),
        ("portfolio_preference", "100% global equities", "Preference: 100% global equities."),
        ("portfolio_preference", "Balanced 60", "Choose Balanced 60."),
        ("portfolio_preference", "low-fee bond portfolio", "Choose the low-fee bond portfolio."),
        (
            "portfolio_preference",
            "British equity portfolio",
            "Choose the British equity portfolio.",
        ),
    ],
)
def test_digits_and_allocations_are_not_blanket_rejected(field, value, quote):
    result = run_awaitable(extract(quote, Provider(field, value, quote)))
    assert result.fields[field].value == value
    assert result.review_candidates == []


@pytest.mark.parametrize(
    "field,value",
    [("portfolio_preference", "balanced"), ("risk", "moderate"), ("horizon", "ten years")],
)
def test_shortened_quote_cannot_hide_maybe(field, value):
    notes = f"Maybe {value}; discuss before approval."
    result = run_awaitable(extract(notes, Provider(field, value, value)))
    assert result.fields[field].value is None
    review = result.review_candidates[0]
    assert review.disposition == "provisional"
    assert review.verified_quote == f"Maybe {value}"


def test_unverified_evidence_is_retained_but_not_marked_verified():
    result = run_awaitable(
        extract("Nothing agreed.", Provider("client_name", "Jane", "Client: Jane."))
    )
    assert result.fields["client_name"].value is None
    assert result.review_candidates[0].proposed.quote == "Client: Jane."
    assert result.review_candidates[0].verified_quote is None
    assert result.review_candidates[0].reason_code == "quote_not_found"


def test_default_model_and_deadline_allow_explicit_override(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_TIMEOUT_SECONDS", raising=False)
    assert OllamaProvider.from_environment()._model == "qwen2.5:3b"
    assert OllamaProvider.from_environment()._timeout == 180
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "45")
    assert OllamaProvider.from_environment()._model == "llama3.2:3b"
    assert OllamaProvider.from_environment()._timeout == 45
