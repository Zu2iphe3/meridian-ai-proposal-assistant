# Architecture

```
Adviser workspace (HTML/CSS/vanilla JS)  notes · recording · questions · review · approval
        |
FastAPI backend                          request handling · provider · transcription · orchestration
        |
Extraction engine                        Pydantic: value + evidence quote + status per field
        |
Trust + mapping layer                    numeric verification · enum/business rules · provenance · proposal JSON
        |
Meridian generator (unchanged, same-origin iframe)   window.loadProposal() · edit · preview · export
```

## Flow
1. Input: pasted text, uploaded audio, or mic recording. Audio -> faster-whisper -> text.
2. Extract: LLM returns facts with evidence quotes (extraction JSON, not proposal JSON).
3. Verify (code): amounts re-derived from the quote, enums bucketed, contradictions found,
   allocation sums checked, model id checked against `window.challenge.models()`.
4. Provenance: each field STATED / INFERRED / MODEL_DEFAULT / MISSING. MODEL_DEFAULT is found
   by diffing what the tool fills for the bare model against what the notes supplied.
5. Gaps: missing/ambiguous items become targeted questions; PM answers become STATED (source: PM).
6. Review: notes with highlighted evidence | field table with status chips | PM edits.
7. Approve: mapper builds proposal JSON; `loadProposal()` is called once; PM finishes in the tool.

## Boundaries
- The generator is not modified. If AI is down, the generator still works on its own.
- Review UI is ours; the tool is loaded only after approval (it creates a new proposal per call).
- The provider is behind an adapter (Ollama default). Model chosen by evaluation.
- No database. Keep any session data local and git-ignored.
