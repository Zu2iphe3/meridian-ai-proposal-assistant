# Progress and open items

The clean foundation is on main at d33afd0. Hosted Actions run 44892664851 passed dependency installation, Ruff, mypy, baseline pytest and Gitleaks. Chromium was skipped on that run because no browser suite existed.

M0 is complete. PR #15 merged the generator contract tests. Hosted PR run 44897994232 and main run 44899483022 installed Chromium and passed both browser tests, three foundation tests and Gitleaks.

Issue #4 adds the local extraction endpoint, strict candidate schema and evidence checks. Local verification passed 27 offline tests, including both Chromium tests, and Ruff and mypy. Hosted verification of this branch is pending.

Ollama 0.18.0 started on loopback with the existing llama3.2:3b model. The model loaded on CPU and Ollama reported 2.3 GiB in use for the model at a 4,096-token context, with 1.0 GiB system RAM free during the run. The initial representative probe timed out on sample 01 at 90 seconds. Sample 04 returned schema-shaped JSON in 46.7 seconds, but only one of six quotes matched the notes and the investment amount was missing. A diagnostic replay exposed an unrelated portfolio quote and an incorrect fee conversion.

The final endpoint smoke run returned a timeout on sample 01 (90.0 seconds), and rejected model output on samples 02 (67.9 seconds), 03 (40.4 seconds), and 04 (37.4 seconds). None produced an accepted candidate response, so withheld counts are unavailable for those runs. This model is not verified for the demo. No alternate model was downloaded. Issue #5 will independently verify financial meaning, and Issue #6 will map reviewed values to the generator.

Issue #4 diagnostic replay used the four fictional samples on loopback with cloud inference disabled and recorded only aggregate diagnostics. Original Llama contract: 0/4 accepted, one timeout, three field-contract rejections, zero malformed JSON and zero wire-schema failures. The three parsed responses had 10 matching and four nonmatching nonempty quotes, six candidates that failed evidence checks, and two incorrect candidates among the values spot-checked.

The compact contract uses 17 model-facing fields and a single status label. The application expands that label to provenance and uncertainty. Replacement details can reuse the verified replacement quote. Optional client email is left for later capture. The prompt requires source-form financial expressions. Quote checks tolerate whitespace and smart quotes and reject partial words and numbers.

| Model on compact contract | Accepted / wire-schema valid | Field-contract rejections | Matching / missing or nonmatching quotes | Evidence failures / incorrect values spot-checked | Sample 01–04 latency (s) |
|---|---|---|---|---|---|
| llama3.2:3b | 0/4 / 4/4 | 4 | 17 / 7 | 1 / 5 | 53.0, 51.2, 18.7, 36.6 |
| qwen2.5:3b | 0/4 / 4/4 | 4 | 8 / 2 | 1 / 0 | 39.5, 25.7, 14.4, 18.8 |

Neither compact-contract run had a timeout, malformed JSON or wire-schema failure. Candidate-level counts are diagnostic observations from rejected responses and may overlap. Zero incorrect values in Qwen's spot checks does not establish completeness. The final offline suite passed 28 tests including Chromium, and Ruff and mypy passed. Neither model is verified for demo use. The default model has not changed.

### Issue #4 field-level recovery

A Qwen-only replay confirmed that Pydantic accepted all four payloads. The extraction helper then raised on the first field error. Across the replay, seven candidates lacked an inference reason, one failed the income choice/type check, one had no traceable quote, and one portfolio candidate would have been accepted. Two quotes failed to match, but one of those candidates failed the inference check before reaching quote validation. Calls stopped normally at 302–383 prompt tokens and 90–201 output tokens, with a 4,096-token context and 2,048-token output cap.

The service now retains independently grounded fields and publishes reason codes for withheld or unresolved candidates. It uses exact original excerpts and can recover a uniquely located, attributable source-form financial value. Malformed payloads or responses with no safely interpretable candidates still fail closed. The fixed 17-field model list is unchanged.

| Qwen retest | Populated / with quotes | Withheld | Correct / incorrect financial checkpoints accepted | Latency | Prompt / output tokens |
|---|---|---|---|---|---|
| 01 | 3 / 3 | 1 | 3 / 0 | 47.6 s | 381 / 328 |
| 02 | 8 / 8 | 2 | 3 / 0 | 64.1 s | 347 / 553 |
| 03 | 1 / 1 | 3 | 1 / 0 | 23.6 s | 316 / 195 |
| 04 | 2 / 2 | 4 | 1 / 0 | 54.1 s | 397 / 450 |

All four returned reviewable partial results. Sample 03 retained source evidence for the unresolved investment amount. Amounts in 01 and 04 and fee and target return in 04 remain gaps. The model omitted the explicit no-income statement in 02 and 04. Separate offline tests verify that conflicting evidence remains unresolved. Financial checking was limited to factual checkpoints, and live results do not establish demo readiness. The local suite reported 29 passed and four opt-in tests skipped. The live metrics above were collected separately through the same extraction service with Qwen on loopback.

