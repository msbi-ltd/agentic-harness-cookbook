#!/usr/bin/env python3
"""Numbered-record collision guardrail (ADR numbers, or any similarly numbered
file convention). Three-outcome exit codes: 0 clean, 1 a real collision found,
2 could-not-assess (a branch couldn't be read -- never silently dropped from
the comparison, since that would make the check pass while comparing against
fewer branches than it claims to)."""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

NUMBER_RE = re.compile(r"(\d{4})-")


@dataclass
class Claim:
    number: str
    source: str  # "local" or a branch/PR identifier
    path: str    # the specific file claiming this number


def local_claims(records_dir: str) -> list[Claim]:
    claims = []
    for path in sorted(Path(records_dir).glob("*.md")):
        m = NUMBER_RE.match(path.name)
        if m:
            claims.append(Claim(number=m.group(1), source="local", path=str(path)))
    return claims


def remote_claims(open_branches: list[str], records_dir: str) -> list[Claim] | None:
    """Returns None (not a verdict) if any branch's listing can't be read.
    Restricted to branches that exist in THIS repo's remote refs -- a PR's
    headRefName from a fork is not fetchable as a local ref and `git ls-tree
    <that name>` would resolve to nothing, or the wrong thing, if a branch of
    the same name also exists locally. Callers should pass only same-repo
    branch names; see the caller's docstring."""
    claims = []
    for branch in open_branches:
        try:
            out = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", branch, records_dir],
                capture_output=True, text=True, timeout=10, check=True,
            ).stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None  # couldn't read this branch; the whole check is unreliable
        for name in out.splitlines():
            m = re.match(r".*/(\d{4})-", name)
            if m:
                claims.append(Claim(number=m.group(1), source=branch, path=name))
    return claims


def evaluate(records_dir: str, open_branches: list[str]) -> int:
    remote = remote_claims(open_branches, records_dir)
    if remote is None:
        print("COULD NOT ASSESS: failed to read one or more open branches", file=sys.stderr)
        return 2

    all_claims = local_claims(records_dir) + remote

    # Group by number, then flag a collision if more than one distinct
    # (source, path) claims it. Keying on (source, path) -- not path alone --
    # catches two DIFFERENT branches that independently create the identical
    # path (docs/adr/0047-x.md on both): path alone would dedupe them to one
    # and miss the collision, even though two branches each claimed 0047. It
    # still catches two files in the same source (two local 0047- files).
    #
    # Caveat: this lists each branch's WHOLE docs/adr/ tree, so it can't tell a
    # file a branch introduced from a baseline file it merely inherited from
    # master -- two branches sharing an already-merged 0047 would read as a
    # false collision. The robust version compares each PR's CHANGED adr files
    # (against the base) using PR head SHAs, not locally-resolved branch names;
    # see the pattern doc. This is the cheap approximation.
    by_number: dict[str, list[Claim]] = {}
    for c in all_claims:
        by_number.setdefault(c.number, []).append(c)

    collisions = {
        number: claims for number, claims in by_number.items()
        if len({(c.source, c.path) for c in claims}) > 1
    }

    if collisions:
        for number, claims in sorted(collisions.items()):
            holders = ", ".join(f"{c.path} ({c.source})" for c in claims)
            print(f"FAIL: {number} claimed by multiple files: {holders}", file=sys.stderr)
        return 1

    print(f"PASS: {len(all_claims)} records, no collisions")
    return 0


if __name__ == "__main__":
    # python check_records.py <records_dir> <branch1> <branch2> ...
    # Pass only branches that exist in THIS repo (same-repo PRs). If your
    # repo accepts fork PRs, fetch each PR's headRefOid via the API instead
    # of relying on `git ls-tree <branch-name>` resolving locally.
    records_dir, branches = sys.argv[1], sys.argv[2:]
    sys.exit(evaluate(records_dir, branches))
