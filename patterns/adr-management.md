# Pattern: architecture decision records as the agent's own memory

> **Status:** Reference implementation · **Last verified:** 2026-08-31  
> **Tested against:** `scripts/new_adr.py`, `scripts/check_records.py` (`tests/`)  
> **Enforcement:** Instruction (write + read trigger) backed by a CI collision check  
> **Reference implementation:** `scripts/new_adr.py` (optional), `scripts/check_records.py`

## Problem

A design decision is made and settled. A few weeks later, a new contributor,
or the same agent in a new session, proposes an option that was already
rejected. The reasoning was sound; it just lived in a chat, a PR comment or
someone's memory. A later reader is unlikely to find it before making the same
decision again.

Agents make this problem more obvious because they start each session with very
little memory beyond what is written in the repository. If the reason for
choosing X over Y is not recorded, the next session may propose Y again.

## How it works

Keep a numbered, append-only log of decisions in the repository itself,
one file per decision, and treat consulting it as a required step before
proposing a new design, not an optional nicety.

1. **One file per decision, numbered, in `docs/adr/`.** Filename convention:
   `NNNN-short-title.md`. Numbers are assigned in order and never reused,
   even for a decision that's later reversed. A later ADR can supersede an
   earlier one; it doesn't overwrite it.
2. **A fixed, short template.** Context (what was actually true when this
   was decided, including constraints that later readers won't have
   lived through), Decision (the choice, stated plainly), Consequences
   (what this makes easier, what it makes harder, and what it rules out).
   Keeping the shape small is what makes these fast enough to actually
   write.
3. **Immutable once merged.** An ADR records what was decided and why, at
   the time. If circumstances change, write a new ADR that supersedes it
   and says so explicitly, rather than editing history. The record is
   only useful if you can trust it reflects what was actually true when
   the call was made.
4. **A number-collision guardrail in CI.** Two branches proposing ADR-0047
   at the same time is a real failure mode once more than one person (or
   agent) is writing these concurrently; each branch's git history is
   blind to what the other has already claimed. A CI check that reads
   every open PR's proposed ADR numbers, not just the local branch, and
   fails on a collision, catches this before either branch merges. The
   worked example in
   [script-three-outcome-contract.md](script-three-outcome-contract.md)
   is exactly this checker, `check_records.py`, applied to `docs/adr/`.
5. **Consulting the log is a required step, not a courtesy.** Before an
   agent proposes a new design in a covered area, it should be instructed
   to check `docs/adr/` for anything already on point, the same way it
   would check existing code before writing new code. This is the part
   that turns the log from an archive into working memory: it only pays
   off if it's actually read before decisions are made, not just written
   after.

## Where this lives, and how it actually gets wired in

The five points above describe the shape of the log. None of them happen
by themselves. Two separate habits have to be wired into the agent's
instructions, because they're triggered by opposite moments: reading the
log happens *before* a design is proposed, writing to it happens *after*
a decision is settled. Naming only one of the two, which is the easy
mistake, gets you either a log nobody consults or a log that stops
growing.

**The write trigger is a checklist item at the point of closing out a
piece of work, not a script.** In the system these patterns come from,
this lives as one line in the standard workflow every task goes through
before it's considered done: *if this settled something that constrains
future work, a contract other code must honour, a rejected alternative
that would otherwise get re-proposed, or a deliberate narrowness someone
could later mistake for an oversight, write an ADR in `docs/adr/` in the
same PR.* The number is picked by hand (`max + 1`, counting open PRs, not
just the local branch), and the CI collision check from point 4 is what
actually catches it if two branches picked the same number, after the
fact, not something that prevents the collision up front. That's a
deliberate, working, low-tech design: cheap enough that people (and
agents) actually do it, backed by a check that catches the one way it
predictably goes wrong.

Put the equivalent line in whatever your own project reads on every turn:

```markdown
## Architecture decisions

At the end of any task, before calling it done: did this settle
something that constrains future work? A contract other code now has to
honour, an alternative you deliberately rejected, a narrowness someone
could later mistake for an oversight. If yes, write an ADR in
`docs/adr/`, in the *same* PR as the change, numbered `max + 1` across
`docs/adr/` on master **and every open PR** (your branch can't see
sibling branches, so check open PRs explicitly, or let CI's collision
check catch it). Say what was rejected and why, and state the
consequences, including the bad ones.
```

