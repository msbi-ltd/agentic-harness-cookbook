#!/usr/bin/env python3
"""Append-only mistake ledger: one line per recorded mistake, JSONL.

The point of the ledger is the `caught_by` field — it's what lets you ask "are
our own automated checks catching mistakes, or is the human always the backstop?"
A record with an invalid kind or caught_by is worse than no record: it silently
drops out of that tally. So this validates on write and refuses a bad record
rather than storing something un-countable.

Store path is `MISTAKE_LEDGER_PATH` if set, else a fixed shared location OUTSIDE
any throwaway agent workspace — a ledger that lives inside a worktree dies with
the worktree, taking the evidence with it.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl  # POSIX only
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

KINDS = (
    "unverified-claim",
    "fabricated-detail",
    "premise-not-checked",
    "process-step-skipped",
    "wrong-diagnosis",
)
CAUGHT_BY = ("tool", "agent", "user", "self")


def ledger_path() -> Path:
    return Path(os.environ.get("MISTAKE_LEDGER_PATH", "/var/lib/agent-harness/mistake-ledger.jsonl"))


@dataclass
class MistakeRecord:
    occurred_at: str          # RFC 3339 with a timezone
    kind: str                 # one of KINDS
    caught_by: str            # one of CAUGHT_BY
    summary: str              # required: an uncountable mistake can't be audited
    corrected: bool | None = None    # None = "not measured", never False-by-default
    correction_ref: str = ""

    def validate(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"kind {self.kind!r} not in {KINDS}")
        if self.caught_by not in CAUGHT_BY:
            raise ValueError(f"caught_by {self.caught_by!r} not in {CAUGHT_BY}")
        if not self.summary.strip():
            raise ValueError("summary is required and cannot be blank")


def append_record(record: MistakeRecord, path: Path | None = None) -> None:
    """Append one JSONL record. Multiple agents may append to the same ledger
    concurrently, so the write is taken under an exclusive advisory lock and
    the line is written in a single write() call. A short JSONL line written in
    one write() under flock won't interleave with another appender's line."""
    record.validate()
    dest = path or ledger_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(record)) + "\n"
    with dest.open("a") as f:
        if fcntl is not None:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(line)
        finally:
            if fcntl is not None:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def report(path: Path | None = None) -> dict[str, int]:
    """Who caught our mistakes? Returns the caught_by tally."""
    src = path or ledger_path()
    if not src.exists():
        return {}
    records = [json.loads(line) for line in src.read_text().splitlines() if line.strip()]
    return dict(Counter(r["caught_by"] for r in records))


if __name__ == "__main__":
    # python ledger.py record <kind> <caught_by> "<summary>"
    # python ledger.py report
    if len(sys.argv) >= 2 and sys.argv[1] == "report":
        tally = report()
        total = sum(tally.values())
        for who, count in sorted(tally.items(), key=lambda kv: -kv[1]):
            share = f"{count / total:.0%}" if total else "0%"
            print(f"{who}: {count} ({share})")
        sys.exit(0)

    # default/`record` form
    args = sys.argv[2:] if sys.argv[1:2] == ["record"] else sys.argv[1:]
    try:
        kind, caught_by, summary = args[0], args[1], args[2]
        rec = MistakeRecord(
            occurred_at=datetime.now(timezone.utc).isoformat(),
            kind=kind,
            caught_by=caught_by,
            summary=summary,
        )
        append_record(rec)
    except (IndexError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        print('usage: ledger.py record <kind> <caught_by> "<summary>" | ledger.py report',
              file=sys.stderr)
        sys.exit(2)
