# Pattern: review evidence bound to a commit, not a PR

> **Status:** Reference implementation · **Last verified:** 2026-08-31  
> **Tested against:** `scripts/check_review_evidence.py` (`tests/test_check_review_evidence.py`)  
> **Enforcement:** CI required check on `pull_request` + `pull_request_review` (or native stale-review dismissal)  
> **Reference implementation:** `scripts/check_review_evidence.py`

## Problem

A pull request is approved, then someone pushes one more commit: a quick fix, a
rebase or a generated-file update. A gate that asks only “does this PR have an
approval?” still says yes, even though the approved code is no longer the code
that will merge.

> **Use GitHub's native control when it fits.** “Dismiss stale pull request
> approvals when new commits are pushed” handles normal GitHub reviews with less
> custom code. Use the check below for signals GitHub cannot dismiss for you,
> such as a bot verdict or required status, or when the gate must trust one
> specific reviewer identity.

## How it works

Check the review against the PR's **current head commit SHA**, not just
its existence:

1. When a review is submitted (an approval, or an equivalent signal like a
   specific reaction on a specific comment), record the commit SHA that
   was checked out at that moment. Most code-hosting APIs expose this
   directly: GitHub's review objects carry a `commit_id`.
2. At merge-gate time, read the PR's **current** head SHA, and check
   whether there's an accepted review whose recorded SHA matches it
   exactly.
3. If the head SHA has moved since the last accepted review (a new commit
   landed), there is no valid evidence for the current code. The gate
   fails, even though a review "exists" on the PR.

This is `check_review_evidence.py` (full, tested version in
[`scripts/check_review_evidence.py`](../scripts/check_review_evidence.py)).
The evaluator works on a normalised `Verdict` (identity, state, commit_id,
submitted_at), so it's testable against fixtures shaped like the real API —
and so a **non-native** verdict (a reviewer App's check-run, a recorded
verdict artifact) can be fed in the same shape as a GitHub review. Three
things must all hold: the verdict is APPROVED, it's bound to the current head
SHA, and it comes from an **authorised identity** — and it must be that
identity's *latest* verdict, so a later "changes requested" revokes an
earlier approval:

```python
# scripts/check_review_evidence.py (core; see the file for fetch/CLI plumbing)
def has_valid_review(verdicts: list[Verdict], head_sha: str, authorised: set[str]) -> bool:
    """True iff some AUTHORISED identity's LATEST verdict is APPROVED and bound
    to head_sha."""
    for v in latest_per_identity(verdicts, authorised).values():
        if v.state == "APPROVED" and v.commit_id == head_sha:
            return True
    return False

def evaluate(verdicts, head_sha, authorised) -> tuple[int, str]:
    if not head_sha:
        return 2, "no head SHA to bind evidence to"               # could-not-assess
    if not authorised:
        return 2, "no authorised reviewer identities configured"  # could-not-assess
    if has_valid_review(verdicts, head_sha, authorised):
        return 0, f"authorised approval bound to head {head_sha[:12]}"
    return 1, f"no authorised approval bound to current head {head_sha[:12]}"
```

**Get `commit_id` from the REST reviews endpoint, not `gh pr view`.**
`gh pr view --json reviews` does not reliably expose each review's
`commit_id`
([cli/cli#6615](https://github.com/cli/cli/discussions/6615)), and the head
binding is the entire point. The reference implementation reads the head SHA
with `gh pr view --json headRefOid` and the reviews from
`gh api repos/{repo}/pulls/{n}/reviews`, which carries `commit_id`,
`state`, `user.login`, and `submitted_at`. Its tests run against a fixture
shaped exactly like that REST response
([`tests/fixtures/reviews_rest_response.json`](../tests/fixtures/reviews_rest_response.json)),
because a unit test against a hand-invented dict can't catch an API-shape
mismatch. The `authorised` set is the reviewer identity (or identities) you
trust — pair this with the [reviewer-isolation
pattern](reviewer-isolation.md), whose isolated App is exactly such an
identity, publishing the verdict this check then binds to a SHA.

The ordering matters in practice: any automated step that could change
the head commit (a rebase, an auto-formatter, a merge-conflict
resolution) must run **before** you ask for review, not after. Running it
after invalidates the review you just got, by design, which is the whole
point.

## Where this runs

Save the script above as `scripts/check_review_evidence.py`, and put the
check in the merge gate itself, not somewhere a reviewer has to remember
to look:

```yaml
# .github/workflows/merge-gate.yml
on:
  pull_request:
    types: [opened, synchronize, reopened]
  pull_request_review:
    types: [submitted]
jobs:
  review-binding:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: read
    steps:
      - uses: actions/checkout@v4
      - env:
          GH_TOKEN: ${{ github.token }}
          PR: ${{ github.event.pull_request.number }}
        # args: <owner/repo> <pr_number> <authorised-reviewer-login>...
        run: python scripts/check_review_evidence.py "$GITHUB_REPOSITORY" "$PR" "reviewer-bot[bot]"
```

Two triggers matter, not one: `pull_request_review` catches a fresh
approval, and `synchronize` (a new commit pushed) is what re-runs the
check against the now-stale review and turns the gate red again. A check
that only runs on the review event will miss the exact moment, a later
push, that this pattern exists to catch.

## What this builds on

This is the same idea as a code-signing system checking a signature
against the exact artifact hash, not just "is there a signature on file
somewhere for this project." Binding an approval to specific content,
rather than to a mutable container that content lives inside, is standard
practice anywhere a signature or approval needs to mean something
specific. The PR-level version (checking only "is there an approval") is
the common shortcut, and it's the one that's actually wrong.

## Limits to understand before using this

**This adds friction on purpose.** Every push after an approval, even a
trivial whitespace fix, invalidates that approval and requires a new one.
That is the correct behaviour for a control that is supposed to mean
something, but it will surprise people used to PR-level "approved" status
staying green through small follow-up pushes. Say this plainly to
reviewers up front, or you'll get bug reports about a "broken" check that
is in fact working exactly as designed.

**It depends on the platform actually recording a commit SHA per review.**
Not every code-hosting API does this consistently for every kind of
approval signal (a formal review versus a comment reaction, for example).
Check what your platform actually gives you before assuming this binding
is available for free.

**A force-push can change the head SHA without changing the meaningful
content.** An interactive rebase that only reorders commits, or a
squash that doesn't change the diff, still produces a new SHA and still
invalidates the review under this rule. That's a real cost of the
pattern, not a bug in it: the alternative (trying to detect "meaningfully
unchanged" automatically) is its own, much harder problem, and getting it
wrong reopens the exact gap this pattern closes.
