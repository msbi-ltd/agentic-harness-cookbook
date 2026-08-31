# Example ADR: a guardrail's liveness is attested from outside itself

> **Status:** Worked example · **Last verified:** 2026-08-31

This is a scrubbed, generalized version of a real ADR from the system these
patterns come from, included to show what a non-trivial one looks like:
a decision with a genuine tradeoff in its Consequences section, not just a
list of benefits, and an Alternatives section that shows the rejected
options were actually considered, not invented after the fact to make the
chosen option look obvious.

---

## ADR-0021: A guardrail's liveness is attested from outside itself

- **Status:** Accepted
- **Supersedes:** nothing. Extends an earlier ADR about check verdicts to
  cover the *running* of a check, not just its result.

### Context

One of our scheduled checks (call it the rot sweep) exempts its own
workflow from its own verdicts, and a separate tracking process watches
the sweep's **outcomes** from outside. So the sweep's results were already
being checked by something other than the sweep itself.

Its **liveness** was not. A scheduled job that runs a thousand times and
then silently stops, because of an expired credential, a renamed runner
label, a stuck concurrency lock, or a scheduler that quietly disables
crons on inactive repositories, reads as healthy on every existing check:
one tool calls it "healthy" because its last few *recorded* runs
succeeded (it never asks how long ago that was), and another calls it
"ok" because the workflow file parses and is marked active. A sweep that
ran an hour ago and one that hasn't run in six weeks score identically.
So "the sweep ran and found nothing" and "the sweep stopped running" look
the same from outside, which is the exact failure shape the earlier ADR
was written to close, one level up.

### Decision

**The evidence that a guardrail is alive is a completed-run timestamp,
observed by a different workflow on a different schedule. No check may
attest its own liveness.**

A new probe ages the rot sweep's most recent *completed, scheduled* run
against the cadence declared in its own trigger configuration, tolerating
a small number of missed ticks before failing. The workflow that runs this
probe is deliberately excluded from the rot sweep's own watch list: a
probe can't usefully report that the run it belongs to never happened.
The two watch each other's absence, not their own.

A few corollaries, each backed by a test:

- A watched job with **no completed run at all** fails. Absence isn't
  the same as freshness.
- **Failure to observe is reported as its own outcome, distinct from
  what was observed.** A workflow the API can't find, or a timestamp
  that won't parse, is reported as "couldn't check," never folded into
  the substantive claim "this has never run," which would be a
  different, and wrong, diagnosis.
- A schedule the parser can't understand is reported as could-not-assess,
  never silently treated as a pass. A guessed cadence would make the
  liveness verdict wrong without anyone noticing.

### Alternatives considered

- **A second, unexempted sweep workflow that checks the first.** Already
  rejected elsewhere: the second sweep would eventually need watching
  too, and if either one rotted, it would report the other as rotten
  forever, with no way to tell which one actually broke.
- **A staleness check built into the sweep itself.** Anything the sweep
  computes about itself is exempt from its own verdicts by the same logic
  that caused this problem. The blind spot moves; it doesn't close.
- **A heartbeat file committed on a schedule.** Would need write
  permissions the running credential doesn't have, and for good reason.

### Consequences

- Every future watchdog now has to name who attests *its* liveness, and
  the answer can't be itself.
- A schedule the parser can't express turns the probe red until either
  the parser is extended or the schedule is rewritten in an expressible
  form. This is intentional, the alternative is a silent gap, but it's a
  real, stated cost: some legitimate schedules will need reformatting
  before they can be watched at all.
- **What's still open, stated rather than hidden:** if both watching
  workflows stop firing at the same moment, neither one reports the
  other. That's irreducible from inside a single scheduling platform
  without a clock external to it. The outer backstop is a human noticing.
  What this decision closes is the more likely case: one of the two
  stopping while the other keeps running.
