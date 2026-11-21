# Decisions (ADR log, append-only)
| ID | Decision | Why | Status |
|----|----------|-----|--------|
| D1 | Companion app; supplied tool unchanged | Lower risk; clearer write-up case | Accepted |
| D2 | Integrate via `window.loadProposal()` once, after approval | Generator creates a new draft per call | Accepted |
| D3 | Python + FastAPI backend; vanilla JS frontend, no build step | Author's strengths; simple | Accepted |
| D4 | Ollama local-first behind provider adapter | Offline; notes stay local | Accepted (model chosen by eval) |
| D5 | faster-whisper local transcription | Free, local | Accepted |
| D6 | Per-field status + evidence quote | Brief: "which parts came from notes?" | Accepted |
| D7 | Code verifies numbers/enums, not the LLM | Prevent fabricated figures | Accepted |
| D8 | Missing -> flag/question, never guess | Financial advice context | Accepted |
| D9 | Open items live in review checklist; marker added to `needs` only if PM approves with gaps | Tool has no open-items field; prevents silent leakage into client text | Accepted |
| D10 | PM approval required; nothing auto-sent | PM is decision-maker | Accepted |
| D11 | Chat = gap-filler on same engine | Covers conversational idea cheaply | Accepted |
| D12 | Eval harness: samples + synthetic edge cases | Choose model by evidence | Accepted |
| D13 | No DB, no Kafka/Airflow/dbt/MLflow, no deployment | Not needed for this problem | Accepted |
| D14 | Private GitHub repo; ask owner about redistributing the HTML | Brief gives no licence terms | Private visibility confirmed on original repo; sharing permission open |
