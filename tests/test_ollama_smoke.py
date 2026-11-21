import os
from pathlib import Path
from time import perf_counter

import pytest
from fastapi.testclient import TestClient

from meridian_agent.app import app

pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(
        os.getenv("RUN_OLLAMA_SMOKE") != "1", reason="Set RUN_OLLAMA_SMOKE=1 for local Ollama"
    ),
]
SAMPLES = Path(__file__).resolve().parents[1] / "challenge" / "sample-inputs"


# Check facts stated in the notes. The example proposal JSON includes model choices,
# defaults and normalized values that are outside the extraction contract.
@pytest.mark.parametrize(
    ("sample", "source_facts", "unresolved"),
    [
        (
            "01-notes-retiree-income.txt",
            {
                "investment_amount": "6.2 million",
                "monthly_income": "28,000",
                "adviser_fee": "0.60%",
            },
            {"client_email"},
        ),
        (
            "02-notes-growth-offshore.txt",
            {
                "investment_amount": "1.2m",
                "adviser_fee": "0.50%",
                "benchmark": "global equity index",
            },
            {"monthly_income", "mandate", "client_email"},
        ),
        (
            "03-notes-sparse.txt",
            {"currency": "rand"},
            {"investment_amount", "monthly_income", "income_requirement", "horizon", "adviser_fee"},
        ),
        (
            "04-voice-note-transcript.txt",
            {
                "investment_amount": "four and a half million",
                "adviser_fee": "zero point seven five",
                "target_return": "CPI plus five",
            },
            {"monthly_income", "client_email"},
        ),
    ],
)
def test_live_extraction(sample: str, source_facts: dict[str, str], unresolved: set[str]) -> None:
    notes = (SAMPLES / sample).read_text(encoding="utf-8")
    started = perf_counter()
    response = TestClient(app).post("/api/extract", json={"notes": notes})
    elapsed = perf_counter() - started
    model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    payload = response.json()
    if response.status_code != 200:
        print(f"{model} sample {sample[:2]}: {elapsed:.1f}s; {payload['detail']['code']}")
        pytest.fail(f"Extraction returned {response.status_code}: {payload['detail']['code']}")

    fields = payload["fields"]
    values = {name for name, field in fields.items() if field["value"] is not None}
    incorrect = [
        name
        for name, expression in source_facts.items()
        if name in values and expression.casefold() not in fields[name]["value"].casefold()
    ]
    print(
        f"{model} sample {sample[:2]}: {elapsed:.1f}s; {len(values)} accepted; "
        f"{payload['withheld_count']} withheld; "
        f"missing checkpoints: {', '.join(sorted(source_facts.keys() - values)) or 'none'}"
    )
    assert values
    assert all(fields[name]["quote"] for name in values)
    assert not (unresolved & values)
    assert not incorrect
    if sample.startswith(("02", "04")) and "income_requirement" in values:
        assert fields["income_requirement"]["value"] == "none"
    if sample.startswith(("01", "04")) and "investment_amount" in values:
        assert fields["investment_amount"]["uncertainty"] == "approximate"
