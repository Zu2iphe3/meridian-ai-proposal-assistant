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
| D15 | Match exact financial text first. If a verified quote has one expression with a clear role, copy it verbatim. Keep ambiguous evidence unresolved. | Retain traceable notes when the model reformats a value. Numerical equivalence, conversion and independent validation belong to Issue #5. | Accepted |

| D16 | Use one local extraction call with field, value, quote and optional reason. Derive status in Python. Only eight core fields may be accepted. | Keep source alignment and PM suggestions separate. Exact financial grounding takes priority. Capital reformats require bounded magnitude and currency equivalence before returning the source expression. Supersedes D15 recovery of different figures. | Accepted in PR #16 |
| D17 | Use local Qwen 2.5 3B with a 180-second deadline, overridable through the process environment. | Freeze a single configuration for acceptance checks and retain a manual review path for partial extraction. | Accepted in PR #16 |
| D18 | Scan the full original note and publish an independent financial verification ledger alongside extraction. | Recover omitted facts only with clear source roles and units, retain obsolete statements and exact evidence, and leave conflicts for PM review. PM review and the mapper use the verification ledger for financial values. | Proposed in Issue #5 |
| D19 | Preserve model-led financial proposals and independently reconcile all compatible source expressions before mapping. | Source alignment and numeric verification cannot decide which of two grounded figures applies. Surface the model's grounded proposal and alternatives for PM confirmation when the contract does not establish a single value. | Proposed in Issue #5 |
