import json
import socket
from collections.abc import Iterator
from pathlib import Path
from threading import Thread

import pytest
import uvicorn
from playwright.sync_api import Page

from meridian_agent.app import app

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
GENERATOR = "/web/vendor/challenge-generator.html"


@pytest.fixture(scope="module")
def app_url() -> Iterator[str]:
    with socket.create_server(("127.0.0.1", 0)) as listener:
        server = uvicorn.Server(
            uvicorn.Config(app, log_level="warning", timeout_graceful_shutdown=5)
        )
        worker = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{listener.getsockname()[1]}"
        finally:
            server.should_exit = True
            worker.join(timeout=10)


@pytest.fixture
def generator(page: Page, app_url: str) -> Page:
    # The page and frame share an origin. Playwright gives each test fresh browser storage.
    page.goto(f"{app_url}/health")
    page.evaluate(
        """url => {
            const iframe = document.createElement('iframe');
            iframe.id = iframe.name = 'generator';
            iframe.src = url;
            document.body.append(iframe);
        }""",
        GENERATOR,
    )
    page.wait_for_function(
        "typeof document.querySelector('#generator').contentWindow.loadProposal === 'function'"
    )
    return page


def load_proposal(page: Page, proposal: dict) -> str:
    return page.evaluate(
        "data => document.querySelector('#generator').contentWindow.loadProposal(data)",
        proposal,
    )


def saved_proposals(page: Page) -> dict:
    return page.evaluate(
        """() => {
            const saved = JSON.parse(localStorage.getItem('meridian_challenge_proposals_v2') || '[]');
            return Object.fromEntries(saved.map(proposal => [proposal.id, proposal]));
        }"""
    )


def test_load_proposal_applies_model_and_explicit_fields(generator: Page) -> None:
    sample = json.loads((ROOT / "challenge/sample-inputs/04-expected.json").read_text("utf-8"))
    models = generator.evaluate(
        "() => document.querySelector('#generator').contentWindow.challenge.models()"
    )
    assert sample["applyModel"] in {model["id"] for model in models}
    assert saved_proposals(generator) == {}

    draft_id = load_proposal(generator, sample)
    saved = saved_proposals(generator)
    assert set(saved) == {draft_id}
    draft = saved[draft_id]
    assert draft["strategy"]["keyFigures"]["totalInvestment"] == "4500000"
    assert draft["objective"]["investmentHorizon"] == "5 years+"
    assert draft["objective"]["riskProfileCategory"] == "Moderately Aggressive"
    assert draft["strategy"]["allocation"]
    assert draft["fees"]["management"].startswith("0.85")
    assert draft["fees"]["advisorFee"] == "0.75"

    overridden = {**sample, "fees": {"management": "0.42"}}
    second_id = load_proposal(generator, overridden)
    assert second_id != draft_id
    saved = saved_proposals(generator)
    assert set(saved) == {draft_id, second_id}
    assert saved[second_id]["fees"]["management"] == "0.42"
    assert saved[draft_id]["fees"] == draft["fees"]

    frame = generator.frame(name="generator")
    assert frame is not None
    frame.goto(frame.url)
    third_id = load_proposal(generator, {"clientName": "Fictional client"})
    reloaded = saved_proposals(generator)
    assert set(reloaded) == {draft_id, second_id, third_id}
    assert reloaded[draft_id] == saved[draft_id]
    assert reloaded[second_id] == saved[second_id]


def test_unknown_model_does_not_apply_defaults(generator: Page) -> None:
    assert saved_proposals(generator) == {}
    without_model = load_proposal(generator, {"clientName": "Fictional client"})
    unknown_model = load_proposal(
        generator, {"clientName": "Fictional client", "applyModel": "unknown-model"}
    )
    saved = saved_proposals(generator)
    assert set(saved) == {without_model, unknown_model}
    assert saved[unknown_model]["strategy"] == saved[without_model]["strategy"]
    assert saved[unknown_model]["fees"] == saved[without_model]["fees"]
    assert saved[unknown_model]["objective"] == saved[without_model]["objective"]