### Issue #4 targeted span experiment

A Qwen-only replay found that the sample 01 investment amount and sample 04 investment amount, fee and return were withheld because the returned values were not verbatim, despite matching quotes. Qwen omitted the income requirement candidates entirely in 02 and 04.

The experiment exposed lexical financial spans with exact character offsets and limited spoken-number patterns. It added separate handling of direct no-income statements and retained the fee conflict guard. Qwen selected zero span IDs across six calls. No targeted financial omission was recovered. Supported fields regressed from 14 to two across the supplied samples. Explicit no-income was correctly recovered in 02 and 04. The unseen sterling note returned currency and no-income only; the unseen note with spoken amounts and conflicting fees returned no supported candidates. No incorrect financial checkpoint was accepted.

| Case | Baseline fields / seconds | Experiment fields / seconds |
|---|---|---|
| 01 | 3 / 47.6 | 0 / 52.1 |
| 02 | 8 / 64.1 | 1 / 32.3 |
| 03 | 1 / 23.6 | 0 / 12.9 |
| 04 | 2 / 54.1 | 1 / 46.4 |
| Unseen sterling | — | 2 / 21.5 |
| Unseen spoken and conflicting fees | — | 0 / 31.3 |

The live run preceded the final offline guard against shortened conditional or reported no-income quotes. The investigation stopped after the six-call comparison. Keep the earlier field-level recovery as the candidate baseline and review the explicit-income guard separately from the span prompt. Neither the experiment nor its predecessor has been committed.

The span-ID experiment was backed up outside the repository and reconstructed byte for byte before selective removal. The stronger field-level recovery prompt and contract are restored, with guarded explicit no-income handling retained. A targeted live replay through FastAPI returned HTTP 200 for samples 01 and 04 with three populated fields each. Qwen's financial rewrites were still withheld under the unchanged lexical matching rule. The source-expression correction awaits approval.

### Issue #4 verified-quote fallback

Decision D15 preserves the exact-value path. When a verified quote contains one financial expression with a clear role, the service copies that expression and its source qualifiers. Competing expressions leave a null field, a reason, and the original quote. No normalized model number is accepted on the fallback path.

The local Qwen run returned HTTP 200 on all four supplied cases and both unseen fictional cases. Sample 01 executed via Swagger Try it out. The fallback recovered the sample 01 investment amount and the sample 04 investment amount, spoken fee, and return wording. Explicit no-income was retained for samples 02, 04, and the unseen sterling note. Sample 03 stayed unresolved for investment amount. Across the run, all 26 populated fields had exact source evidence, 11 candidates were withheld, and no incorrect financial checkpoint was accepted. Latencies for cases 01–06 were 51.9, 67.9, 26.9, 57.4, 31.3, and 33.8 seconds. The unseen competing-fees case still omitted the amount and income requirement. It withheld the fee without surfacing both competing statements. Whole-note contradiction detection remains an Issue #5 responsibility.

The complete local suite passed 43 tests, including Chromium and the focused regressions, with four opt-in tests skipped. The six live HTTP calls were verified separately. Ruff, mypy, and diff whitespace checks passed. The vendor SHA-256 remains unchanged. Issue #4 is awaiting review and commit approval.

The updated challenge requires a working demo, runnable code with a README and a short engineering write-up. Model choice and handling of ambiguous portfolio labels require validation. Ask the portfolio manager to confirm unclear labels. Confirm permission before sharing the supplied generator and review the outstanding questionnaire before submission.

The merged Issue #4 revision uses one Qwen 2.5 3B call and a minimal
field/value/quote/reason contract. Python derives status, limits acceptance to
eight core fields, and retains noncore proposals for review. A single live
smoke recovered 22/24 facts, including Sarah's approximate amount. The subsequent
post-tuning pass recovered 56/84 facts from the previously seen locked pack,
with zero incorrect accepted values or timeouts. The median was 40.86 seconds
and p95 was 58.63 seconds. H12 accepted no fields, because the model cited the
planted instruction as evidence even for genuine values. The pack remains below
the agreed coverage and latency targets. Issue #4 closed when PR #16 merged. Follow-up
verification and mapper tests can use deterministic fixtures independently of
live inference.

### Independent manual Swagger checks

The portfolio manager independently tested four fictional notes through Swagger
using the Qwen 2.5 3B implementation now on main. These user-reported results are
separate from the locked benchmark and the developer smoke run.

