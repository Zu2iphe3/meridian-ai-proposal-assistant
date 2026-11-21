# Brief: from meeting notes to a draft proposal

## The problem

Portfolio Managers (PMs) write investment proposals for their clients using the
proposal tool in this pack (`challenge-generator.html`). The tool works well
once its fields are filled in. Filling them in is the slow part.

After a client meeting, a PM has a page of scribbled notes or a voice note
recorded in the car. Today they translate that into the tool by hand.

**Your challenge: make it possible for a PM to hand the tool their free-text
notes or a voice recording, and get a draft proposal set up for them to review.**

How you solve it is up to you. You can build something that sits alongside the
tool, change the tool itself, or both. Use whatever models, frameworks and
approach you think are right.

We're also open to a different way of building proposals altogether. If you
think there's a better solution than this tool, make the case and show us.

## What you have

- **`challenge-generator.html`**: the proposal tool. Open it in a browser; it
  runs offline with no login. It already has an entry point you can use,
  `window.loadProposal(...)`, but you don't have to.
- **`proposal-schema.md`**: a reference to the data the tool understands today.
- **`sample-inputs/`**: four sets of realistic adviser notes, including a
  voice-note transcript and a deliberately sparse note. Each comes with an
  example output. Treat these as illustrations, not an answer key.

All data in this pack is fictional. Keep it that way: don't use any real client
or company data.

## Things worth thinking about

These aren't requirements. They're the parts of the problem that make it
interesting.

- **Real notes are messy and incomplete.** What should happen when the amount,
  income need or time horizon is missing?
- **This is financial advice to a real client.** How does the PM know which
  parts came from their notes and which the system filled in?
- **The PM is the decision-maker.** How do they review, correct and finish the
  draft?
- **PMs are busy and often on the move.** What's the least effort it could take
  them?
- **Could the PM build the proposal through a conversation rather than a
  form?** Picture talking to an agent that already knows the firm's model
  portfolios and proposal template, and that builds the proposal up as you go.

## How we'll work

- **Make assumptions.** Where something is unclear, decide, write the decision
  down, and keep going.
- **Ask questions** whenever you'd rather check than assume. Questions go to
  `[OWNER: name + how to reach you]`.
- **Show something early.** A rough end-to-end version beats a polished half.

## What to bring back

- A working demo: notes or a voice note go in, a draft proposal comes out.
- The code, with a README explaining how to run it.
- A short write-up covering what you built and why, the assumptions you made,
  what you'd do next, and any changes you'd suggest to the tool (or why you'd replace it).
