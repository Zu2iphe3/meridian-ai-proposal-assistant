# Meridian AI Proposal Assistant

A local-first companion that turns fictional portfolio-manager notes into an evidence-backed draft for review in the supplied Meridian Proposal Generator.

The foundation serves the original generator and exposes a health endpoint. Extraction, review and transcription are planned milestones.

The `challenge/` folder contains supplied reference material from the updated assessment pack, including the brief, schema, and fictional sample inputs and outputs.

Use Python 3.12 in a virtual environment. From the repository root:

```text
python -m pip install -e ".[dev]"
python -m uvicorn meridian_agent.app:app
```

Open the generator at `http://127.0.0.1:8000/web/vendor/challenge-generator.html`.

```text
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -m "not browser and not llm"
```

See `docs/architecture.md`, `docs/integration.md` and `docs/bok/progress.md`.