**A scaffold script is an optional hardening on top of that, not
something the source system actually uses.** If picking the number by
hand keeps causing collisions in practice, a small command that
computes it and writes the template removes that specific failure mode:

```python
# new_adr.py
import re
import sys
from pathlib import Path

ADR_DIR = Path("docs/adr")

TEMPLATE = """# ADR-{number}: {title}

- **Status:** Proposed
- **Supersedes:** nothing

## Context



## Decision



## Consequences


"""

def next_number() -> str:
    existing = [int(m.group(1)) for p in ADR_DIR.glob("*.md")
                if (m := re.match(r"(\d{4})-", p.name))]
    return f"{(max(existing) + 1) if existing else 1:04d}"

if __name__ == "__main__":
    title = sys.argv[1]
    number = next_number()
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    path = ADR_DIR / f"{number}-{slug}.md"
    path.write_text(TEMPLATE.format(number=number, title=title))
    print(f"Created {path}. Fill in Context, Decision, Consequences, then open a PR.")
```

`next_number` still only sees the local branch, exactly like picking a
number by hand does. The CI collision check is what makes either
approach safe, not the script: the script just removes a typo-prone step,
it doesn't remove the need for the check.

**The read trigger, checking `docs/adr/` before proposing a design, is
the general principle this pattern is named for, worth adding
explicitly rather than assumed.** Whether or not you automate it, name it
as its own rule, since it's triggered by a different moment than the
write trigger above and won't happen just because the write trigger
exists:

```markdown
**Before proposing a design for anything covered by `docs/adr/`,
search it first.** Run `grep -ril "<topic>" docs/adr/` (or your repo's
equivalent search) before writing a design doc or opening a PR that
makes an architectural choice. If a relevant ADR exists, either follow
it or explicitly say which ADR you're superseding and why. Proposing an
already-rejected alternative without mentioning the ADR that rejected it
is a process error, not just a missed optimization.
```

If your agents run as dispatched subagents, put this rule directly in
the dispatch prompt for design-shaped tasks too, not only in the shared
instruction file, since a subagent may not read the same standing
instructions the orchestrator does.

## Why this matters more once an agent is involved

A human designer builds up tacit memory of past decisions just by having
been there. An agent starts every session close to blank, with only what's
written in the repository to go on. That makes an ADR log less of a
convenience and more of a critical part of the agent's working memory:
it's the mechanism by which "we already tried that" survives from one
session to the next. Practically, this means the log should grow the same
way any other memory would: a new ADR gets written whenever a decision is
made that would otherwise have to be re-litigated later, and the instructions
that dispatch agent work should name where to look before proposing
something new.

See [`examples/adr-0021-example.md`](examples/adr-0021-example.md) for a
real (scrubbed) ADR from the system these patterns come from, showing what
a non-trivial one looks like in practice, including a "Consequences"
section that names a real tradeoff rather than only listing benefits.

## What this builds on

This is the standard [Architecture Decision Records](https://adr.github.io/)
practice, originated by Michael Nygard. Nothing about the numbering,
template, or immutability convention here is new. What's specific to this
write-up is the number-collision guardrail (a concurrency problem that
barely exists with a single human author working on one branch at a time,
and becomes routine once multiple agents propose designs in parallel), and
treating "check the log before deciding" as a required step in an agent's
instructions rather than an assumed habit.

## Limits to understand before using this

**An ADR log only works if writing one is actually cheap.** If the
template is heavy or the process feels bureaucratic, decisions stop
getting recorded, quietly, and the log becomes an incomplete record that's
worse than no record because it looks authoritative. Keep the template
short enough that a real decision takes a few minutes to write up.

**Immutability needs to be a real convention, not just a preference.**
Nothing stops someone from editing an old ADR to match new reality. The
value depends on people (and agents) actually treating merged ADRs as
frozen and writing a new superseding one instead. Say this explicitly in
whatever process document governs the log.

**"Check the log first" doesn't happen by itself.** An agent won't reliably
search `docs/adr/` before proposing a design unless something in its
instructions tells it to, every time, for the areas the log covers.
Treat this the same as any other required step: name it explicitly, don't
assume it's implied by the log existing.
