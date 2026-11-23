"""Exercise the visible PM workflow with deterministic extraction and the real mapper."""

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from meridian_agent.extraction import extract
from meridian_agent.financial_verification import verify_financials

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "challenge/sample-inputs/01-notes-retiree-income.txt"
EXTRACT = "**/api/extract"
MAP = "**/api/proposals/map"
CLARIFY = "**/api/clarifications"


def fixture_response(notes: str, candidates: list[dict]) -> dict:
    class OfflineProvider:
        async def generate(self, _policy: str, _notes: str, _schema: dict[str, object]) -> str:
            return json.dumps({"candidates": candidates})

    # Playwright's synchronous API already owns an event loop on this thread.
    with ThreadPoolExecutor(max_workers=1) as worker:
        result = worker.submit(lambda: asyncio.run(extract(notes, OfflineProvider()))).result()
    return {
        **result.model_dump(),
        "financial_verification": verify_financials(notes, result).model_dump(),
    }


@pytest.fixture
def sample_response() -> dict:
    return fixture_response(
        SAMPLE.read_text(encoding="utf-8"),
        [
            {
                "field": "client_name",
                "value": "Mr George Whitfield",
                "quote": "Client: Mr George Whitfield",
            },
            {"field": "horizon", "value": "15+ years", "quote": "thinks 15+ years"},
        ],
    )


@pytest.fixture
def assistant(page: Page, app_url: str) -> Page:
    page.route(CLARIFY, lambda route: route.fulfill(json={"questions": []}))
    page.set_viewport_size({"width": 1440, "height": 1080})
    page.goto(app_url)
    expect(page.get_by_role("heading", name="Prepare an investment proposal")).to_be_visible()
    return page


def capture(page: Page, name: str) -> None:
    target = os.getenv("MERIDIAN_BROWSER_CAPTURES")
    if target:
        page.screenshot(path=str(Path(target) / name), full_page=name == "mobile-review.png")


def saved_drafts(page: Page) -> list[dict]:
    return page.evaluate(
        "JSON.parse(localStorage.getItem('meridian_challenge_proposals_v2') || '[]')"
    )


def enter_notes(page: Page, notes: str) -> None:
    page.get_by_role("textbox", name="Meeting notes").fill(notes)
    page.get_by_role("button", name="Extract proposal details").click()


def test_sample_keyboard_review_and_exactly_one_draft(
    assistant: Page, sample_response: dict
) -> None:
    assistant.route(EXTRACT, lambda route: route.fulfill(json=sample_response))
    capture(assistant, "desktop-notes.png")
    expect(assistant.get_by_role("button", name="Load fictional sample")).to_have_count(0)
    notes = assistant.get_by_role("textbox", name="Meeting notes")
    notes.fill(SAMPLE.read_text(encoding="utf-8"))
    expect(notes).to_be_focused()
    submit = assistant.get_by_role("button", name="Extract proposal details")
    notes.press("Tab")
    expect(submit).to_be_focused()
    submit.press("Enter")
    expect(assistant.get_by_role("heading", name="Review & correct")).to_be_focused()
    proposed = assistant.get_by_text("Review proposed ZAR 6,200,000", exact=True)
    proposed.focus()
    proposed.press("Enter")
    assistant.get_by_role("button", name="Confirm investment capital").click()
    expect(assistant.get_by_label("Investment capital", exact=True)).to_have_value("6200000")
    expect(assistant.get_by_label("Monthly income", exact=True)).to_have_value("28000")
    expect(assistant.get_by_label("Proposal currency", exact=True)).to_have_value("ZAR")
    expect(assistant.get_by_label("Investment horizon", exact=True)).to_have_value("5 years+")
    expect(assistant.get_by_label("Annual adviser fee (%)", exact=True)).to_have_value("0.6")
    expect(assistant.get_by_label("Approximate investment capital")).to_be_checked()

    assistant.get_by_label("Risk category", exact=True).select_option("Moderately Conservative")
    assistant.get_by_label("Annual adviser fee (%)", exact=True).fill("0.64")
    assistant.get_by_label("Generator model", exact=True).select_option("balanced")
    assistant.get_by_role("button", name="View evidence for Investment capital").click()
    assistant.get_by_text("Read original notes", exact=True).click()
    expect(assistant.locator("#source-text mark")).to_contain_text("R6.2 million")
    expect(assistant.get_by_text("PM correction", exact=True)).to_have_count(3)
    expect(assistant.get_by_text("Generator default", exact=True)).to_be_visible()
    expect(assistant.locator("#model-defaults")).to_be_visible()
    approve = assistant.get_by_role("button", name="Approve & generate draft")
    confirmation = assistant.get_by_role(
        "checkbox", name="I confirm these reviewed values and any fields left blank."
    )
    expect(approve).to_be_disabled()
    assert saved_drafts(assistant) == []
    confirmation.focus()
    confirmation.press("Space")
    expect(approve).to_be_enabled()
    assistant.evaluate("window.scrollTo(0, 240)")
    capture(assistant, "desktop-review.png")
    assistant.set_viewport_size({"width": 390, "height": 844})
    assistant.evaluate("window.scrollTo(0, 0)")
    capture(assistant, "mobile-review.png")
    assistant.set_viewport_size({"width": 1440, "height": 1080})
    approve.evaluate("button => { button.click(); button.click(); }")
    expect(assistant.get_by_text("Approved draft created.", exact=True)).to_be_visible()
    editor = assistant.frame_locator("#proposal-generator").get_by_placeholder("Enter client name")
    expect(editor).to_have_value("Mr George Whitfield")
    expect(editor).to_be_editable()
    drafts = saved_drafts(assistant)
    assert len(drafts) == 1
    assert drafts[0]["strategy"]["keyFigures"]["totalInvestment"] == "6200000"
    assert drafts[0]["strategy"]["keyFigures"]["incomeValue"] == "28000"
    assert drafts[0]["objective"]["riskProfileCategory"] == "Moderately Conservative"
    assert drafts[0]["fees"]["advisorFee"] == "0.64"
    expect(approve).to_be_disabled()
    capture(assistant, "approved-draft.png")