| Manual case | Correct / determinate | Observation |
|---|---:|---|
| 1 | 7/8 | One determinate fact was withheld. |
| 2 | 6/8 | Two determinate facts were withheld. |
| 3 | 4/4 | Missing information stayed blank. |
| 4 | 6/7 | Neither competing adviser fee was accepted. |
| Total | 23/27 (85.2%) | Zero incorrect accepted fields reported. |

Explicit income or no-income wording, equivalent adviser fee forms and
paraphrased quotes can still cause correct proposals to be withheld. Competing
fees stayed blank in case 4, but no structured conflict was surfaced.

### Issue #5 financial verification

The extraction endpoint now adds a financial verification result from scanning the
original notes, including passages the model omitted. It keeps original expressions,
offsets, uncertainty, periods, and explicitly superseded figures. Ambiguous values,
unsupported units, currency mismatches and competing figures are review items.

Replaying all 12 saved fictional Qwen responses through a mocked provider gave
21/40 correct determinate financial facts before verification and 40/40 after.
The four scored fields were investment amount, currency, adviser fee and income
requirement. The verifier recovered 19 facts with zero incorrect accepted values
and zero false rejections in this replay. These notes were previously seen. The
four original assessment inputs were also tested offline. The unlabelled fee
unit in sample 04 still requires PM confirmation.

Two fresh fictional notes passed through FastAPI and local Qwen with the
same model digest, prompt and output schema as Issue #4. Both requests
returned HTTP 200 in 39.87 s and 28.74 s, with 8/8 determinate financial
facts and zero incorrect accepted values. The second case kept both
competing fee quotes and withheld the fee even though the model proposed
one. An earlier smoke check had missed these quotes because the scanner
mistook a reference to a record for an instruction. The corrected rule
has a focused regression test.

Local verification passed 117 offline tests including both Chromium tests.
Ruff, mypy, actionlint and the patch whitespace and secret scans passed.
Unmarked text that reads as a client fact still needs PM review. The scanner
does not establish authenticity, infer absent units, convert currencies, or
map non-monthly income to the generator's monthly field.

### Issue #5 manual-test correction

Three independent manual Swagger tests exposed a gap in the original scan.
The verifier could miss capital and corrections, and it verified one fee
despite source evidence for a competing rate. The ledger now reconciles
source-grounded uncertainty and conflicts before admitting a result. It retains
superseded amounts and evidence for excluded roles. Issue #6 must use
`financial_verification.mapping_candidates` after PM review and approval.

Replay of the supplied request and processed-response captures recovered
five facts. Correct coverage changed from 6/11 to 11/11, with no false
rejections. Incorrect accepted values and missed conflicts each changed from
one to zero. In the fee conflict case, the captured Issue #4 conflicts
object was empty. The anchored unresolved evidence and the full note still
blocked both fees. The captures were replayed offline and kept outside Git.
The saved 12-note benchmark matched the earlier 40/40 at the four scored
financial fields, with no incorrect accepted values or false rejections.

The frozen verifier and local Qwen returned HTTP 200 for all three fresh
notes in 30.56 s, 27.72 s and 30.54 s. The prewritten key scored 10/12
financial facts, up from 4/12 before verification. The verifier recovered
six facts with no incorrect accepted values, false rejections or missed
conflicts in this run. It withheld the competing fee Qwen proposed and kept
both percentages for review. The two misses were income requirement and
amount in a note that named a quarterly figure without specifying drawdown
or contribution. No tuning followed this run. The full offline suite passed
125 tests including both Chromium regressions.

### Issue #5 proposal-led verification

The next three independent Swagger tests exposed the limits of inferring
financial roles and correction links from wording. The original Test E
capture shows a grounded USD 325,000 model proposal and an unsafe USD 250,000
verified output. The revised verifier preserves the model proposal, scans
for compatible alternatives and leaves both amounts in review with capital
omitted from mapping. It leaves correction decisions to the PM when the
existing model contract cannot settle the relationship.

The six exact processed-response replays yielded 19/21 automatically verified
financial facts, versus 12/21 in the captures. The verifier produced one
correct numeric PM suggestion, blocked two previously incorrect values,
and made no incorrect acceptances. Two determinate corrections required PM
input. The saved 12-note replay verified 39/40 with zero incorrect values
and surfaced the remaining confirmed amount as a model-backed PM suggestion.
These fixtures, including the exact captures, remain outside the repository.

Three fresh notes completed a frozen loopback run in 38.95 s, 29.26 s and
25.35 s. The verifier automatically verified 11/12 determinate facts and
made no incorrect acceptances. In the remaining case, Qwen proposed the
correct revised amount with a quote that could not be found. The ledger
kept both source figures for PM review without promoting either. Another
case withheld both competing fees. No changes followed the frozen run.
The offline suite passed 127 tests, including both Chromium regressions.

### Issue #5 final evaluation

