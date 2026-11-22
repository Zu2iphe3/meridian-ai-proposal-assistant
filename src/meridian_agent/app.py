"""HTTP host for extraction and the supplied Meridian generator."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from meridian_agent.clarifications import (
    ClarificationRequest,
    ClarificationResult,
    clarification_targets,
    generate_clarifications,
)
from meridian_agent.extraction import ExtractionError, ExtractionProvider, ExtractionResult, extract
from meridian_agent.financial_verification import FinancialVerification, verify_financials
from meridian_agent.ollama import OllamaProvider
from meridian_agent.proposal_mapping import ApprovedProposal, MappedProposal, map_reviewed

app = FastAPI()
MAX_NOTES_LENGTH = 4000
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    notes: str


class VerifiedExtractionResult(ExtractionResult):
    financial_verification: FinancialVerification


def get_extraction_provider() -> OllamaProvider:
    try:
        return OllamaProvider.from_environment()
    except ExtractionError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc)}) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def assistant() -> RedirectResponse:
    return RedirectResponse("/web/index.html")


@app.get("/api/examples/meeting-notes", response_class=PlainTextResponse)
def example_notes() -> str:
    # Serve the supplied fictional example only, without exposing the challenge directory.
    sample = PROJECT_ROOT / "challenge" / "sample-inputs" / "01-notes-retiree-income.txt"
    return sample.read_text(encoding="utf-8")


@app.post("/api/extract")
async def extract_notes(
    request: ExtractionRequest,
    provider: Annotated[ExtractionProvider, Depends(get_extraction_provider)],
) -> VerifiedExtractionResult:
    if not request.notes.strip() or len(request.notes) > MAX_NOTES_LENGTH:
        raise HTTPException(
            422,
            detail={"code": "invalid_notes", "message": "Provide 1 to 4,000 characters of notes."},
        )
    try:
        result = await extract(request.notes, provider)
        return VerifiedExtractionResult(
            **result.model_dump(),
            financial_verification=verify_financials(request.notes, result),
        )
    except ExtractionError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc)}) from exc


@app.post("/api/clarifications")
async def clarify(request: ClarificationRequest) -> ClarificationResult:
    targets = clarification_targets(request)
    if not targets:
        return ClarificationResult(questions=[])
    try:
        return await generate_clarifications(targets, get_extraction_provider())
    except ExtractionError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc)}) from exc


@app.post("/api/proposals/map", response_model_exclude_none=True)
def map_proposal(request: ApprovedProposal) -> MappedProposal:
    return map_reviewed(request.review)


app.mount("/web", StaticFiles(directory=PROJECT_ROOT / "web"), name="web")
