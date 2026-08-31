# Pattern: deadline-based heartbeat protocol

> **Status:** Reference implementation · **Last verified:** 2026-08-31  
> **Tested against:** `scripts/beats.py` (`tests/test_beats.py`)  
> **Enforcement:** Worker-liveness convention + supervisor/controller check; **not workflow durability**  
> **Reference implementation:** `scripts/beats.py`

## Problem

When an orchestrator dispatches a long-running subagent, one that might take minutes working through a multi-step task, it needs to know whether that worker has silently stalled. A fixed poll interval cannot distinguish "quiet because stuck" from "quiet because legitimately busy."

The useful question is narrower than it first appears:

> **Is this worker still plausibly executing the task it currently owns?**

A heartbeat should answer that question. It should **not** be responsible for answering a different one:

> **Will the overall workflow eventually continue?**

That second property is workflow durability and belongs to a durable controller or workflow engine, not to the worker that happens to be running one step.

Polling every few seconds is noisy and wasteful, but a fixed timeout is not much
better. Five minutes of silence could mean a dead process, a blocked tool call,
or a valid step that simply takes six minutes. Silence alone does not tell the
orchestrator which one happened.

## How it works

Have each worker report a **deadline, not merely a timestamp**. It does not say "I last checked in at 14:02." It says "I expect to report again by 14:15, or sooner if something long-running starts."

1. On dispatch, and again at the end of every work round, the worker reports `--next-in=<duration>` and a short description of what it is doing.
2. Before a genuinely long operation, the worker extends the deadline first, sized to that operation.
3. On completion, it reports `done`.
4. A deterministic supervisor/controller reads those deadlines and treats a missed deadline as a reason to inspect or reclaim the work.

This is lease-like reasoning: the worker holds work for a bounded period and renews that claim while it remains active.

## The load-bearing boundary: heartbeat is not workflow durability

A healthy heartbeat only tells you about the **current worker**. It must never be the mechanism that makes the **next workflow transition** happen.

Bad shape:

```text
worker
  -> reports heartbeat
  -> starts CI
  -> waits for CI
  -> session reaches a completion boundary
  -> never re-enters

heartbeat was healthy
workflow still stalled
```

Nothing is wrong with the heartbeat there. The architecture failed because continuation depended on re-entering the same conversational session.

Preferred shape:

```text
controller: task = FULL_CI_RUNNING, run_id = 12345
                     |
                     v
                   GitHub
                     |
                   complete
                     |
                     v
controller: task = REVIEW_FIX
                     |
                     v
              dispatch any worker
```

The original worker can disappear after starting CI. Durable state, not conversational continuity, determines what happens next.

**Rule:** use heartbeats to renew or diagnose a worker lease. Persist workflow state separately and let deterministic software decide the next transition.

See [Durable controller, disposable agent workers](durable-controller-agent-workers.md).

## Where this lives

Three pieces, each in a different place:

1. **A shared store outside any worker workspace.** A fixed directory, small database table or key-value store is sufficient. One record per task or lease.
2. **The report call in worker instructions.** It should be a required first/last action for the bounded worker invocation, not an optional courtesy.
3. **A deterministic check in the controller/supervisor.** The worker never evaluates its own liveness.

The shared store is important because the record must outlive the worker and its worktree.

## Minimal reference implementation

The worker is an LLM using a shell tool, not a Python process that can import a function. The example is therefore a runnable CLI as well as a library. It illustrates the approach; do not paste it into production unchanged.

```python
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

STORE_DIR = Path("/var/lib/myagent/beats")
TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _path(task_id: str) -> Path:
    if not TASK_ID.fullmatch(task_id):
        raise ValueError("invalid task id")
    return STORE_DIR / f"{task_id}.json"


def _atomic_write(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(record, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def report(task_id: str, due_in_seconds: int, doing: str) -> None:
    now = int(time.time())
    _atomic_write(_path(task_id), {
        "task_id": task_id,
        "state": "working",
        "stamped_at": now,
        "due_at": now + due_in_seconds,
        "doing": doing,
    })


def done(task_id: str) -> None:
    _atomic_write(_path(task_id), {
        "task_id": task_id,
        "state": "done",
        "stamped_at": int(time.time()),
    })


def check(task_id: str) -> str:
    path = _path(task_id)
    if not path.exists():
        return "unknown: no beat has ever been recorded"
    try:
        record = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return "unknown: beat record unreadable"
    if record.get("state") == "done":
        return "done"
    if time.time() > record.get("due_at", 0):
        return f"overdue: {record.get('doing', 'unknown work')}"
    return f"on-time: {record.get('doing', 'working')}"
```

In a worker instruction:

```markdown
Run `python beats.py report <task_id> <due_in_seconds> "<doing>"` as the
first action of this bounded work invocation. Extend it before a long-running
operation. Run `python beats.py done <task_id>` when this invocation finishes.
Do not wait for later workflow stages merely to keep the heartbeat alive; return
control to the controller when your assigned transition is complete.
```

## Using the heartbeat as a lease

For autonomous execution, the strongest use is to combine the heartbeat with explicit work ownership:

```text
task: 1665
state: IMPLEMENTING
worker_id: claude-xyz
lease_expires: 21:42
```

The worker renews `lease_expires` through its heartbeat. If the lease expires, the controller may inspect, mark the attempt lost and dispatch a replacement. The next worker does not need the previous conversation's memory; it receives the durable task state and repository state.

That is a stronger model than trying to prove that a particular chat session is alive.

## Parallel workers

The protocol naturally supports many workers at once because records are keyed by task/lease rather than by one global orchestrator session:

```text
controller
  |- task A -> worker 1 -> lease A
  |- task B -> worker 2 -> lease B
  |- task C -> reviewer -> lease C
  `- task D -> worker 4 -> lease D
```

The controller can reclaim one expired lease without disturbing healthy work on the others.

## Prior art

Deadline-based liveness and renewable leases are standard distributed-systems mechanisms: leader-election leases, distributed locks and service heartbeats all use the absence of timely renewal as evidence that ownership may have been lost.

For an LLM worker, the lease describes a bounded invocation whose runtime is
unpredictable.

## Limits to understand before using this

**The worker can forget or fail to renew.** A missed beat means "inspect/reclaim according to policy," not necessarily "the worker process is dead." The controller should be conservative about destructive termination.

**The heartbeat does not prove useful progress.** A worker can keep renewing while looping uselessly. Pair liveness with bounded task attempts, progress evidence, token/time budgets, or transition-specific acceptance criteria.

**The heartbeat must not become a hidden scheduler.** Do not encode "when this deadline expires, re-enter the same conversation and hope it continues." Expiry should return control to deterministic orchestration.

**Nothing-to-report rounds still matter only while the worker owns work.** A worker intentionally waiting on external CI should normally relinquish the transition rather than keep renewing forever. The controller should own `WAITING_FOR_CI` as durable state.

**Treat task IDs and concurrent writes as untrusted.** Validate IDs before mapping them to file paths and write atomically. An unreadable record is `unknown`, never a healthy pass.

**A heartbeat is evidence, not authority.** The controller decides what an overdue lease means. The agent that writes the heartbeat must not also be the sole judge of whether its own missed beat should be ignored.
