import { createProposalHandoff, listGeneratorModels, reviewFromExtraction } from "./proposal-handoff.js";

const clarification = { request: null, questions: null, failed: false, deferred: new Set(), held: new Set() };

const byId = id => document.getElementById(id);
const formatAmount = new Intl.NumberFormat("en-GB");
const notes = byId("meeting-notes");
const frame = byId("proposal-generator");
const confirmReview = byId("confirm-review");
const approveButton = byId("approve-draft");
const handoff = createProposalHandoff(frame);

const groups = [
  ["Client and capital", [
    { key: "client_name", label: "Client name", limit: 500 },
    { key: "currency", label: "Proposal currency", choices: ["ZAR", "USD", "GBP", "EUR"] },
    { key: "investment_amount", label: "Investment capital", money: true },
  ]],
  ["Income and fees", [
    { key: "monthly_income", label: "Monthly income", money: true, source: "income_amount" },
    { key: "adviser_fee", label: "Annual adviser fee (%)", limit: 20, decimal: true },
  ]],
  ["Risk and portfolio", [
    { key: "horizon", label: "Investment horizon", choices: ["1 year+", "3 years+", "5 years+"] },
    { key: "risk", label: "Risk category", choices: [
      "Conservative", "Moderately Conservative", "Moderate", "Moderately Aggressive", "Aggressive",
    ] },
    { key: "model_id", label: "Generator model", choices: [], source: "portfolio_preference" },
    { key: "needs", label: "Client objectives and notes", multiline: true, limit: 4000 },
  ]],
];
const rows = new Map();
const state = {
  extraction: null, source: "", automatic: {}, edits: new Map(), evidenceKey: "client_name",
  requestId: 0, request: null, frameReady: false, models: [], reviewVersion: 0,
  makingDraft: false, draftCreated: false,
};

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function notify(id, text) {
  const node = byId(id);
  node.textContent = text;
  node.hidden = !text;
}

function setOptions(control, placeholder, choices) {
  control.replaceChildren(new Option(placeholder, ""));
  for (const [value, label] of choices) control.add(new Option(label, value));
}

function buildFields() {
  for (const [group, definitions] of groups) {
    const fieldset = element("fieldset", "", "review-group");
    fieldset.append(element("legend", group));
    const grid = element("div", "", "field-grid");
    for (const def of definitions) {
      const row = element("div", "", def.multiline ? "field wide" : "field");
      const heading = element("div", "", "field-head");
      const label = element("label", def.label);
      label.htmlFor = "review-" + def.key;
      const badge = element("span", "", "badge");
      heading.append(label, badge);
      const control = element(def.choices ? "select" : def.multiline ? "textarea" : "input");
      control.id = label.htmlFor;
      if (def.choices) setOptions(control, def.key === "model_id" ? "No model selected" : "Leave blank", def.choices.map(x => [x, x]));
      if (def.limit) control.maxLength = def.limit;
      if (def.money) { control.maxLength = 30; control.inputMode = "numeric"; }
      if (def.decimal) control.inputMode = "decimal";
      control.placeholder = def.key === "monthly_income" ? "e.g. 28000" :
        def.money ? "e.g. 6200000" : def.decimal ? "e.g. 0.60" : "";
      const meta = element("div", "", "field-meta");
      const context = element("div", "", "field-context");
      const evidence = element("button", "View evidence");
      evidence.type = "button";
      evidence.setAttribute("aria-label", "View evidence for " + def.label);
      evidence.addEventListener("click", () => {
        state.evidenceKey = def.key;
        renderEvidence();
        if (matchMedia("(max-width: 740px)").matches) byId("evidence-title").focus();
      });
      context.append(evidence);
      meta.append(context);
      let approximate;
      if (def.money) {
        const toggle = element("label", "", "approx");
        approximate = element("input");
        approximate.type = "checkbox";
        approximate.setAttribute("aria-label", "Approximate " + def.label.toLowerCase());
        toggle.append(approximate, "Approximate");
        meta.append(toggle);
        approximate.addEventListener("change", () => recordEdit(def.key, false));
      }
      const warning = element("p", "", "field-warning");
      warning.id = control.id + "-warning";
      warning.hidden = true;
      control.addEventListener(def.choices ? "change" : "input", () => recordEdit(def.key, true));
      const question = element("div", "", "field-clarification");
      question.id = control.id + "-clarification";
      question.hidden = true;
      control.setAttribute("aria-describedby", warning.id + " " + question.id);
      row.append(heading, control, meta, warning, question);
      grid.append(row);
      rows.set(def.key, { ...def, control, badge, evidence, approximate, warning, question });
    }
    fieldset.append(grid);
    byId("review-fields").append(fieldset);
  }
}

