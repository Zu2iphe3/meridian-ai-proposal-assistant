import json
import socket
from collections.abc import Iterator
from pathlib import Path
from threading import Thread

import pytest
import uvicorn
from playwright.sync_api import Page, expect

from meridian_agent.app import app, get_extraction_provider

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


def test_generator_ignores_capital_under_goal_assessment(generator: Page) -> None:
    draft_id = load_proposal(
        generator, {"goalAssessment": {"keyFigures": {"totalInvestment": "6200000"}}}
    )
    assert saved_proposals(generator)[draft_id]["strategy"]["keyFigures"]["totalInvestment"] == ""


@pytest.fixture
def handoff(generator: Page) -> Page:
    generator.evaluate(
        """async () => {
            const module = await import('/web/proposal-handoff.js');
            const frame = document.querySelector('#generator');
            window.bridge = module.createProposalHandoff(frame);
            window.readModels = () => module.listGeneratorModels(frame);
            window.reviewFromExtraction = module.reviewFromExtraction;
        }"""
    )
    return generator


def extract_offline(page: Page, notes: str, candidates: list[dict]) -> dict:
    class SavedProvider:
        async def generate(self, _policy: str, _notes: str, _schema: dict[str, object]) -> str:
            return json.dumps({"candidates": candidates})

    app.dependency_overrides[get_extraction_provider] = SavedProvider
    try:
        return page.evaluate(
            """async notes => {
                const response = await fetch('/api/extract', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({notes}),
                });
                if (!response.ok) throw new Error('Offline extraction failed: ' + response.status);
                return response.json();
            }""",
            notes,
        )
    finally:
        app.dependency_overrides.pop(get_extraction_provider)


def test_handoff_preserves_reviewed_fields_and_creates_one_draft(handoff: Page) -> None:
    notes = (ROOT / "challenge/sample-inputs/01-notes-retiree-income.txt").read_text("utf-8")
    extraction = extract_offline(
        handoff,
        notes,
        [
            {
                "field": "client_name",
                "value": "Mr George Whitfield",
                "quote": "Client: Mr George Whitfield",
            },
            {"field": "horizon", "value": "15+ years", "quote": "thinks 15+ years"},
        ],
    )
    assert saved_proposals(handoff) == {}
    code = handoff.evaluate(
        """async extraction => {
            const seed = window.reviewFromExtraction(extraction);
            const modelWasUnselected = !('model_id' in seed);
            const automaticFee = seed.adviser_fee;
            const review = {
                ...seed,
                risk: "Moderately Conservative",
                adviser_fee: "0.64",
                model_id: window.readModels().find(({ id }) => id === 'balanced').id,
            };
            window.bridge.setReview(review);
            const blocked = await window.bridge.createDraft().then(() => false, () => true);
            const beforeApproval = JSON.parse(localStorage.getItem('meridian_challenge_proposals_v2') || '[]').length;
            const approval = window.bridge.approve();
            review.adviser_fee = "9.9";
            const first = window.bridge.createDraft(approval);
            const second = window.bridge.createDraft(window.bridge.approve());
            const result = await first;
            return { result, blocked, beforeApproval, modelWasUnselected, automaticFee,
                     duplicateSharesPromise: first === second,
                     sameDraft: result.draftId === (await second).draftId };
        }""",
        extraction,
    )
    assert code["blocked"] and code["beforeApproval"] == 0
    assert code["modelWasUnselected"] and code["automaticFee"] == "0.6"
    assert code["duplicateSharesPromise"] and code["sameDraft"]
    draft_id = code["result"]["draftId"]
    saved = saved_proposals(handoff)
    assert set(saved) == {draft_id}
    draft = saved[draft_id]
    assert draft["status"] == "draft"
    editor = handoff.frame_locator("#generator").get_by_placeholder("Enter client name")
    expect(editor).to_have_value("Mr George Whitfield")
    expect(editor).to_be_editable()
    assert draft["strategy"]["keyFigures"]["totalInvestment"] == "6200000"
    assert draft["strategy"]["keyFigures"]["incomeValue"] == "28000"
    assert not draft["goalAssessment"].get("keyFigures")
    assert draft["strategy"]["currency"] == draft["goalAssessment"]["currency"] == "ZAR"
    assert draft["objective"]["investmentHorizon"] == "5 years+"
    assert draft["objective"]["riskProfileCategory"] == "Moderately Conservative"
    assert draft["goalAssessment"]["riskTolerance"] == "Moderately Conservative"
    assert draft["fees"]["advisorFee"] == "0.64"
    assert draft["fees"]["management"].startswith("0.85")
    assert draft["strategy"]["allocation"]
    assert "model objective and fees" in code["result"]["generatorDefaults"]
    assert "investment amount is approximate" in draft["needs"]


