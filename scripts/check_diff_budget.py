#!/usr/bin/env python3
"""Diff-budget guardrail with a named, human-granted escape valve.

Checks BOTH net lines (additions - deletions) and churn (additions + deletions).
Net alone hides an equal-size rewrite: 1000 added, 1000 deleted nets to zero and
would slip through a net-only check even though it's a large, risky change.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

MAX_FILES = 15
MAX_NET_LINES = 500
MAX_CHURN_LINES = 1000
ESCAPE_LABEL = "oversize-approved"


def numstat_counts(base_ref: str) -> tuple[int, int, int]:
    """(files, additions, deletions) from `git diff --numstat`, robust to
    files with only additions or only deletions (numstat prints 0 there,
    but a binary file prints '-' for both, which int() would choke on --
    binary changes are counted as a file but contribute 0 to the line counts,
    since "how many lines changed" doesn't apply to them)."""
    out = subprocess.run(
        ["git", "diff", "--numstat", f"{base_ref}..."],
        capture_output=True, text=True, check=True,
    ).stdout
    files = additions = deletions = 0
    for line in out.splitlines():
        if not line.strip():
            continue
        files += 1
        add_s, del_s, _path = line.split("\t", 2)
        if add_s != "-":
            additions += int(add_s)
        if del_s != "-":
            deletions += int(del_s)
    return files, additions, deletions


def escape_grant(labels: list[str], granting_actor: str | None = None,
                 authorised_actors: set[str] | None = None) -> tuple[bool, str]:
    """Does the escape valve legitimately apply? The label alone is a weak
    signal: on its own it proves nothing about WHO applied it, and if the
    authoring agent can apply labels, an "exception" is just a self-serve
    bypass. So attribution is a required second control:

      - authorised_actors given + actor in it -> genuine human-granted exception
      - authorised_actors given + actor NOT in it -> label present but NOT a
        valid grant (the whole point of the check)
      - authorised_actors is None -> label present but UNVERIFIED; accepted, but
        the caller is responsible for ensuring, out of band (repo permissions),
        that the authoring identity cannot apply the label. Weaker; say so.
    """
    if ESCAPE_LABEL not in labels:
        return False, f"{ESCAPE_LABEL} label not applied"
    if authorised_actors is None:
        return True, f"{ESCAPE_LABEL} present (granting actor NOT verified — see docstring)"
    if granting_actor in authorised_actors:
        return True, f"{ESCAPE_LABEL} granted by authorised actor {granting_actor!r}"
    return False, (
        f"{ESCAPE_LABEL} present but granted by {granting_actor!r}, "
        f"who is not in the authorised set {sorted(authorised_actors)}"
    )


def evaluate_diff_budget(files: int, additions: int, deletions: int, labels: list[str],
                          max_files: int = MAX_FILES, max_net_lines: int = MAX_NET_LINES,
                          max_churn_lines: int = MAX_CHURN_LINES,
                          granting_actor: str | None = None,
                          authorised_actors: set[str] | None = None) -> tuple[bool, str]:
    net_lines = additions - deletions
    churn = additions + deletions
    over_budget = (
        files > max_files
        or abs(net_lines) > max_net_lines
        or churn > max_churn_lines
    )
    detail = f"{files} files, {net_lines} net lines, {churn} churn lines"
    if not over_budget:
        return True, f"within budget: {detail}"
    granted, why = escape_grant(labels, granting_actor, authorised_actors)
    if granted:
        return True, f"over budget ({detail}) but {why}"
    return False, (
        f"over budget: {detail} "
        f"(max {max_files} files, {max_net_lines} net lines, {max_churn_lines} churn lines); "
        f"{why}. Split the PR, or get an authorised {ESCAPE_LABEL} grant"
    )


if __name__ == "__main__":
    # python check_diff_budget.py <base_ref> '<json labels list>'
    # Optional attribution, from the label event, via env:
    #   LABEL_ACTOR         -- who applied the label (github.event.sender.login)
    #   AUTHORISED_APPROVERS-- comma-separated logins allowed to grant it
    # With AUTHORISED_APPROVERS unset, the label is accepted but flagged
    # unverified (weaker mode); see escape_grant.
    base_ref, labels = sys.argv[1], json.loads(sys.argv[2])
    actor = os.environ.get("LABEL_ACTOR") or None
    raw_auth = os.environ.get("AUTHORISED_APPROVERS", "").strip()
    authorised = {a.strip() for a in raw_auth.split(",") if a.strip()} or None
    files, additions, deletions = numstat_counts(base_ref)
    ok, detail = evaluate_diff_budget(
        files, additions, deletions, labels,
        granting_actor=actor, authorised_actors=authorised,
    )
    print(detail)
    sys.exit(0 if ok else 1)