function currentValue(key) {
  if (state.edits.has(key)) return state.edits.get(key);
  return clarification.held.has(key) ? undefined : state.automatic[key];
}

function reviewedValues() {
  return Object.fromEntries(Array.from(rows.keys(), key => [key, currentValue(key)])
    .filter(([, value]) => value != null));
}

function recordEdit(key, reenterAmount) {
  const row = rows.get(key);
  const value = row.control.value.trim();
  const previous = currentValue(key);
  state.edits.set(key, !value ? null : row.money ? {
    amount: value,
    // Editing the number confirms its denomination. Toggling approximation alone does not.
    currency: reenterAmount ? currentValue("currency") || "" : previous?.currency || "",
    approximate: row.approximate.checked,
  } : value);
  invalidateApproval();
  renderReview(false);
}

function invalidateApproval() {
  state.reviewVersion++;
  state.draftCreated = false;
  confirmReview.checked = false;
  notify("handoff-error", "");
  byId("handoff-status").textContent = "";
  if (!byId("draft-section").hidden) {
    byId("draft-summary").textContent = "Previously created draft. It does not include changes to the current review.";
  }
  handoff.setReview(reviewedValues());
}

function fieldSource(row) {
  const key = row.source || row.key;
  const extraction = state.extraction;
  const verification = extraction.financial_verification;
  return {
    key, legacy: extraction.fields[key],
    verified: verification.fields[key] || verification[key],
    candidates: extraction.review_candidates.filter(item => item.proposed.field === key ||
      (key === "income_amount" && item.proposed.field === "monthly_income")),
    conflicts: extraction.conflicts[key] || [],
  };
}

function unconfirmedIncome(verified) {
  // A verified amount can still be ineligible for the monthly draft field.
  return state.automatic.monthly_income === undefined && verified?.status === "verified" &&
    verified.value != null && verified.evidence.some(item => item.quote && item.disposition === "current");
}

function fieldBadge(row) {
  if (row.key === "model_id") return ["PM selection", state.edits.has(row.key) ? "corrected" : "default"];
  if (state.edits.has(row.key)) return ["PM correction", "corrected"];
  if (row.key === "needs") return ["Optional", ""];
  if (clarification.held.has(row.key)) return ["Decision pending", "pending"];
  const { legacy, verified, candidates, conflicts } = fieldSource(row);
  if (conflicts.length || verified?.status === "conflict") return ["Conflict", "conflict"];
  if (row.key === "monthly_income" && unconfirmedIncome(verified)) {
    return [verified.frequency && verified.frequency !== "monthly"
      ? "Non-monthly · review" : "Income suggestion · confirm", "pending"];
  }
  if (candidates.some(item => item.disposition === "provisional")) return ["Provisional suggestion", "pending"];
  if (verified?.status === "unresolved" || legacy?.uncertainty === "unresolved") return ["Needs confirmation", "pending"];
  if (!currentValue(row.key)) return ["Missing", ""];
  if (legacy?.provenance === "INFERRED") return ["AI inferred", "inferred"];
  return [currentValue(row.key)?.approximate ? "Stated · approximate" : "Stated in notes", "stated"];
}

function renderReview(fillControls = true) {
  if (!state.extraction) { refreshApproval(); return; }
  for (const row of rows.values()) {
    const value = currentValue(row.key);
    if (fillControls) {
      row.control.value = row.money ? value?.amount || "" : value || "";
      if (row.approximate) row.approximate.checked = value?.approximate || false;
    }
    if (row.approximate) row.approximate.disabled = !value;
    const [text, tone] = fieldBadge(row);
    row.badge.textContent = text;
    row.badge.className = "badge " + tone;
    row.evidence.hidden = row.key === "needs";
  }
  renderEvidence();
  renderClarifications();
  refreshApproval();
}

