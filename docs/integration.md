# Generator integration contract

Issue #2 reproduced the same-origin API, sample 04 mapping, model defaults, explicit overrides, unknown-model fallback, multiple drafts and reload persistence in local Chromium. The browser suite checks these through the public API and persisted proposals, with fresh browser storage per test. The other findings below come from the starter materials.

Original tool: `web/vendor/challenge-generator.html`  sha256: `bd20df4c79e70da57b4d4ddf0215f642b4653ad1277c95cbac522fcc2f48a9f8`

| # | Finding | Consequence |
|---|---------|-------------|
| 1 | Tool served over http inside a same-origin iframe: parent can call `contentWindow.loadProposal()`. | Serve via FastAPI static; never file://. |
| 2 | Each `loadProposal()` call creates a new proposal (2 calls -> 2 proposals). | Call once, after PM approval. |
| 3 | `deleteProposal(id)` exists but opens a confirm modal. | Not usable for silent cleanup. Playwright isolates tests with a fresh browser context and its own localStorage. |
| 4 | `state` is a top-level binding, not a window property. | Use exposed API: `window.challenge.models/practices/people/blank/example`. |
| 5 | Persistence is browser localStorage: `meridian_challenge_org_v2`, `meridian_challenge_proposals_v2`. | Use fresh browser storage for each test. Firebase config exists but is unused. |
| 6 | Models available: `balanced`, `global-growth`, `income`. | Discover at runtime; do not hard-code. |
| 7 | `applyModel` fills allocation, fees, objective preset. `income`: mgmt 0.75, brokerage 0.50, admin "R100 per month", alloc 50 fixed-interest / 20 SA equity / 20 intl equity / 10 cash. `balanced`: mgmt 0.85, alloc 30 SA equity / 35 intl equity / 25 fixed-interest / 10 cash. (`global-growth` defaults not yet inspected.) | These are MODEL_DEFAULT values, not from the notes. |
| 8 | Unknown `applyModel` ids are silently ignored. | Validate model id before loading. |
| 9 | Caller fields win over model defaults (deep merge; arrays/scalars replaced). | Mapper sends only fields we can justify. |
| 10 | Schema quirks: amounts under `strategy.keyFigures` only; digit strings; dropdown enums (horizon max "5 years+"). | Encode as validation rules (#5 and #6). For #6, add a regression test showing that an amount supplied only under `goalAssessment.keyFigures` is ignored by the generator and that the mapper emits monetary values under `strategy.keyFigures`. |
| 11 | Tool has no field for open items; samples 02/03 put "[TO CONFIRM: ...]" inside `needs`. | See ADR D9; suggest an open-items field in the write-up. |
| 12 | Optional `loadProposal(obj, {preview:true})` opens preview instead of editor. | Not needed for MVP. |

Not yet verified: file:// iframe behaviour (irrelevant if we serve over http), export/PDF flow.