def test_provider_failure_preserves_notes_and_pm_edits_on_retry(
    assistant: Page, sample_response: dict
) -> None:
    mode = {"fail": False}

    def response(route) -> None:
        if mode["fail"]:
            route.fulfill(
                status=503, json={"detail": {"message": "Start the local Ollama service."}}
            )
        else:
            route.fulfill(json=sample_response)

    assistant.route(EXTRACT, response)
    assistant.get_by_role("button", name="Extract proposal details").click()
    expect(assistant.locator("#extraction-error")).to_contain_text("Enter meeting notes")
    notes = SAMPLE.read_text(encoding="utf-8")
    enter_notes(assistant, notes)
    expect(assistant.get_by_label("Annual adviser fee (%)", exact=True)).to_have_value("0.6")
    assistant.get_by_label("Client name", exact=True).fill("PM corrected client")
    assistant.get_by_label("Annual adviser fee (%)", exact=True).fill("")
    mode["fail"] = True
    assistant.get_by_role("button", name="Extract proposal details").click()
    expect(assistant.locator("#extraction-error")).to_contain_text("Start the local Ollama service")
    expect(assistant.get_by_role("textbox", name="Meeting notes")).to_have_value(notes)
    expect(assistant.get_by_label("Client name", exact=True)).to_have_value("PM corrected client")
    mode["fail"] = False
    assistant.get_by_role("button", name="Extract proposal details").click()
    expect(assistant.locator("#extraction-status")).to_have_text("Review ready")
    expect(assistant.get_by_label("Client name", exact=True)).to_have_value("PM corrected client")
    expect(assistant.get_by_label("Annual adviser fee (%)", exact=True)).to_have_value("")


def test_late_extraction_cannot_replace_current_review(
    assistant: Page, sample_response: dict
) -> None:
    # Ignore the abort signal deliberately to exercise the request-number guard.
    assistant.evaluate(
        """() => {
            const fetchLocal = window.fetch.bind(window);
            window.pendingExtraction = [];
            window.fetch = (url, options) => url === '/api/extract'
                ? new Promise(resolve => window.pendingExtraction.push(
                    result => resolve(new Response(JSON.stringify(result)))))
                : fetchLocal(url, options);
        }"""
    )
    enter_notes(assistant, "First fictional note")
    expect(assistant.locator("#extraction-status")).to_contain_text("Extracting")
    enter_notes(assistant, "Second fictional note")
    expect(assistant.locator("#extraction-status")).to_contain_text("Extracting")
    assistant.wait_for_function("window.pendingExtraction.length === 2")
    assistant.evaluate("data => window.pendingExtraction[1](data)", sample_response)
    expect(assistant.get_by_label("Client name", exact=True)).to_have_value("Mr George Whitfield")
    assistant.get_by_label("Client name", exact=True).fill("Reviewed by PM")
    sample_response["fields"]["client_name"]["value"] = "Stale name"
    assistant.evaluate(
        """async data => {
            window.pendingExtraction[0](data);
            await new Promise(resolve => setTimeout(resolve, 0));
        }""",
        sample_response,
    )
    expect(assistant.get_by_label("Client name", exact=True)).to_have_value("Reviewed by PM")
    expect(assistant.locator("#stale-review")).to_be_hidden()