function showSource(evidence) {
  const source = state.source;
  const node = byId("source-text");
  // Python offsets count code points, while JavaScript slices UTF-16 code units.
  // Locate the literal quote in the original text and highlight only a unique match.
  const quote = evidence.find(item => item.quote && source.includes(item.quote))?.quote;
  const index = quote ? source.indexOf(quote) : -1;
  if (index === -1 || source.indexOf(quote, index + quote.length) !== -1) {
    node.textContent = source;
    return;
  }
  node.replaceChildren(source.slice(0, index), element("mark", quote), source.slice(index + quote.length));
}

function renderEvidence() {
  const row = rows.get(state.evidenceKey);
  if (!row || !state.extraction) return;
  const { key, legacy, verified, candidates, conflicts } = fieldSource(row);
  const evidence = [];
  const add = (quote, label) => {
    if (quote && !evidence.some(item => item.quote === quote)) evidence.push({ quote, label });
  };
  for (const item of verified?.evidence || []) {
    add(item.quote, item.disposition === "superseded" ? "Earlier figure" :
      verified.status === "conflict" ? "Competing evidence" : "Source passage");
  }
  add(verified?.quote || legacy?.quote, "Source passage");
  const clarificationItem = clarification.questions?.find(item => item.field === row.key);
  for (const source of clarificationItem?.evidence || []) {
    if (!evidence.some(item => item.quote.includes(source.quote))) {
      add(source.quote, "Clarification context");
    }
  }
  for (const item of conflicts) add(item.quote, "Competing evidence");
  for (const item of candidates) add(item.verified_quote,
    item.disposition === "provisional" ? "Provisional suggestion" : "Review evidence");
  if (["investment_amount", "currency", "income_amount", "adviser_fee"].includes(key)) {
    for (const item of state.extraction.financial_verification.excluded_evidence) {
      add(item.quote, "Excluded from mapping");
    }
  }
  const suggestion = row.key === "client_name" && candidates.find(
    item => item.disposition === "provisional" && item.verified_quote && typeof item.proposed.value === "string",
  );
  byId("use-name").hidden = !suggestion;
  if (suggestion) byId("use-name").textContent = "Use suggested name: " + suggestion.proposed.value;
  for (const entry of rows.values()) entry.evidence.setAttribute("aria-pressed", String(entry === row));
  const fieldHeading = byId("evidence-field");
  fieldHeading.textContent = row.label;
  if (row.key === "monthly_income") {
    const requirement = state.extraction.financial_verification.fields.income_requirement;
    if (requirement.value === "none") fieldHeading.textContent += " · No income required";
    if (verified?.frequency && verified.frequency !== "monthly") fieldHeading.textContent += " · " + verified.frequency + " figure stays in review";
    for (const item of requirement.evidence) add(item.quote, "Income requirement");
  }
  // A model quote can contain the same individual passages the verifier found.
  // Keep the longer passage when both have the same evidence label.
  const passages = evidence.filter(item => !evidence.some(other =>
    other !== item && other.label === item.label && other.quote.includes(item.quote)
  ));
  const quotes = byId("evidence-quotes");
  quotes.replaceChildren();
  if (row.key === "monthly_income" && unconfirmedIncome(verified)) {
    const amount = [verified.unit, verified.value].filter(Boolean).join(" ");
    const frequency = verified.frequency || "frequency unconfirmed";
    quotes.append(element("p", `Unconfirmed suggestion: ${amount} (${frequency}). Enter a monthly amount only if confirmed.`));
  }
  if (!passages.length) quotes.append(element("p", "No verified source quote is available for this field."));
  for (const item of passages) {
    const quote = element("div", "", "evidence-line");
    quote.append(element("small", item.label), element("blockquote", item.quote));
    quotes.append(quote);
  }
  showSource(passages);
}

