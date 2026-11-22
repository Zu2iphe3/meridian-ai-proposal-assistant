# Meridian AI Proposal Assistant

A local-first companion that turns fictional portfolio-manager notes into an evidence-backed draft for review in the supplied Meridian Proposal Generator.

The assistant extracts and verifies information from typed notes, then lets the portfolio manager review and correct it before creating an editable draft in the original generator.

The `challenge/` folder contains supplied reference material from the updated assessment pack, including the brief, schema, and fictional sample inputs and outputs.

Use Python 3.12 in a virtual environment. From the repository root:

```text
python -m pip install -e ".[dev]"
python -m uvicorn meridian_agent.app:app
```

Start Ollama, then open [the assistant workspace](http://127.0.0.1:8000/). Load the fictional sample or enter meeting notes, review the values and evidence, then confirm and approve the draft.

## Extract candidates locally

Start Ollama on loopback and use an installed local model. Defaults are `OLLAMA_HOST=http://127.0.0.1:11434`, `OLLAMA_MODEL=qwen2.5:3b` and `OLLAMA_TIMEOUT_SECONDS=180`. Set these environment variables before starting FastAPI to change them. Keep Ollama in local-only mode (`OLLAMA_NO_CLOUD=1`) when using meeting notes.

See `.env.example` for the process environment settings. Extraction uses one
local inference request. The model proposes fields and supporting quotes. Python
derives source status, checks money and conflicts, and accepts only the eight
core fields. Other proposals are suggestions for the portfolio manager.

Example using fictional notes in PowerShell:

```powershell
$body = @{ notes = (Get-Content challenge/sample-inputs/01-notes-retiree-income.txt -Raw) } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/extract -ContentType 'application/json; charset=utf-8' -Body $body
```

The endpoint accepts up to 4,000 characters. It returns core fields, grounded
conflicts, gap reasons and review candidates. Review candidates keep their
proposed text, verified quote when available and disposition. Missing values
stay blank for PM review. Provisional and conflicting information stays out of
the accepted values. Financial verification and proposal mapping are subsequent
steps.

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
