#!/usr/bin/env python3
"""Deadline-based heartbeat store: a subagent reports a DUE time, not a
timestamp. A missed beat is then a fact ("it promised a beat by 14:15 and it's
14:20") rather than a guess ("we haven't heard from it, is that bad?").

A subagent is an LLM driving a shell, not a Python process that can import a
function, so this is a runnable CLI first and a library second. Store path is
`BEATS_DIR` if set, else a fixed shared location OUTSIDE any one agent's
workspace — a beat inside a throwaway worktree dies with it.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# The caller is an LLM agent, so task_id is effectively untrusted input. Without
# this, an id like "../../etc/whatever" would escape the beat directory when
# used as a filename. Narrow, filename-safe format only.
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def _safe(task_id: str) -> str:
    if not _TASK_ID_RE.match(task_id):
        raise ValueError(
            f"invalid task_id {task_id!r}: must match {_TASK_ID_RE.pattern}"
        )
    return task_id


def store_dir() -> Path:
    return Path(os.environ.get("BEATS_DIR", "/var/lib/agent-harness/beats"))


def _atomic_write(path: Path, record: dict) -> None:
    """Write to a temp file in the same dir, then os.replace() into place, so a
    supervisor reading concurrently never sees a half-written beat (which is
    exactly when the liveness check matters most). Replace is atomic on POSIX
    within one filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(record))
    os.replace(tmp, path)


def report(task_id: str, due_in_seconds: int, doing: str, now: float | None = None) -> None:
    """First and last action of every work round; again before anything long,
    with a due time sized to that step."""
    now = time.time() if now is None else now
    _atomic_write(
        store_dir() / f"{_safe(task_id)}.json",
        {
            "task_id": task_id,
            "state": "working",
            "stamped_at": int(now),
            "due_at": int(now) + due_in_seconds,
            "doing": doing,
        },
    )


def done(task_id: str, now: float | None = None) -> None:
    now = time.time() if now is None else now
    _atomic_write(
        store_dir() / f"{_safe(task_id)}.json",
        {"task_id": task_id, "state": "done", "stamped_at": int(now)},
    )


def check(task_id: str, now: float | None = None) -> str:
    """Run by the orchestrator, not the subagent."""
    now = time.time() if now is None else now
    path = store_dir() / f"{_safe(task_id)}.json"
    if not path.exists():
        return "unknown: no beat has ever been recorded for this task"
    try:
        record = json.loads(path.read_text())
    except (json.JSONDecodeError, ValueError):
        # A torn/partial write. Don't crash the liveness check on it: report
        # unknown and let the next beat (or the mtime backstop) settle it.
        return "unknown: beat record is unreadable (partial write?), check again shortly"
    if record.get("state") == "done":
        return "done: no further beat expected"
    if now > record["due_at"]:
        return f'overdue: last said "{record["doing"]}" and promised a beat that has now passed'
    return f'on-time: "{record["doing"]}"'


if __name__ == "__main__":
    # python beats.py report <task_id> <due_in_seconds> "<doing>"
    # python beats.py done   <task_id>
    # python beats.py check  <task_id>
    cmd, task_id = sys.argv[1], sys.argv[2]
    if cmd == "report":
        report(task_id, int(sys.argv[3]), sys.argv[4])
    elif cmd == "done":
        done(task_id)
    elif cmd == "check":
        print(check(task_id))
    else:
        print(f"unknown command {cmd!r}", file=sys.stderr)
        sys.exit(2)
