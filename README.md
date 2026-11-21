# Meridian AI Proposal Assistant

A local-first companion that turns fictional portfolio-manager notes into an evidence-backed draft for review in the supplied Meridian Proposal Generator.

The app serves the original generator and extracts evidence-backed candidates from typed notes. Financial validation, adviser review, proposal mapping and transcription are later milestones.

The `challenge/` folder contains supplied reference material from the updated assessment pack, including the brief, schema, and fictional sample inputs and outputs.

Use Python 3.12 in a virtual environment. From the repository root:

```text
python -m pip install -e ".[dev]"
python -m uvicorn meridian_agent.app:app
```

Open the generator at `http://127.0.0.1:8000/web/vendor/challenge-generator.html`.

## Extract candidates locally

Start Ollama on loopback and use an installed local model. Defaults are `OLLAMA_HOST=http://127.0.0.1:11434`, `OLLAMA_MODEL=llama3.2:3b` and `OLLAMA_TIMEOUT_SECONDS=90`. Set these environment variables before starting FastAPI to change them. Keep Ollama in local-only mode (`OLLAMA_NO_CLOUD=1`) when using meeting notes.

Example using fictional notes in PowerShell:

```powershell
$body = @{ notes = (Get-Content challenge/sample-inputs/01-notes-retiree-income.txt -Raw) } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/extract -ContentType 'application/json; charset=utf-8' -Body $body
```

The endpoint accepts up to 4,000 characters. It returns source-backed candidate fields, conflicts, gap reasons, and a withheld-candidate count. A rejected field leaves a gap while other supported fields can still be reviewed. Source matching verifies traceability. Financial meaning and proposal mapping are separate steps.

## Checks

```text
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -m "not browser and not llm"
python -m playwright install chromium
python -m pytest -m browser
```

To run the four fictional samples through Ollama, set `RUN_OLLAMA_SMOKE=1` and run `python -m pytest -m llm -q -s`. This check is opt-in and excluded from CI.

See `docs/architecture.md`, `docs/integration.md` and `docs/bok/progress.md`.
