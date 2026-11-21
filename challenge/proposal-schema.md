# Proposal tool — data reference

This describes the data the tool understands **today**. It's a reference, not a
set of rules: you're free to use it as-is, extend it, or change the tool.

## Loading a proposal

The tool exposes one entry point:

```js
window.loadProposal(proposalObject)   // a JS object, or a JSON string
```

It merges your object onto a blank proposal, opens it in the editor and renders
it. Every field is optional; anything you leave out keeps its default.

Helpers for exploring the tool's dummy data from the browser console:

```js
window.challenge.models()      // the model portfolios
window.challenge.practices()   // practices
window.challenge.people()      // portfolio managers
window.challenge.blank()       // a blank proposal: the full shape
window.challenge.example()     // load a fully-worked example
```

## Model portfolios

Passing `applyModel` fills in the asset allocation, the composition and the
fees from a model portfolio, so most of a proposal comes from one choice.

| `applyModel`    | Portfolio                         | Currency |
|-----------------|-----------------------------------|----------|
| `balanced`      | Meridian Balanced Portfolio       | ZAR      |
| `global-growth` | Meridian Global Growth Portfolio  | USD      |
| `income`        | Meridian Income Portfolio         | ZAR      |

## Main fields

| Field | Meaning |
|---|---|
| `clientName`, `clientEmail` | The client. |
| `introGreetTo` | `"client"` or `"advisor"`: who the letter is addressed to. |
| `financialPlanner` | The client's adviser, when the proposal goes to them. |
| `needs` | The client's needs and objectives, in prose. |
| `goalAssessment.clientType` | e.g. `Individual`, `Trust`, `Company`. |
| `goalAssessment.mandateType` | e.g. `Discretionary`. |
| `goalAssessment.currency` | `ZAR`, `USD`, `GBP`, `EUR`. |
| `strategy.keyFigures.totalInvestment` | Amount to invest, as a digit string, e.g. `"8500000"`. |
| `strategy.keyFigures.incomeValue` | Monthly income drawdown. |
| `objective.targetReturn` | e.g. `"CPI + 5%"`. |
| `objective.benchmark` | Benchmark description. |
| `objective.riskProfileCategory` | `Conservative`, `Moderately Conservative`, `Moderate`, `Moderately Aggressive` or `Aggressive`. |
| `objective.riskProfile` | Risk profile, in prose. |
| `objective.investmentHorizon` | `1 year+`, `3 years+` or `5 years+`. |
| `fees.advisorFee` | Adviser fee %, e.g. `"0.75"`. |
| `replacements` | `{ isReplacement, details }`, used when replacing an existing portfolio. |
| `strategy.allocation` | A bespoke allocation, `[{ class, key, percent }]`, instead of a model. |

`schema.json` has the full machine-readable version, and
`window.challenge.blank()` shows every field the tool holds.

## Quirks worth knowing

- **Amounts must go under `strategy.keyFigures`.** The tool ignores
  `goalAssessment.keyFigures`, and anything placed there won't show on the
  proposal.
- **Horizon and risk level are dropdowns.** A value outside the listed options
  is stored but won't match a dropdown option in the editor.
- **Number fields take plain digit strings** with no separators or currency
  symbols.
