# Pattern: mechanical claim-discipline rules

> **Status:** Prose discipline (no script) · **Last verified:** 2026-08-31  
> **Tested against:** n/a — the rules are auditable from the transcript alone  
> **Enforcement:** Reviewer/self discipline, measured after the fact  
> **Reference implementation:** none — this pattern is rules, not code

## Problem

Sooner or later, an agent will state something it did not check in the current
turn: “the PR is green,” “the file is fixed,” or “I’ll watch CI and merge when
it passes.”

The claim may come from an older check, another agent's report, or an assumption
that sounds like an observation. The dangerous part is the confidence. A
tentative claim tends to get checked; a confident one tends to get used.

“Be careful” is not enough. The agent needs a small set of rules that make the
required evidence clear at the moment it makes the claim.

## How it works

Replace the general instruction with a small number of **mechanical,
checkable rules**. Rules whose violation can be confirmed after the fact
just by reading the transcript, not rules that depend on the agent
remembering to use good judgment:

1. **Same-turn evidence only.** A fact about external state (a PR, a CI
   run, a file, a board) can only be stated if the command that produced
   it ran *in this turn*. Not "I checked earlier," not a summary of a
   prior tick. If the claim matters and the command hasn't run yet, the
   answer is "not yet verified." That's a third state, not a forced
   choice between yes and no.
2. **No volunteered claims.** Answer what was asked, then stop. Every
   extra claim is another chance to state something nobody actually
   checked. A shorter answer with three verified facts beats a longer one
   with a fourth that was just inferred.
3. **Never promise a watch you haven't armed.** "I'll monitor X and act
   when it changes" is false unless a monitoring mechanism was actually
   started in this same turn. If nothing was armed, say so plainly
   instead of implying ongoing attention that isn't actually happening.
4. **A three-outcome contract for checks, not two.** Any verification
   step reports pass, fail, or *couldn't assess*, and couldn't-assess is
   never silently folded into pass. "I don't know why X broke, here's the
   one command that would tell us" is a legitimate, complete answer.
   "X is broken, do Y" without having run that command is a made-up
   verdict.

None of these need the model to introspect correctly at the exact moment
it matters. They just need it to follow a fixed, narrow procedure that a
transcript audit can confirm was followed. The check happens outside the
generation, not inside it.

## Example

A subagent is asked to check whether a deploy succeeded. Ten minutes
earlier, in an unrelated turn, it ran a health check that passed. Without
these rules, a plausible response is:

> "Deploy succeeded, health check is green."

That's a same-turn violation. The command backing the claim ran in a
*previous* turn, and nothing re-verified it now. Health could have
regressed in the meantime. Under rule 1, the correct response is either
to re-run the check in this turn, or to say plainly that the claim is
based on a check from ten minutes ago and offer to re-verify. Not to
restate a stale result as current fact.

A second example, for rule 3: asked to "keep an eye on the deploy and let
me know if it fails," a response like "I'll monitor it and flag
anything" is only true if a polling loop, webhook, or scheduled check was
actually started in that turn. If nothing was armed, the honest answer is
"I can't monitor passively, ping me and I'll check," not a phrase that
implies ongoing attention that nothing is actually providing.

## Where these rules go

These are **standing instructions**, not one-off reminders. They need to
live in whatever the agent reads on every turn, not be said once
mid-conversation and expected to stick. Concretely, that means the
project's system prompt or persistent instruction file. For a Claude
Code-style harness, that's a `CLAUDE.md` or `AGENTS.md` equivalent loaded
at the start of every session, not a comment left in a single chat turn.
A rule stated once in a conversation is competing with everything said
afterward for the model's attention. A rule loaded fresh into context
every turn doesn't have that problem. If the harness supports it, pair
the written rule with an automated transcript check, a script that greps
for violations, or a review step that reads back over what was claimed.
That closes a gap prose alone can't.

Here's a version you can drop into a `CLAUDE.md` or `AGENTS.md` file
almost as is:

```markdown
## Communication

**Apply the three-outcome contract to your own statements, not just to
scripts.** Any check you report on has three outcomes: pass, fail, or
could-not-assess. Could-not-assess is never reported as a pass.

Before naming a cause, declaring something broken, or asking the user to
act, work out when it last worked and say how you know. If you can't,
that's could-not-assess: say so. "I don't know why X broke, here's the
one command that would tell us" is a good answer. "X is broken, do Y"
without having run that command is a made-up verdict.

### The mechanical rules

1. **A fact about external state (a PR, a CI run, a file, a deployment)
   may only be stated if the command producing it ran in THIS turn.**
   Not "I checked earlier." Not a summary of a previous turn. Either the
   command ran just now, or the claim isn't made: say "not yet verified"
   instead.
2. **Don't volunteer claims nobody asked for.** Answer what was asked,
   report what was done, and stop.
3. **Don't promise a watch you haven't armed.** "I'll watch CI and merge
   on green" is false unless a monitoring mechanism was actually started
   in this same turn. If you can't arm one, say "still running, ping me
   and I'll look."
```

Adjust the examples in rule 1 (PR, CI run, file, deployment) to whatever
your own agent actually touches. The structure, not the exact wording, is
what matters: a fixed, short list of checkable rules living in the file
the agent reloads every session.

## What this builds on

Not much, honestly. This is a mitigation, not a technique with an
established literature behind it. It borrows the spirit of "make the
invariant checkable, not just statable" from testing and formal methods,
applied to a much softer problem: a language model reporting on its own
work.

## Limits to understand before using this

**This does not solve hallucination or fabrication. It makes specific
instances of it easier to catch after the fact.** The rules are
instructions in the prompt, enforced by a transcript audit that happens
after generation, not a constraint applied during generation itself. A
model can still break any of these rules. What changes is that the
violation becomes something a human or an automated check can point to
and name, instead of just a vague sense that something felt off.

**Measure whether it's actually working. Don't just assume it is.** If
you adopt these rules, track violations directly: count the times a
claim was made without same-turn evidence, or a watch was promised but
never armed. If that rate isn't dropping, the rules aren't working, and
more sentences won't fix that. Something needs to change about where and
how they're enforced. That means tooling, not more prose.

This pattern doesn't crack agent honesty. It's a stricter, checkable set
of rules with an audit for violations. Claiming more than that would be
exactly the kind of unverified claim this pattern exists to prevent.
