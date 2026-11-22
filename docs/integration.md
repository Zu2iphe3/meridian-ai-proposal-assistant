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

## Handoff for financial verification and PM review

The generator's public API accepts a partial object merged into its blank
proposal. Extraction supplies evidence for review. A schema-valid extraction
response alone does not authorize loading a draft.

| Reviewed fact | Generator handoff |
|---|---|
| Client | `clientName` |
| Investment capital | Verified, normalized digit string at `strategy.keyFigures.totalInvestment` |
| Currency | Reviewed code at both `goalAssessment.currency` and `strategy.currency` for the summary and displayed figures |
| Horizon and risk | `objective.investmentHorizon` and `objective.riskProfileCategory` using supported dropdown options |
| Income need | Review context only. An independently verified monthly amount maps to `strategy.keyFigures.incomeValue` |
| Portfolio preference | After PM selection, map to a discovered `applyModel` ID or validated `strategy.allocation` |
| Adviser fee | Verified percentage string at `fees.advisorFee` |

Other inputs such as recipient details, needs, mandate, benchmark and return
objective can be supplied or approved separately by the PM. Model defaults
are shown as defaults. A source suggestion does not become an approved value.
The review step shows accepted text and original evidence, clearly marks
approximation, and lists missing or conflicting core facts for correction.
Unresolved values stay blank in the mapped draft.

`POST /api/extract` adds a `financial_verification` result alongside extraction
fields and diagnostics. The verifier supplies decimal strings, exact source
expressions and character offsets, source frequency, and evidence dispositions. PM review uses `financial_verification.fields` as the authoritative financial
ledger. The sibling `excluded_evidence` lists expressions classified outside
the proposal, such as a reserve or other fees. Keep competing and potentially
superseded figures visible. For an unsettled field, an evidence disposition
of `current` means the expression remains in consideration. It confers no
approval. The top-level Issue #4 fields retain the model's diagnostics.
Use the top-level `client_name` as the accepted name. A recovered name is
accepted only when an explicit source label supports the proposed identity.
Client-name entries in `review_candidates` retain the original quote and
diagnostic. Ask the PM to confirm only entries marked `provisional`.


For `pm_confirm_source_backed_proposal`, display the evidence first. Where
the first evidence entry matches the source-backed extraction candidate,
show that proposal with its exact quote. Keep the selected mapping value
blank until the PM confirms it. If the extraction returned no source-backed
value, show the alternatives and ask for the figure directly.
If a rejected quote can be replaced with one unique literal source span,
show that span and the rejection reason for PM review. The recovered literal
does not verify the model's semantic interpretation. Grounded risk labels
tolerate surface formatting, and grounded duration ranges map only when
both exact endpoints share the same supported horizon bucket.

For Issue #6, `financial_verification.mapping_candidates` is the only
source of automatic financial inputs to the mapper. Apply PM edits
and approval before building any proposal. Never populate a proposal from
the ledger's evidence, raw candidates, unresolved fields or excluded figures.
Capital requires an integer amount and supported currency. Only verified
monthly income with compatible currency is included. A verified quarterly
or annual amount remains in the review ledger. A verified magnitude with
unresolved currency also remains available for review.

## Mapper and approval handoff

`web/proposal-handoff.js` exposes `reviewFromExtraction()`,
`listGeneratorModels()`, and `createProposalHandoff(iframe)`. Keep the
original extraction response beside the editable review so quotes,
uncertainty and provenance remain visible. User corrections replace the
reviewed values and must pass the same validation as automatic candidates.

Call `setReview(values)` when the review changes. On explicit PM approval,
call `approve()`, then pass its token to `createDraft(token)`. The handoff
maps that snapshot through `POST /api/proposals/map`, checks that the selected
model is still available, and makes one vendor call. Duplicate activation
shares the same result. An edit invalidates any pending approval. An error
after invoking the vendor does not retry automatically because a draft may
already exist.

The mapper emits the supported subset of `challenge/schema.json`. It keeps
capital and income currency attached to their reviewed values, maps only
monthly income, and retains approximation in `needs`. Applying a model
requires reviewed currency, risk and horizon so the vendor presets cannot
fill those gaps silently. The PM can leave the model unselected and still
create a draft. The mapping response labels the groups supplied by model or
practice settings separately. The public model list exposes names and IDs,
so exact defaults are visible in the generator after handoff. The vendor can
display a configured practice fee for an omitted fee field.

The assistant keeps PM edits separate from extraction results so another
extraction preserves them. Note changes, a new extraction or a field edit
invalidate approval. Conflicts and provisional evidence remain visible for PM
review. Only the approved snapshot enters the handoff. The resulting draft
opens in the vendor's independent editor.