def test_mobile_provisional_name_and_competing_fee_evidence(assistant: Page) -> None:
    assistant.set_viewport_size({"width": 390, "height": 844})
    notes = (
        "Meeting with Finch Talbot. The client will invest GBP 420,000. "
        "They need GBP 1,300 each quarter. Adviser fee 0.35%. Another adviser fee is 0.70%. "
        "Quoted text: <img src=x onerror=window.injected=true>."
    )
    payload = fixture_response(
        notes,
        [
            {
                "field": "client_name",
                "value": "Finch Talbot",
                "quote": "The client will invest GBP 420,000.",
            },
        ],
    )
    # Include source text that looks like HTML and prove the review renders it literally.
    payload["financial_verification"]["fields"]["adviser_fee"]["evidence"].append(
        {"quote": "<img src=x onerror=window.injected=true>", "disposition": "current"}
    )
    assistant.route(EXTRACT, lambda route: route.fulfill(json=payload))
    enter_notes(assistant, notes)
    expect(assistant.get_by_label("Client name", exact=True)).to_have_value("")
    expect(assistant.get_by_label("Monthly income", exact=True)).to_have_value("")
    expect(assistant.get_by_label("Annual adviser fee (%)", exact=True)).to_have_value("")
    expect(assistant.get_by_role("button", name="Use suggested client name")).to_contain_text(
        "Finch Talbot"
    )
    assistant.get_by_role("button", name="Use suggested client name").click()
    expect(assistant.get_by_label("Client name", exact=True)).to_have_value("Finch Talbot")
    assistant.get_by_role("button", name="View evidence for Annual adviser fee").click()
    expect(assistant.locator("#evidence-quotes")).to_contain_text("0.35%")
    expect(assistant.locator("#evidence-quotes")).to_contain_text("0.70%")
    expect(assistant.locator("#evidence-quotes")).to_contain_text("<img src=x")
    assert assistant.locator("#evidence-quotes img").count() == 0
    assert assistant.evaluate("document.documentElement.scrollWidth === window.innerWidth")
    assert saved_drafts(assistant) == []


@pytest.mark.parametrize(
    ("income_note", "badge", "expected", "suggestion"),
    [
        (
            "She requires R12,000 in income.",
            "Income suggestion · confirm",
            "",
            "ZAR 12000 (frequency unconfirmed)",
        ),
        ("They require ZAR 12,000 each month.", "Stated in notes", "12000", None),
        ("She requires R12,000 in monthly income.", "Stated in notes", "12000", None),
        (
            "They require ZAR 12,000 each quarter.",
            "Non-monthly · review",
            "",
            "ZAR 12000 (quarterly)",
        ),
        (
            "If the property sells, they will need ZAR 12,000 each month.",
            "Needs confirmation",
            "",
            None,
        ),
        ("They discussed investment objectives.", "Missing", "", None),
    ],
    ids=[
        "frequency-unconfirmed",
        "monthly",
        "cadence-after-label",
        "quarterly",
        "conditional",
        "missing",
    ],
)
def test_income_evidence_preserves_monthly_eligibility(
    assistant: Page, income_note: str, badge: str, expected: str, suggestion: str | None
) -> None:
    notes = "The client will invest ZAR 480,000. " + income_note
    payload = fixture_response(notes, [])
    assistant.route(EXTRACT, lambda route: route.fulfill(json=payload))
    enter_notes(assistant, notes)

    income = assistant.get_by_label("Monthly income", exact=True)
    expect(income).to_have_value(expected)
    income_badge = assistant.locator(".field").filter(has=income).locator(".badge")
    expect(income_badge).to_have_text(badge)
    assistant.get_by_role("button", name="View evidence for Monthly income").click()
    evidence = assistant.locator("#evidence-quotes")
    if "12,000" in income_note:
        expect(evidence).to_contain_text(income_note.rstrip("."))
    else:
        expect(evidence).to_contain_text("No verified source quote")
    if suggestion:
        expect(evidence).to_contain_text(f"Unconfirmed suggestion: {suggestion}")
    else:
        expect(evidence).not_to_contain_text("Unconfirmed suggestion")

    confirm = assistant.get_by_label("I confirm these reviewed values and any fields left blank.")
    approve = assistant.get_by_role("button", name="Approve & generate draft")
    if suggestion and "frequency unconfirmed" in suggestion:
        confirm.check()
        income.fill("12000")
        expect(approve).to_be_disabled()
        expect(assistant.get_by_text("PM correction", exact=True)).to_be_visible()
        expected = "12000"

    confirm.check()
    approve.click()
    expect(assistant.get_by_text("Approved draft created.", exact=True)).to_be_visible()
    [draft] = saved_drafts(assistant)
    assert draft["strategy"]["keyFigures"]["incomeValue"] == expected


