# Pattern: ask only what needs a person

> **Status:** Prose discipline (no script) · **Last verified:** 2026-11-15  
> **Tested against:** n/a — the rules are auditable from the transcript alone  
> **Enforcement:** Reviewer/self discipline; the authority boundary belongs in a gate, not in this prose  
> **Reference implementation:** none — this pattern is rules, not code

## Problem

An agent that asks before every step turns its maintainer into a rubber stamp.
Most of the questions have one obvious answer, and many could be settled by a
command the agent is already allowed to run: "is the branch up to date?",
"does this test still fail on the base?", "is the service healthy?".

Each such question costs a round trip. The work waits, the person switches
context, and the answer adds nothing a fresh observation would not have given.
Worse, real decisions get buried among the routine ones, and the person learns
to approve without reading.

The opposite failure is just as real. An agent told to "stop asking" starts
taking decisions that were never its to take.

## How it works

Sort every pending question through three tests, in this order.

1. **Could running something answer it?** If a check the agent is already
   permitted to run would settle the question, the agent runs it and reports
   the result. A question to a person is the slowest and least reliable probe
   available; use it last. If the check cannot be run or read, that is
   could-not-assess: say so and ask, never guess.
2. **Would the answer be a rubber stamp?** If the choice is reversible and has
   one clearly sensible answer, the agent decides, records the decision where
   it lives (the ticket, the spec, the pull request) and reports it with an
   invitation to disagree. The person reviews after, not before.
3. **Is it the person's to decide?** Everything left is a real question:
   something that cannot be undone, something that needs authority, or a
   judgement only the person can make.

The usual shorthand for tests 2 and 3 is doors. A two-way door can be walked
back through; a one-way door cannot. The shorthand misses a case, so this
pattern uses three doors:

| Door | Examples | What the agent does |
|---|---|---|
| **Two-way** | local code, a feature branch, test data, a draft specification | Walks through, shows the result after |
| **One-way** | production data, a release to users, a force-push to a shared branch, deleting something it did not make, a message to another person | Stops and asks |
| **Reversible, but not yours** | merging to the default branch, releasing work for pickup, changing a credential or a policy, granting an exception to a guardrail | Stops and asks |

The third door is the one that matters. A merge can be reverted, so a rule
built only on reversibility lets the agent merge. But who may merge is a
question of authority, not of undo cost. **An action is not permitted merely
because it can be undone.**

Two entries that often appear on two-way lists deserve care. A pull request
notifies people and starts automation the moment it opens, so it is only
partly undoable. "Development infrastructure" can hold live state that nothing
else has a copy of. Classify by what the action touches, not by the name of
the environment.

## How to ask, when asking is right

- **Give a recommendation.** A question without one hands the analysis back to
  the person. State the options, the default you would take and why.
- **Make each question self-contained.** The person may read it hours later
  with no memory of the conversation. Name the thing, link it, and say what
  happens for each answer.
- **Match the batching to the person.** In a live session, one question at a
  time keeps the exchange short. For a maintainer who checks in a few times a
  day, one numbered list of every open point is better than a drip of single
  questions. Pick one and write it down.

## Example

An agent is fixing a failing test and wants to know whether the failure is its
own doing.

Without the pattern it asks: "This test also seems to fail on the main branch.
Should I treat it as pre-existing?" The person has to go and look.

With the pattern, test 1 applies. The agent checks out the base commit, runs
the one test, and reports: "The test fails on the base commit too (same
assertion). I have left it out of this change and recorded it on the ticket.
Say so if you want it fixed here instead." No question was needed, and the
decision is visible and reversible.

Later the change is green and reviewed. Reverting a merge is easy, so by a
two-door rule the agent would merge. Under three doors it stops: merging is
reversible but not its decision. It reports the head commit, the evidence, and
asks for the merge.

## Where the rule goes

Like any standing instruction, it belongs in the file the agent loads every
session (`CLAUDE.md`, `AGENTS.md` or your equivalent), not in a message said
once. A version you can adapt:

```markdown
## When to ask

If a check you are already permitted to run could answer a question, run it
and report the result instead of asking. If the check cannot be run or read,
say so and ask; do not guess.

Decide reversible choices that have one sensible answer. Record the decision
where it lives and report it, so it can be overturned.

Stop and ask for anything that cannot be undone, and for anything that is
someone else's to decide even if it can be undone: merging, releasing work,
credentials, spend, policy, and exceptions to a guardrail. An action is not
permitted merely because it can be undone.

When you ask, give the options and your recommendation, and make the question
readable on its own.
```

Replace the list in the third paragraph with your own authority decisions.
That list is the part that carries the weight; the rest is economy.

## What this builds on

The one-way and two-way door framing comes from Amazon's 2015 letter to
shareholders, which separates irreversible "Type 1" decisions from reversible
"Type 2" ones and warns against using the heavy process for both. A
[short post by Vox](https://x.com/Voxyz_ai/status/2121672008421568810) applied
that framing to agent instruction files and added the two lines this page
keeps closest to the original: do not ask when the answer would be a rubber
stamp, and run the thing when running it would answer the question. The third
door is this page's addition.

It also leans on two neighbours in this cookbook: the
[three-outcome script contract](script-three-outcome-contract.md), which is
why an unreadable check leads to a question and not a guess, and the
[claim-discipline rules](claim-discipline-rules.md), which govern how the
result of the check is reported.

## Limits to understand before using this

**The door classification is a judgement made by the agent, in prose.** An
agent can misfile a one-way door as two-way, and nothing in this pattern stops
it. Do not rely on this page for the authority boundary. Put that in a
mechanism the agent cannot talk its way past: branch protection, a merge gate
that checks who approved, credentials the agent does not hold. See the
[direct-push guard](direct-push-guard.md) and
[reviewer isolation](reviewer-isolation.md). This pattern reduces unnecessary
questions; the gates are what make that safe.

**"Permitted" has to be defined somewhere else.** Test 1 covers checks the
agent may already run. If your permission model is loose, "run it instead of
asking" inherits the looseness. A check that changes state is not a check.

**Decide-and-report moves review later, it does not remove it.** If nobody
reads the reports, wrong defaults accumulate quietly. Keep the reports short
enough to be read.

**Measure it.** Count how often a person had to act per unit of shipped work,
and how many reported decisions were later overturned. If the first number is
not falling, the rule is not working. If the second is rising, the agent is
deciding things it should have asked about. The source harness adopted this
rule on the date above and has no measurement to report yet.