Eight development mocks isolated role contamination, quote-grounding
failures and category formatting. The final pass limits exclusions to
expressions with explicit source evidence of an unrelated role, preserves
unique recovered literals as PM review evidence, and normalises supported
risk formatting and grounded month/year horizons. Bounded ranges are
eligible only when both endpoints yield the same dropdown bucket.

The original A–H captures were replayed as regressions. G now preserves
the approximate capital and distinguishes the adviser fee from the
management charge. H keeps both capital figures and the exact risk term
in review without treating paraphrased or absent quotes as verified.
Across all eight captures, 38/42 keyed determinate facts were verified
automatically, two correct PM suggestions were surfaced, and no incorrect
values or missed conflicts were observed. The previously seen saved pack
remained at 39/40 on its four keyed fields. Local checks passed 134 offline
tests including both Chromium regressions. All benchmark notes and captures
are fictional and remain outside Git.

The development mocks improved from 25/35 to 32/35 verified facts and
reduced referrals on determinate facts from eight to two. The four live
development notes scored 21/22 verified with one correct PM suggestion,
zero incorrect values, and zero missed conflicts. The locked ten-note
holdout scored 40/47 verified, two correct PM suggestions, five referrals
on determinate facts, and two omitted determinate facts. No incorrect
verified or mapped values and no missed keyed fee conflicts were observed.

On the actual Qwen holdout responses, raw semantic precision was 35/42
and recall was 35/47. A source quote was located for 41/44 non-null
proposals, and 35/44 had a source quote and value aligned in an admissible
passage. All ten requests succeeded, with 32.65 s median and 91.00 s p95
end-to-end latency and no timeouts. No implementation or answer-key
changes followed the holdout. The largest remaining gaps are correction
links, equivalent compound fee expressions, and horizons that the model
omits or transforms before grounding.

### Client identity grounding follow-up

Issue #5 preserves the original client-name path where the person's role
is supported. It withholds explicit non-clients, unlabelled generic actors,
and names sourced only from instruction text. A unique exact occurrence
can repair a bad quote when its passage establishes the proposed person or
entity as the client. Otherwise the evidence is provisional. Original
model quotes and rejection reasons remain visible in review entries.

From 29 saved raw responses, 11 previously correct client names remained
accepted, two correct names were recovered, two generic role labels were
withheld, and three names were surfaced for PM confirmation. J stayed
provisional and K recovered automatically. All 203 other core field
comparisons and 41 financial payload comparisons matched before and after.
The 22 focused mocked cases showed no false rejections or incorrect client
identities. The full offline suite passed 156 tests including Chromium.

### Final client identity simplification

Automatic recovery now requires an explicit client or proposal label.
The own-capital wording heuristic was removed. J and K both retain exact
recovered passages for PM confirmation. The identity-specific instruction
guard uses explicit instruction markers rather than incidental words such
as “sample” or “instructions”. The financial source filter is unchanged.

The production delta is 49 added and 64 removed lines. All 29 saved raw
responses preserve the previous client outcomes, and the other seven
core fields and all 41 financial payloads match. The only changed capture
is K, which switches from automatically recovered to provisional. The
full offline suite passed 157 tests. No new model calls were made.

### Independent live Swagger follow-up

The user reported that all three additional fictional Swagger cases passed
the critical financial mapping checks. All three client names were accepted,
including one automatic evidence recovery. Revised capital, unknown currency,
conditional income and competing adviser fees stayed out of unsafe mapping.
These manual observations are separate from the frozen benchmark.

- Separate emergency savings can trigger unnecessary capital confirmation.
- A correct revised capital proposal can still require PM confirmation.
- A tentative investment horizon can lose its uncertainty classification.
- The numeric scan can retain irrelevant evidence, such as “One” in an
  adviser fee quotation.

The review workflow must retain the original evidence, let the PM resolve
uncertainty and confirm or correct tentative fields, and require explicit
PM approval before the mapper hands a proposal to the generator.

### Issue #6 proposal handoff

The mapper validates approved review values and calls the original generator
through its public interface. Deterministic Chromium tests cover Sample 01
from mocked extraction to a saved draft, explicit overrides, unresolved fee
and quarterly income omission, unknown models, stale approval, and duplicate
activation. The handoff module is ready for the review controls in Issues #7
and #8.

### Issues #7 and #8 PM workspace

The text workflow connects local extraction and source evidence to PM
corrections, explicit approval and a single editable draft. Review state is
held in the page for the current case. The generator retains its own draft
storage. Chromium tests cover retries, stale responses, mapping failures and
duplicate approval, including review on a mobile viewport.

The income review distinguishes a source-backed amount with unconfirmed
frequency from missing income and leaves the monthly field for PM confirmation.
Verification checks cadence against the amount and its income wording in the
same source clause. Competing or unsupported schedules stay in PM review.