def test_invalid_edit_revokes_approval_and_handoff_failure_keeps_review(
    assistant: Page, sample_response: dict
) -> None:
    assistant.route(EXTRACT, lambda route: route.fulfill(json=sample_response))
    enter_notes(assistant, SAMPLE.read_text(encoding="utf-8"))
    confirmation = assistant.get_by_role(
        "checkbox", name="I confirm these reviewed values and any fields left blank."
    )
    approve = assistant.get_by_role("button", name="Approve & generate draft")
    confirmation.check()
    expect(approve).to_be_enabled()
    amount = assistant.get_by_label("Investment capital", exact=True)
    amount.fill("xx")
    expect(confirmation).not_to_be_checked()
    expect(approve).to_be_disabled()
    amount.fill("6290000")
    confirmation.check()
    assistant.route(MAP, lambda route: route.fulfill(status=503, json={"detail": "Try again"}))
    approve.click()
    expect(assistant.locator("#handoff-error")).to_contain_text("reviewed values are still here")
    expect(amount).to_have_value("6290000")
    assert saved_drafts(assistant) == []
    assistant.unroute(MAP)
    approve.click()
    expect(assistant.get_by_text("Approved draft created.", exact=True)).to_be_visible()
    assert len(saved_drafts(assistant)) == 1
    assert saved_drafts(assistant)[0]["strategy"]["keyFigures"]["totalInvestment"] == "6290000"


