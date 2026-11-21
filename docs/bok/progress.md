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

The proposed Issue #4 revision uses one Qwen 2.5 3B call and a minimal
field/value/quote/reason contract. Python derives status, limits acceptance to
eight core fields, and retains noncore proposals for review. A single live
smoke recovered 22/24 facts, including Sarah's approximate amount. The subsequent
post-tuning pass recovered 56/84 facts from the previously seen locked pack,
with zero incorrect accepted values or timeouts. The median was 40.86 seconds
and p95 was 58.63 seconds. H12 accepted no fields, because the model cited the
planted instruction as evidence even for genuine values. The pack remains below
the agreed coverage and latency targets. Issue #4 is open for review. Follow-up
verification and mapper tests can use deterministic fixtures independently of
live inference.

### Independent manual Swagger checks

The portfolio manager independently tested four fictional notes through Swagger
using the proposed Qwen 2.5 3B implementation. These user-reported results are
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

Issue #5 will scan the entire original note for financial expressions,
independently of the model's evidence quotes, and reconcile those findings
with its proposed roles. It will verify equivalent numeric forms and income
frequency or absence against source context, preserve the original evidence,
and surface competing figures for PM review. The case with competing adviser
fees is a required regression. These findings do not change the extraction
prompt or close Issue #4.