def test_handoff_omits_competing_fee_and_nonmonthly_income(handoff: Page) -> None:
    extraction = extract_offline(
        handoff,
        "Client: Hilltop Trust. The trust will invest GBP 330,000. "
        "They need GBP 1,200 each quarter. Adviser fee 0.35%. Another adviser fee is 0.70%.",
        [],
    )
    verification = extraction["financial_verification"]["fields"]
    assert verification["income_amount"]["frequency"] == "quarterly"
    assert verification["adviser_fee"]["status"] == "conflict"
    result = handoff.evaluate(
        """async extraction => {
            const review = window.reviewFromExtraction(extraction);
            window.bridge.setReview(review);
            const draft = await window.bridge.createDraft(window.bridge.approve());
            return { review, id: draft.draftId };
        }""",
        extraction,
    )
    assert "monthly_income" not in result["review"]
    assert "adviser_fee" not in result["review"]
    draft = saved_proposals(handoff)[result["id"]]
    assert draft["goalAssessment"]["currency"] == draft["strategy"]["currency"] == "GBP"
    assert draft["strategy"]["keyFigures"]["incomeValue"] == ""
    assert draft["fees"]["advisorFee"] == ""


def test_handoff_rejects_unknown_model_invalid_values_and_partial_model_review(
    handoff: Page,
) -> None:
    errors = handoff.evaluate(
        """async () => {
            const failures = [];
            for (const review of [
                {model_id: 'unknown-model', currency: 'ZAR', risk: 'Moderate', horizon: '5 years+'},
                {currency: 'ZAR', investment_amount: {currency: 'ZAR', amount: '1,200'}},
                {model_id: 'balanced', currency: 'ZAR', risk: 'Moderate'},
            ]) {
                window.bridge.setReview(review);
                try {
                    await window.bridge.createDraft(window.bridge.approve());
                    failures.push(null);
                } catch (error) {
                    failures.push(error.message);
                }
            }
            return failures;
        }"""
    )
    assert "no longer available" in errors[0]
    assert all("could not be mapped" in reason for reason in errors[1:])
    assert not saved_proposals(handoff)


def test_handoff_discards_stale_mapping_after_edit(handoff: Page) -> None:
    output = handoff.evaluate(
        """async () => {
            const realFetch = window.fetch;
            let release, requested;
            const barrier = new Promise(resolve => { release = resolve; });
            const started = new Promise(resolve => { requested = resolve; });
            window.fetch = async (...args) => {
                const result = await realFetch(...args);
                requested();
                await barrier;
                return result;
            };
            window.bridge.setReview({client_name: 'First version'});
            const token = window.bridge.approve();
            const old = window.bridge.createDraft(token).then(() => false, () => true);
            await started;
            window.bridge.setReview({client_name: 'Corrected draft'});
            release();
            const staleRejected = await old;
            const oldTokenRejected = await window.bridge.createDraft(token).then(() => false, () => true);
            window.fetch = realFetch;
            const result = await window.bridge.createDraft(window.bridge.approve());
            return {staleRejected, oldTokenRejected, id: result.draftId};
        }"""
    )
    assert output["staleRejected"] and output["oldTokenRejected"]
    saved = saved_proposals(handoff)
    assert list(saved) == [output["id"]]
    assert saved[output["id"]]["clientName"] == "Corrected draft"


def test_vendor_failure_after_persistence_does_not_retry_same_approval(handoff: Page) -> None:
    outcome = handoff.evaluate(
        """async () => {
            const tool = document.querySelector('#generator').contentWindow;
            const load = tool.loadProposal;
            let calls = 0;
            tool.loadProposal = proposal => {
                calls++;
                load(proposal);
                throw new Error('Vendor threw after persistence');
            };
            window.bridge.setReview({client_name: 'Fictional client'});
            const token = window.bridge.approve();
            const result = [];
            for (let i = 0; i < 2; i++) {
                result.push(await window.bridge.createDraft(token).then(() => false, () => true));
            }
            return {calls, result};
        }"""
    )
    assert outcome == {"calls": 1, "result": [True, True]}
    assert len(saved_proposals(handoff)) == 1