@pytest.mark.parametrize(
    ("defer_capital", "fee_question"), [(False, True), (True, False)], ids=["answer", "defer"]
)
def test_clarification_answers_use_review_and_deferral_stays_out_of_draft(
    assistant: Page, defer_capital: bool, fee_question: bool
) -> None:
    notes = (
        "Client: Olivia Bennett. The client will invest about GBP 300,000. "
        "Olivia must confirm the final amount. Adviser fee: 0.40%. Adviser fee: 0.70%. "
        "If the property sells, they require GBP 1,500 each quarter."
    )
    payload = fixture_response(notes, [])
    # Live extraction can supply one broad quote in addition to the individual fee passages.
    payload["financial_verification"]["fields"]["adviser_fee"]["evidence"].append(
        {"quote": "Adviser fee: 0.40%. Adviser fee: 0.70%.", "disposition": "current"}
    )
    assistant.route(EXTRACT, lambda route: route.fulfill(json=payload))
    calls = []

    def evidence(quote):
        return {"id": quote, "quote": quote}

    def clarify(route):
        calls.append(route.request.post_data_json)
        route.fulfill(
            json={
                "questions": [
                    {
                        "field": "investment_amount",
                        "question": "Is the investment estimate final?",
                        "pending_decision": True,
                        "evidence": [evidence("Olivia must confirm the final amount.")],
                    },
                ]
                + (
                    [
                        {
                            "field": "adviser_fee",
                            "question": "Which fee was agreed?",
                            "pending_decision": False,
                            "evidence": [
                                evidence("Adviser fee: 0.40%."),
                                evidence("Adviser fee: 0.70%."),
                            ],
                        }
                    ]
                    if fee_question
                    else []
                )
            }
        )

    assistant.route(CLARIFY, clarify)
    enter_notes(assistant, notes)
    amount = assistant.get_by_label("Investment capital", exact=True)
    fee = assistant.get_by_label("Annual adviser fee (%)", exact=True)
    capital_row = assistant.locator(".field").filter(has=amount)
    fee_row = assistant.locator(".field").filter(has=fee)
    expect(assistant.get_by_label("Monthly income", exact=True)).to_have_value("")
    expect(assistant.locator("#clarifications-status")).to_be_hidden()
    expect(fee).to_have_value("")
    expect(fee_row.get_by_text("Conflict", exact=True)).to_be_visible()
    if fee_question:
        expect(fee_row.get_by_text("Which fee was agreed?", exact=True)).to_be_visible()
    else:
        expect(fee_row.locator(".field-clarification")).to_be_hidden()
    expect(amount).to_have_value("")
    expect(capital_row.get_by_text("Decision pending", exact=True)).to_be_visible()
    proposed = capital_row.get_by_text("Review proposed GBP 300,000", exact=True)
    expect(proposed).to_be_visible()
    expect(capital_row.get_by_text("Is the investment estimate final?", exact=True)).to_be_hidden()
    expect(assistant.get_by_role("button", name="Confirm investment capital")).to_be_hidden()
    proposed.click()
    expect(capital_row.get_by_text("Is the investment estimate final?", exact=True)).to_be_visible()
    expect(
        capital_row.get_by_text("This amount is approximate and unconfirmed.", exact=False)
    ).to_be_visible()
    expect(fee_row.locator("blockquote")).to_have_count(0)
    assistant.get_by_role("button", name="View evidence for Annual adviser fee").click()
    expect(assistant.locator("#evidence-quotes")).to_contain_text("0.40%")
    expect(assistant.locator("#evidence-quotes")).to_contain_text("0.70%")
    expect(assistant.locator("#evidence-quotes blockquote")).to_have_count(1)
    if defer_capital:
        assistant.get_by_role("button", name="Defer investment capital").click()
        expect(assistant.get_by_text("Deferred · stays in review")).to_be_visible()
    else:
        assistant.get_by_role("button", name="Confirm investment capital").click()
        expect(amount).to_be_focused()
    expected_capital = "" if defer_capital else "300000"
    expect(amount).to_have_value(expected_capital)

    fee.fill("125")
    approve = assistant.get_by_role("button", name="Approve & generate draft")
    expect(approve).to_be_disabled()
    fee.fill("0.55")
    assert len(calls) == 1
    expect(fee_row.get_by_text("PM correction", exact=True)).to_be_visible()
    expect(fee_row.get_by_text("Which fee was agreed?", exact=True)).to_be_hidden()
    with assistant.expect_response(lambda response: response.url.endswith("/api/extract")):
        assistant.get_by_role("button", name="Extract proposal details").click()
    expect(assistant.locator("#extraction-status")).to_have_text("Review ready")
    expect(amount).to_have_value(expected_capital)
    expect(fee).to_have_value("0.55")
    assert len(calls) == 1
    assert saved_drafts(assistant) == []
    assistant.get_by_label("I confirm these reviewed values and any fields left blank.").check()
    approve.evaluate("button => { button.click(); button.click(); }")
    expect(assistant.get_by_text("Approved draft created.", exact=True)).to_be_visible()
    [draft] = saved_drafts(assistant)
    assert draft["fees"]["advisorFee"] == "0.55"
    assert draft["strategy"]["keyFigures"]["totalInvestment"] == expected_capital
    assert draft["strategy"]["keyFigures"]["incomeValue"] == ""


def test_clarification_timeout_keeps_manual_review_and_pm_edits(
    assistant: Page, sample_response: dict
) -> None:
    assistant.route(EXTRACT, lambda route: route.fulfill(json=sample_response))
    assistant.route("**/api/clarifications", lambda route: route.fulfill(status=504))
    notes = SAMPLE.read_text(encoding="utf-8")
    enter_notes(assistant, notes)
    fee = assistant.get_by_label("Annual adviser fee (%)", exact=True)
    fee.fill("0.55")
    expect(assistant.get_by_text("AI questions are unavailable.", exact=False)).to_be_visible()
    expect(fee).to_have_value("0.55")
    expect(assistant.get_by_role("textbox", name="Meeting notes")).to_have_value(notes)
    assistant.get_by_label("I confirm these reviewed values and any fields left blank.").check()
    expect(assistant.get_by_role("button", name="Approve & generate draft")).to_be_enabled()