function renderClarifications() {
  const visible = !!state.extraction && !state.request && notes.value.trim() === state.source;
  notify("clarifications-status", !visible ? "" : clarification.request
    ? "Checking for questions. You can continue reviewing."
    : clarification.failed ? "AI questions are unavailable. Continue with manual review."
    : "");
  for (const row of rows.values()) {
    const item = clarification.questions?.find(question => question.field === row.key);
    const needsConfirmation = clarification.held.has(row.key);
    const wasOpen = row.question.querySelector("details")?.open;
    row.question.replaceChildren();
    row.question.hidden = !visible || state.edits.has(row.key) || !(item || needsConfirmation);
    if (row.question.hidden) continue;
    const suggested = needsConfirmation ? state.automatic[row.key] : undefined;
    let content = row.question;
    if (suggested) {
      const details = element("details");
      const amount = formatAmount.format(BigInt(suggested.amount));
      details.open = wasOpen ?? false;
      details.append(element("summary", `Review proposed ${suggested.currency} ${amount}`));
      row.question.append(details);
      content = details;
    }
    if (item) content.append(element("p", item.question));
    if (clarification.deferred.has(row.key)) {
      content.append(element("small", "Deferred · stays in review"));
      continue;
    }
    const actions = element("div", "", "clarification-actions");
    if (needsConfirmation) {
      if (suggested) {
        content.append(element("small", "This amount is approximate and unconfirmed. Confirm it or enter the agreed amount."));
        if (suggested.currency === currentValue("currency")) {
          const confirm = element("button", "Confirm " + row.label.toLowerCase(), "quiet");
          confirm.type = "button";
          confirm.addEventListener("click", () => {
            row.control.value = suggested.amount;
            row.approximate.checked = suggested.approximate;
            recordEdit(row.key, true);
            row.control.focus();
          });
          actions.append(confirm);
        }
      }
    } else {
      content.append(element("small", "Use the review field to record the confirmed answer."));
    }
    const defer = element("button", "Defer " + row.label.toLowerCase(), "quiet");
    defer.type = "button";
    defer.addEventListener("click", () => {
      clarification.deferred.add(row.key);
      renderClarifications();
      row.control.focus();
    });
    actions.append(defer);
    content.append(actions);
  }
}

function cancelClarifications() {
  clarification.request?.abort();
  clarification.request = null;
}

async function askClarifications() {
  if (clarification.request || clarification.questions !== null || state.request ||
      !state.extraction || notes.value.trim() !== state.source) return;
  const controller = new AbortController();
  clarification.request = controller;
  clarification.failed = false;
  renderClarifications();
  refreshApproval();
  const { financial_verification, ...extraction } = state.extraction;
  try {
    const response = await fetch("/api/clarifications", {
      method: "POST", headers: { "Content-Type": "application/json" }, signal: controller.signal,
      body: JSON.stringify({
        notes: state.source, extraction, financial_verification,
        pm_fields: [...state.edits.keys()].filter(key => !["needs", "model_id"].includes(key)),
      }),
    });
    if (!response.ok) throw new Error("Clarification unavailable");
    const data = await response.json();
    if (clarification.request !== controller) return;
    clarification.questions = data.questions.filter(item => rows.has(item.field) && !state.edits.has(item.field));
  } catch {
    if (clarification.request === controller) clarification.failed = true;
  } finally {
    if (clarification.request === controller) {
      clarification.request = null;
      renderReview(false);
    }
  }
}

function validationErrors(review) {
  const errors = {};
  for (const key of ["investment_amount", "monthly_income"]) {
    const money = review[key];
    if (!money) continue;
    if (!/^[0-9]{1,30}$/.test(money.amount) || (key === "investment_amount" && /^0+$/.test(money.amount))) {
      errors[key] = "Enter a whole amount without currency symbols or separators.";
    } else if (!review.currency) {
      errors[key] = "Select a proposal currency.";
    } else if (money.currency !== review.currency) {
      errors[key] = "Re-enter the amount to confirm the selected currency.";
    }
  }
  if (review.adviser_fee !== undefined &&
      (!/^[0-9]+(?:\.[0-9]+)?$/.test(review.adviser_fee) || Number(review.adviser_fee) > 100)) {
    errors.adviser_fee = "Enter an annual percentage from 0 to 100 without the % symbol.";
  }
  if (review.model_id) {
    if (!state.models.some(model => model.id === review.model_id)) errors.model_id = "Select an available model.";
    else if (!review.currency || !review.horizon || !review.risk) errors.model_id = "Confirm currency, risk and horizon before applying a model.";
  }
  return errors;
}

