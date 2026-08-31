# Pattern: mistake ledger with `caught_by`

> **Status:** Reference implementation · **Last verified:** 2026-08-31  
> **Tested against:** `scripts/ledger.py` (`tests/test_ledger.py`)  
> **Enforcement:** Convention: records appended at named trigger moments; `caught_by` is the metric  
> **Reference implementation:** `scripts/ledger.py`

## Problem

An agent working across many sessions will make mistakes: an unsupported claim,
a wrong fact, or a skipped step. If each mistake is fixed and forgotten, the
only result is a vague feeling that reliability is improving.

Counting only mistakes found by a human is also misleading. A lower count could
mean the agent improved, or that the checks stopped catching problems. A useful
ledger records both the mistake and who found it.

## How it works

Keep a small, append-only log of mistakes, one entry per mistake, with a
fixed, closed set of fields. The field that matters most is **who caught
it**, not the mistake itself:

```python
from dataclasses import dataclass, field

KINDS = (
    "unverified-claim",
    "fabricated-detail",
    "premise-not-checked",
    "process-step-skipped",
    "wrong-diagnosis",
)

CAUGHT_BY = ("tool", "agent", "user", "self")  # tool = an automated check
                                                # agent = another agent caught it
                                                # user = the human caught it
                                                # self = the same agent noticed mid-task


@dataclass
class MistakeRecord:
    occurred_at: str       # RFC 3339 with a timezone
    kind: str              # one of KINDS
    caught_by: str         # one of CAUGHT_BY
    summary: str           # required: an uncountable mistake can't be audited
    corrected: bool | None = None    # None means "not measured", never "False"
    correction_ref: str = ""         # issue, PR, or commit that fixed it
```

A few choices carry the pattern's real weight:

- **`kind` is a closed list, not free text.** A free-text field silently
  grows new categories every week, and a ratio computed across weeks
  stops meaning anything once the categories underneath it have shifted.
  Add a new kind as a one-line change, rather than letting the
  model invent a new string.
- **`corrected` is `bool | None`, and `None` is not the same as `False`.**
  "Nobody checked whether this got fixed" and "this was checked and is
  still broken" are different claims. Coercing an unmeasured value to
  `False` invents a verdict nobody earned; coercing it to `True` is
  worse.
- **The record is written when the mistake happens, not batched up at the
  end of a session.** A mistake caught at 2pm and written up at 6pm
  competes with everything that happened in between for the agent's
  attention, and tends to get summarized into something vaguer than what
  actually occurred.

## Where this lives, and how a record actually gets written

The data structure above is only half the pattern. The other half is
making sure a record gets written at the moment a mistake is caught,
not "whenever someone remembers." Three pieces make that happen:

1. **A store outside any single agent's throwaway workspace.** If the
   ledger lives inside a git worktree that gets deleted when a task ends,
   every record in it disappears with the worktree. Put it somewhere
   that survives the agent, and the branch, that wrote it: an append-only
   file (JSON Lines works well, one record per line) at a fixed path in
   the main checkout, or a table in a shared database if you already have
   one running.
2. **A small append function, called by name, not reimplemented ad hoc
   each time.** Give the agent one command to run, so writing a record
   is as easy as running a test, not a multi-step thing it has to
   remember the shape of.
3. **An explicit instruction that names the trigger.** "Write a record
   when a mistake is caught" is too vague to act on reliably. Name the
   moments: when an automated check fails on the agent's own output, when
   a human corrects something the agent claimed, when another agent's
   review catches an error, when the agent notices its own mistake
   mid-task. Each of those maps directly to a `caught_by` value.

```python
# ledger.py
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

LEDGER_PATH = Path("/var/lib/agent-harness/mistake-ledger.jsonl")

@dataclass
class MistakeRecord:
    occurred_at: str
    kind: str
    caught_by: str
    summary: str
    corrected: bool | None = None
    correction_ref: str = ""

def append_record(record: MistakeRecord) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a") as f:
        f.write(json.dumps(asdict(record)) + "\n")

if __name__ == "__main__":
    # Callable directly: python ledger.py <kind> <caught_by> "<summary>"
    kind, caught_by, summary = sys.argv[1], sys.argv[2], sys.argv[3]
    record = MistakeRecord(
        occurred_at=datetime.now(timezone.utc).isoformat(),
        kind=kind,
        caught_by=caught_by,
        summary=summary,
    )
    append_record(record)
```

A line in the project's `CLAUDE.md` or `AGENTS.md` is what actually
connects the trigger to the write:

```markdown
## Recording mistakes

When a mistake in your own output is caught, by a failing check, a
human correction, another agent's review, or your own mid-task
realization, run:

    python ledger.py <kind> <caught_by> "<one-line summary>"

`<kind>` is one of: unverified-claim, fabricated-detail,
premise-not-checked, process-step-skipped, wrong-diagnosis.
`<caught_by>` is one of: tool, agent, user, self.
Do this immediately, in the same turn the mistake surfaces, not batched
up at the end of the session.
```

Reading the ledger back is what makes it worth having written to. A
short report script, run periodically, is enough:

```python
from collections import Counter
import json

def report(path=LEDGER_PATH):
    records = [json.loads(line) for line in open(path)]
    by_caught = Counter(r["caught_by"] for r in records)
    total = sum(by_caught.values())
    for who, count in by_caught.most_common():
        print(f"{who}: {count} ({count / total:.0%})")
```

## What the ledger is for

The raw count is less useful than the ratio of `caught_by` values over
time. A rising share of `tool` (an automated check caught it before
anyone had to notice) means your mechanisms are working. A stubborn share
of `user` means a human is still the safety net, no matter how good the
mistake count looks in isolation. Track that ratio, not just the total.

## What this builds on

This is standard incident tracking and blameless postmortem practice
(record what happened, categorize it, track who caught it and how)
applied to an agent's own output instead of a production outage. Nothing
new in the approach. What's less common is applying it
specifically to a coding agent's self-generated errors, where the natural
temptation is to just fix the code and move on without writing anything
down.

## Limits to understand before using this

**This only works if writing a record is actually mandatory when a
mistake is caught.** If it's a "nice to have, if you remember," it'll be
the first thing skipped exactly when things are going wrong, which is
also when the data matters most.

**A closed `kind` vocabulary needs someone maintaining it.** If a real
mistake doesn't fit any existing kind, that's a signal to add a kind on
purpose, not to force-fit it into the nearest one and quietly erode what
that category means.

**Concurrent appenders need a real atomic-append guarantee.** More than one
agent writing to a single JSONL file can interleave or tear lines. The
reference `ledger.py` takes an exclusive `flock` around a single-`write()`
append, which is enough on a local POSIX filesystem; a network filesystem
where `flock` is unreliable, or higher write volume, is a signal to move to a
storage backend with real atomic-append semantics (a database, an append-only
log service) rather than a shared file.

**The ledger measures what gets caught, not what doesn't.** A silent,
uncaught mistake never generates a record. Treat a very low count with
some suspicion: it might mean things are going well, or it might mean
your catching mechanisms have gaps. The ledger alone can't tell you
which.