def delay_clarifications(page: Page) -> None:
    page.evaluate(
        """() => {
            const fetchLocal = window.fetch.bind(window);
            window.finishClarifications = [];
            window.fetch = (url, options) => url === '/api/clarifications'
              ? new Promise(resolve => window.finishClarifications.push(
                  data => resolve(new Response(JSON.stringify(data)))))
              : fetchLocal(url, options);
        }"""
    )


def test_background_questions_preserve_pm_edits_and_do_not_block_approval(
    assistant: Page, sample_response: dict
) -> None:
    assistant.route(EXTRACT, lambda route: route.fulfill(json=sample_response))
    delay_clarifications(assistant)
    enter_notes(assistant, SAMPLE.read_text(encoding="utf-8"))
    assistant.wait_for_function("window.finishClarifications.length === 1")
    amount = assistant.get_by_label("Investment capital", exact=True)
    expect(amount).to_have_value("")
    assistant.get_by_text("Review proposed ZAR 6,200,000", exact=True).click()
    fee = assistant.get_by_label("Annual adviser fee (%)", exact=True)
    fee.fill("0.55")
    assistant.get_by_label("I confirm these reviewed values and any fields left blank.").check()
    assistant.get_by_role("button", name="Approve & generate draft").click()
    expect(assistant.get_by_text("Approved draft created.", exact=True)).to_be_visible()
    [draft] = saved_drafts(assistant)
    assert draft["strategy"]["keyFigures"]["totalInvestment"] == ""
    assert draft["fees"]["advisorFee"] == "0.55"
    assistant.evaluate(
        """() => window.finishClarifications[0]({questions: [
          {field: 'adviser_fee', question: 'Which fee was confirmed?', evidence: []},
          {field: 'investment_amount', question: 'Is the capital confirmed?', evidence: []}
        ]})"""
    )
    expect(assistant.get_by_text("Is the capital confirmed?", exact=True)).to_be_visible()
    expect(assistant.get_by_text("Which fee was confirmed?", exact=True)).to_have_count(0)
    expect(fee).to_have_value("0.55")
    assert len(saved_drafts(assistant)) == 1


def test_stale_clarification_cannot_mutate_new_review(
    assistant: Page, sample_response: dict
) -> None:
    assistant.route(EXTRACT, lambda route: route.fulfill(json=sample_response))
    delay_clarifications(assistant)
    notes = SAMPLE.read_text(encoding="utf-8")
    enter_notes(assistant, notes)
    assistant.wait_for_function("window.finishClarifications.length === 1")
    enter_notes(assistant, notes + " Another fictional fact.")
    assistant.wait_for_function("window.finishClarifications.length === 2")
    assistant.get_by_label("Investment capital", exact=True).fill("6200000")
    assistant.evaluate(
        """() => {
            window.finishClarifications[0]({questions: [{field: 'horizon',
                question: 'What old horizon was confirmed?', evidence: []}]});
            window.finishClarifications[1]({questions: []});
        }"""
    )
    expect(assistant.locator("#clarifications-status")).to_be_hidden()
    expect(assistant.get_by_label("Investment capital", exact=True)).to_have_value("6200000")
    expect(assistant.get_by_text("What old horizon was confirmed?")).to_have_count(0)


def test_reconstructed_emma_missing_fields_remain_editable(assistant: Page) -> None:
    notes = "Client: Emma Collins. First planning meeting. Investment budget and timing are open."
    payload = fixture_response(notes, [])
    assistant.route(EXTRACT, lambda route: route.fulfill(json=payload))
    assistant.set_viewport_size({"width": 390, "height": 844})
    with assistant.expect_response(lambda response: response.url.endswith("/api/clarifications")):
        enter_notes(assistant, notes)
    for label in ("Investment capital", "Monthly income", "Investment horizon"):
        control = assistant.get_by_label(label, exact=True)
        expect(control).to_have_value("")
        expect(control).to_be_editable()
        row = assistant.locator(".field").filter(has=control)
        expect(row.get_by_text("Missing", exact=True)).to_be_visible()
        expect(row.locator(".field-clarification")).to_be_hidden()
    assert assistant.locator(".field-clarification:visible").count() == 0
    assert assistant.evaluate("document.documentElement.scrollWidth === window.innerWidth")