function refreshApproval() {
  const review = reviewedValues();
  const errors = validationErrors(review);
  for (const row of rows.values()) {
    const error = errors[row.key] || "";
    row.warning.textContent = error;
    row.warning.hidden = !error;
    row.control.setAttribute("aria-invalid", String(!!error));
  }
  const stale = state.extraction && notes.value.trim() !== state.source;
  byId("stale-review").hidden = !stale;
  byId("model-defaults").hidden = !review.model_id;
  const blocker = !state.extraction ? "Extract and review the notes to enable approval."
    : state.request ? "Wait for extraction to finish."
    : stale ? "Extract the updated notes before approval."
    : Object.keys(errors).length ? "Resolve the highlighted fields before approval."
    : !Object.keys(review).length ? "Enter at least one reviewed value to continue."
    : !state.frameReady ? "Wait for the generator to finish loading."
    : state.draftCreated ? "This approval already created a draft." : "";
  confirmReview.disabled = !!blocker || state.makingDraft;
  approveButton.disabled = confirmReview.disabled || !confirmReview.checked;
  byId("approval-hint").textContent = blocker || (clarification.held.has("investment_amount") &&
    !state.edits.has("investment_amount") ? "Unconfirmed capital stays out of this draft."
    : "Confirm the current values, then approve to create one editable draft.");
  const step = state.request ? 1 : state.extraction ? (confirmReview.checked || state.draftCreated ? 3 : 2) : 0;
  for (const [i, item] of Array.from(document.querySelectorAll(".workflow li")).entries()) {
    item.dataset.complete = String(i < step);
    if (i === step) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  }
}

function setBusy(busy) {
  const button = byId("extract-button");
  button.disabled = busy;
  button.setAttribute("aria-busy", String(busy));
  byId("notes-form").setAttribute("aria-busy", String(busy));
}

function notesChanged() {
  cancelClarifications();
  renderClarifications();
  if (state.request) {
    state.request.abort();
    state.request = null;
    state.requestId++;
    setBusy(false);
  }
  byId("note-count").textContent = notes.value.length.toLocaleString("en-ZA") + " / 4,000";
  byId("new-case").hidden = !notes.value && !state.extraction && !state.draftCreated;
  notify("extraction-error", "");
  byId("extraction-status").textContent = state.extraction ? (
    notes.value.trim() === state.source ? "Review ready" : "Notes changed"
  ) : "Ready for notes";
  invalidateApproval();
  refreshApproval();
}

async function extractNotes(event) {
  event.preventDefault();
  const source = notes.value.trim();
  if (!source) {
    notify("extraction-error", "Enter meeting notes or load the fictional sample.");
    notes.focus();
    return;
  }
  state.request?.abort();
  cancelClarifications();
  const id = ++state.requestId;
  const controller = new AbortController();
  state.request = controller;
  invalidateApproval();
  setBusy(true);
  renderClarifications();
  notify("extraction-error", "");
  byId("extraction-status").textContent = "Extracting with local AI…";
  refreshApproval();
  let receivedExtraction = false;
  try {
    const response = await fetch("/api/extract", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes: source }), signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail?.message || "Extraction failed. Check the local service and try again.");
    // Aborting saves work. The request number also protects against late responses.
    if (id !== state.requestId) return;
    if (state.source !== source) clarification.held.clear();
    if (state.source !== source || JSON.stringify(state.extraction) !== JSON.stringify(data)) {
      clarification.questions = null;
      clarification.failed = false;
      clarification.deferred.clear();
    }
    state.extraction = data;
    state.source = source;
    state.automatic = reviewFromExtraction(data);
    // Keep a source estimate out of approval while Qwen is still checking it.
    if (state.automatic.investment_amount?.approximate) clarification.held.add("investment_amount");
    receivedExtraction = true;
    byId("review-panel").hidden = false;
    byId("evidence-empty").hidden = true;
    byId("evidence-content").hidden = false;
    document.body.dataset.reviewed = "true";
    invalidateApproval();
    renderReview();
    byId("extraction-status").textContent = "Review ready";
    byId("review-title").focus({ preventScroll: true });
  } catch (error) {
    if (id === state.requestId && error.name !== "AbortError") {
      notify("extraction-error", error.message + " Your notes and edits are still here.");
      byId("extraction-status").textContent = "Extraction failed";
    }
  } finally {
    if (id === state.requestId) {
      state.request = null;
      setBusy(false);
      renderClarifications();
      refreshApproval();
      if (receivedExtraction) void askClarifications();
    }
  }
}

