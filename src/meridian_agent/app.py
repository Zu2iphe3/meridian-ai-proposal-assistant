"""HTTP host for the supplied Meridian generator."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.mount("/web", StaticFiles(directory=Path(__file__).resolve().parents[2] / "web"), name="web")
