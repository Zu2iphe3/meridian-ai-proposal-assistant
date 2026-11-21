"""HTTP host for extraction and the supplied Meridian generator."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from meridian_agent.extraction import ExtractionError, ExtractionProvider, ExtractionResult, extract
from meridian_agent.ollama import OllamaProvider

app = FastAPI()
MAX_NOTES_LENGTH = 4000


class ExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    notes: str


def get_extraction_provider() -> OllamaProvider:
    try:
        return OllamaProvider.from_environment()
    except ExtractionError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc)}) from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/extract")
async def extract_notes(
    request: ExtractionRequest,
    provider: Annotated[ExtractionProvider, Depends(get_extraction_provider)],
) -> ExtractionResult:
    if not request.notes.strip() or len(request.notes) > MAX_NOTES_LENGTH:
        raise HTTPException(
            422,
            detail={"code": "invalid_notes", "message": "Provide 1 to 4,000 characters of notes."},
        )
    try:
        return await extract(request.notes, provider)
    except ExtractionError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": str(exc)}) from exc


app.mount("/web", StaticFiles(directory=Path(__file__).resolve().parents[2] / "web"), name="web")
