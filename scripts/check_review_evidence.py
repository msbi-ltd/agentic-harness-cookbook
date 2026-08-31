#!/usr/bin/env python3
"""Merge gate: require an approval that is bound to the PR's CURRENT head
commit AND comes from a specific authorised reviewer identity.

This is deliberately MORE than GitHub's native "dismiss stale approvals on
push" toggle, because that toggle can't do two things this gate needs:

  1. bind the verdict to a *specific identity* (a reviewer App / bot / a named
     set of humans), not "any collaborator who can approve"; and
  2. accept a *non-native* verdict — a signal that isn't a GitHub review at
     all (a reviewer App publishing a check run, a recorded verdict artifact).

So the evaluator works on a normalised `Verdict` (identity, state, sha,
submitted_at). Native GitHub reviews map into `Verdict`s; a non-native source
can produce them too (see `verdicts_from_reviews` and the docstring on
`evaluate`). The rule then is: among AUTHORISED identities only, take each
identity's LATEST verdict, and pass only if that latest verdict is APPROVED and
bound to the current head SHA. A stale approval, an approval from an
unauthorised identity, or a later CHANGES_REQUESTED all correctly fail.

Three-outcome contract: 0 an authorised, head-bound approval exists; 1 none
does; 2 could-not-assess (couldn't read head SHA or reviews).

Note on the API: `gh pr view --json reviews` does NOT reliably expose each
review's `commit_id`. The head-SHA binding is the whole point, so this reads
reviews from the REST endpoint `repos/{repo}/pulls/{n}/reviews`, which does.
See https://github.com/cli/cli/discussions/6615.
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass

VERDICT_EXIT = 1
COULD_NOT_ASSESS_EXIT = 2


@dataclass(frozen=True)
class Verdict:
    identity: str        # reviewer login, e.g. "reviewer-bot[bot]" or a human login
    state: str           # APPROVED | CHANGES_REQUESTED | COMMENTED | ...
    commit_id: str       # the head SHA this verdict was made against
    submitted_at: str    # RFC 3339; orders two verdicts from the same identity


class Unassessable(Exception):
    """Couldn't gather the evidence — could-not-assess, not a verdict."""


def _run_json(args: list[str]) -> object:
    try:
        out = subprocess.run(
            args, capture_output=True, text=True, check=True, timeout=30
        ).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise Unassessable(f"{' '.join(args[:3])}…: {exc}") from exc
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise Unassessable(f"unparseable response from {' '.join(args[:3])}…: {exc}") from exc


def fetch_head_sha(repo: str, pr_number: str) -> str:
    data = _run_json(["gh", "pr", "view", pr_number, "--repo", repo, "--json", "headRefOid"])
    sha = data.get("headRefOid") if isinstance(data, dict) else None
    if not sha:
        raise Unassessable(f"no headRefOid for PR {pr_number}")
    return sha


def fetch_reviews(repo: str, pr_number: str) -> list[dict]:
    # REST paginates; --paginate flattens. Each item has user.login, state,
    # commit_id, submitted_at.
    data = _run_json(
        ["gh", "api", "--paginate", f"repos/{repo}/pulls/{pr_number}/reviews"]
    )
    if not isinstance(data, list):
        raise Unassessable("reviews endpoint did not return a list")
    return data


def verdicts_from_reviews(reviews: list[dict]) -> list[Verdict]:
    """Map GitHub's REST review objects into normalised Verdicts. A review with
    no commit_id (some historical/edge cases) is kept with an empty sha, which
    can never match a real head SHA — so it fails safe rather than being
    silently dropped."""
    out = []
    for r in reviews:
        user = (r.get("user") or {}).get("login", "")
        out.append(
            Verdict(
                identity=user,
                state=r.get("state", ""),
                commit_id=r.get("commit_id") or "",
                submitted_at=r.get("submitted_at") or "",
            )
        )
    return out


def latest_per_identity(verdicts: list[Verdict], authorised: set[str]) -> dict[str, Verdict]:
    """For each AUTHORISED identity, its most recent verdict (by submitted_at).
    An identity with no verdict simply doesn't appear."""
    latest: dict[str, Verdict] = {}
    for v in verdicts:
        if v.identity not in authorised:
            continue
        prev = latest.get(v.identity)
        if prev is None or v.submitted_at > prev.submitted_at:
            latest[v.identity] = v
    return latest


def has_valid_review(verdicts: list[Verdict], head_sha: str, authorised: set[str]) -> bool:
    """True iff some authorised identity's LATEST verdict is APPROVED and bound
    to head_sha. A later non-approval from the same identity revokes it."""
    for v in latest_per_identity(verdicts, authorised).values():
        if v.state == "APPROVED" and v.commit_id == head_sha:
            return True
    return False


def evaluate(verdicts: list[Verdict], head_sha: str, authorised: set[str]) -> tuple[int, str]:
    """Pure gate logic — no IO, so it's testable against fixtures shaped like
    the real API. `verdicts` may include non-native ones from any source."""
    if not head_sha:
        return COULD_NOT_ASSESS_EXIT, "no head SHA to bind evidence to"
    if not authorised:
        return COULD_NOT_ASSESS_EXIT, "no authorised reviewer identities configured"
    if has_valid_review(verdicts, head_sha, authorised):
        return 0, f"authorised approval bound to head {head_sha[:12]}"
    return VERDICT_EXIT, (
        f"no authorised approval bound to current head {head_sha[:12]} "
        f"(authorised: {sorted(authorised)})"
    )


if __name__ == "__main__":
    # python check_review_evidence.py <owner/repo> <pr_number> <authorised-login>...
    try:
        repo, pr_number, authorised = sys.argv[1], sys.argv[2], set(sys.argv[3:])
        head = fetch_head_sha(repo, pr_number)
        verdicts = verdicts_from_reviews(fetch_reviews(repo, pr_number))
    except Unassessable as exc:
        print(f"COULD NOT ASSESS: {exc}", file=sys.stderr)
        sys.exit(COULD_NOT_ASSESS_EXIT)
    except IndexError:
        print("usage: check_review_evidence.py <owner/repo> <pr_number> <authorised-login>...",
              file=sys.stderr)
        sys.exit(COULD_NOT_ASSESS_EXIT)
    code, detail = evaluate(verdicts, head, authorised)
    print(detail, file=sys.stderr if code else sys.stdout)
    sys.exit(code)
