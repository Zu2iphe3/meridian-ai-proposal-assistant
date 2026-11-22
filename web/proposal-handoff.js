// Build editable inputs. Keep the original extraction response alongside them for evidence.
export function reviewFromExtraction(extraction) {
  const verification = extraction.financial_verification;
  const accepted = verification.mapping_candidates;
  const fields = extraction.fields;
  const review = {};
  const name = fields.client_name;
  if (name.value && name.uncertainty === "none") review.client_name = name.value;
  if (accepted.currency) review.currency = accepted.currency;
  for (const [candidate, reviewed] of [
    ["investment_amount", "investment_amount"],
    ["income_amount", "monthly_income"],
  ]) {
    if (accepted[candidate] !== undefined && review.currency) {
      review[reviewed] = {
        amount: accepted[candidate],
        currency: review.currency,
        approximate: verification.fields[candidate].uncertainty === "approximate",
      };
    }
  }
  const frequency = verification.fields.adviser_fee.frequency;
  if (accepted.adviser_fee !== undefined && (frequency === null || frequency === "annual")) {
    review.adviser_fee = accepted.adviser_fee;
  }
  for (const field of ["horizon", "risk"]) {
    if (verification[field].status === "verified" && fields[field].uncertainty === "none") {
      review[field] = verification[field].value;
    }
  }
  return review;
}

function generator(frame) {
  const tool = frame.contentWindow;
  if (typeof tool?.loadProposal !== "function" || typeof tool.challenge?.models !== "function") {
    throw new Error("Wait for the proposal generator to finish loading.");
  }
  return tool;
}

export function listGeneratorModels(frame) {
  return generator(frame).challenge.models().map(({ id, label, portfolioName, scope }) => ({
    id, label, portfolioName, scope,
  }));
}

async function requestMapping(review) {
  const response = await fetch("/api/proposals/map", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved: true, review }),
  });
  if (!response.ok) {
    const error = new Error("The reviewed proposal could not be mapped. Check the reviewed values.");
    error.details = (await response.json().catch(() => ({}))).detail;
    throw error;
  }
  return response.json();
}

export function createProposalHandoff(frame) {
  let review;
  let approval;

  function setReview(values) {
    review = structuredClone(values);
    approval = undefined;
  }

  function approve() {
    if (!review) throw new Error("Set the reviewed proposal before approving it.");
    approval ??= { token: Symbol("proposal approval"), review, pending: undefined, called: false };
    return approval.token;
  }

  function createDraft(token) {
    const attempt = approval;
    if (!attempt || token !== attempt.token) {
      return Promise.reject(new Error("Approve the current review before creating a draft."));
    }
    // Publish the shared promise before any validation or I/O so duplicate
    // activation of this approval cannot race into the vendor call.
    attempt.pending ??= Promise.resolve().then(async () => {
      if (approval !== attempt) throw new Error("Review changed. Approve it again.");
      generator(frame);
      const mapped = await requestMapping(attempt.review);
      if (approval !== attempt) throw new Error("Review changed. Approve it again.");

      const tool = generator(frame);
      const model = attempt.review.model_id;
      if (mapped.proposal.applyModel !== (model ?? undefined)) {
        throw new Error("The mapped model does not match the approved review.");
      }
      if (model && !listGeneratorModels(frame).some(({ id }) => id === model)) {
        throw new Error("The selected model is no longer available in the generator.");
      }

      // A vendor exception can happen after persistence. Do not retry that call
      // for the same approval when its outcome is uncertain.
      attempt.called = true;
      const draftId = tool.loadProposal(mapped.proposal);
      return { draftId, generatorDefaults: mapped.generator_defaults };
    }).catch((error) => {
      if (!attempt.called) attempt.pending = undefined;
      throw error;
    });
    return attempt.pending;
  }

  return { setReview, approve, createDraft };
}