async function createDraft() {
  if (approveButton.disabled) return;
  const revision = state.reviewVersion;
  state.makingDraft = true;
  notify("handoff-error", "");
  byId("handoff-status").textContent = "Creating the approved draft…";
  refreshApproval();
  try {
    const draft = await handoff.createDraft(handoff.approve());
    if (revision !== state.reviewVersion) return;
    state.draftCreated = true;
    byId("draft-section").hidden = false;
    byId("draft-summary").textContent = "Draft ready to edit. Generator defaults: " +
      draft.generatorDefaults.join(", ") + ".";
    byId("handoff-status").textContent = "Approved draft created.";
    byId("draft-title").focus();
  } catch (error) {
    if (revision === state.reviewVersion) {
      notify("handoff-error", error.message + " Your reviewed values are still here.");
      byId("handoff-status").textContent = "";
    }
  } finally {
    state.makingDraft = false;
    refreshApproval();
  }
}

function resetCase() {
  clarification.questions = null;
  clarification.failed = false;
  clarification.held.clear();
  clarification.deferred.clear();
  state.extraction = null;
  state.source = "";
  state.automatic = {};
  state.edits.clear();
  state.evidenceKey = "client_name";
  notes.value = "";
  byId("review-panel").hidden = true;
  byId("evidence-content").hidden = true;
  byId("evidence-empty").hidden = false;
  byId("evidence-field").textContent = "Review the original wording for a field.";
  byId("draft-section").hidden = true;
  delete document.body.dataset.reviewed;
  notesChanged();
}

async function loadSample() {
  if ((notes.value.trim() || state.extraction) &&
      !confirm("Replace the current notes and review with the fictional sample?")) return;
  const button = byId("load-sample");
  const current = notes.value;
  const revision = state.reviewVersion;
  button.disabled = true;
  try {
    const response = await fetch("/api/examples/meeting-notes");
    if (!response.ok) throw new Error("The fictional sample could not be loaded.");
    const sample = await response.text();
    if (notes.value !== current || state.reviewVersion !== revision) return;
    resetCase();
    notes.value = sample;
    notesChanged();
    notes.focus();
  } catch (error) {
    notify("extraction-error", error.message);
  } finally {
    button.disabled = false;
  }
}

function loadModels() {
  try {
    state.models = listGeneratorModels(frame);
    state.frameReady = true;
    const modelControl = rows.get("model_id").control;
    setOptions(modelControl, "No model selected", state.models.map(({ id, label }) => [id, label || id]));
    modelControl.value = currentValue("model_id") || "";
  } catch {
    state.frameReady = false;
  }
  refreshApproval();
}

buildFields();
handoff.setReview({});
notes.addEventListener("input", notesChanged);
byId("notes-form").addEventListener("submit", extractNotes);
byId("review-form").addEventListener("submit", event => event.preventDefault());
byId("load-sample").addEventListener("click", loadSample);
byId("new-case").addEventListener("click", () => {
  if (confirm("Start a new case? The current notes and review will be cleared.")) {
    resetCase();
    notes.focus();
  }
});
byId("use-name").addEventListener("click", () => {
  const suggestion = fieldSource(rows.get("client_name")).candidates.find(
    item => item.disposition === "provisional" && item.verified_quote && typeof item.proposed.value === "string",
  );
  if (suggestion) {
    const control = rows.get("client_name").control;
    control.value = suggestion.proposed.value;
    recordEdit("client_name", true);
    control.focus();
  }
});
confirmReview.addEventListener("change", refreshApproval);
approveButton.addEventListener("click", createDraft);
frame.addEventListener("load", loadModels);
loadModels();
