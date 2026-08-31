# Pattern: diff budget with a named escape valve

> **Status:** Reference implementation · **Last verified:** 2026-08-31  
> **Tested against:** `scripts/check_diff_budget.py` (`tests/test_check_diff_budget.py`)  
> **Enforcement:** CI check on every PR (required status check to actually gate)  
> **Reference implementation:** `scripts/check_diff_budget.py`

## Problem

A PR-size limit stops a small task from quietly becoming a large rewrite. A rule
such as “no more than 500 net lines or 15 files” is useful until a genuinely
large change appears.

If the limit has no controlled exception, someone will eventually raise it or
disable the check. The one difficult change then weakens the rule for every
future change. The better design keeps the limit and provides one visible,
authorised way around it.

## How it works

Keep the hard limit, but give it exactly one way through: a named,
logged, human-granted exception, not a config change.

1. The check reads the PR's file and line-change counts and fails if
   they're over budget.
2. A specific, visible label (something like `oversize-approved`) lets
   the same PR pass despite being over budget — but the label is only a
   *label-granted* exception, and a label on its own proves nothing about
   **who** applied it. If the authoring agent can add labels, the "exception"
   is just a self-serve bypass. So the label needs a second control:
   **attribution.** Either verify the actor who applied the label against an
   authorised set (the reference script does this — see `escape_grant`), or
   guarantee out of band, through repo permissions, that the authoring
   identity cannot apply the label at all. The label alone is the weak
   version; the label plus verified human attribution is the control.
3. Every time the exception is used, that's a fact worth recording, not just
   a check that silently passes. Log which PR, **who** granted it, and why,
   the same way you'd log any other exception to a rule.

This is `check_diff_budget.py` (the full, tested version is in
[`scripts/check_diff_budget.py`](../scripts/check_diff_budget.py); the gate
logic is reproduced here). Note it checks **both** net lines *and* churn:

```python
# scripts/check_diff_budget.py (gate logic; see the file for the git plumbing)
def evaluate_diff_budget(files: int, additions: int, deletions: int, labels: list[str],
                          max_files: int = 15, max_net_lines: int = 500,
                          max_churn_lines: int = 1000,
                          granting_actor: str | None = None,
                          authorised_actors: set[str] | None = None) -> tuple[bool, str]:
    net_lines = additions - deletions
    churn = additions + deletions
    over_budget = (
        files > max_files
        or abs(net_lines) > max_net_lines   # abs: a big pure DELETION is also large
        or churn > max_churn_lines          # churn: an equal add/delete rewrite nets to ~0
    )
    detail = f"{files} files, {net_lines} net lines, {churn} churn lines"
    if not over_budget:
        return True, f"within budget: {detail}"
    # escape_grant checks the label AND, when an authorised-actor set is given,
    # who applied it. With no authorised set it accepts the label but flags it
    # as unverified -- a documented weaker mode, not a silent pass.
    granted, why = escape_grant(labels, granting_actor, authorised_actors)
    return (True, f"over budget ({detail}) but {why}") if granted else \
        (False, f"over budget: {detail}. {why}. Split the PR, or get an authorised grant")
```

Two things this gets right that a naive version doesn't. **Net alone hides
an equal-size rewrite**: 1000 added and 1000 deleted nets to zero and would
slip a `net > 500` check even though it's a large, risky diff — so the gate
also caps *churn* (additions + deletions). And the counts come from
`git diff --numstat` parsed per-file (see the script), not from
`--shortstat` piped through `awk '{print $4-$6}'` — that awk trick silently
produces the wrong number when a diff has only additions or only deletions
(shortstat omits the missing half, so the fields shift), and chokes on
binary files, which numstat marks with `-`.

A useful refinement, already in the script: split the count into "product
code" and "everything else" (tests, generated files, documentation), and
budget only the product-code half. A PR that adds 40 lines of source and
600 lines of tests for it shouldn't need an exception; a PR that adds 600
lines of source genuinely should.

## Where this runs

The script lives at `scripts/check_diff_budget.py`. Wire it into a CI job
that runs on every pull request — including when a label is added or
removed, which the default `pull_request` trigger does **not** cover:

```yaml
# .github/workflows/diff-budget.yml
on:
  pull_request:
    # opened/synchronize/reopened are the defaults; labeled/unlabeled are NOT,
    # and without them the job never re-runs when oversize-approved is applied.
    types: [opened, synchronize, reopened, labeled, unlabeled]
jobs:
  diff-budget:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - env:
          BASE: origin/${{ github.base_ref }}
          LABELS: ${{ toJson(github.event.pull_request.labels.*.name) }}
          # Attribution: who applied the label on THIS event, and who's allowed
          # to. With AUTHORISED_APPROVERS unset the label is accepted but
          # flagged unverified. github.event.sender is who triggered the event.
          LABEL_ACTOR: ${{ github.event.sender.login }}
          AUTHORISED_APPROVERS: "alice,bob"   # your maintainers
        run: python scripts/check_diff_budget.py "$BASE" "$LABELS"
```

The `types:` line is critical. `oversize-approved` is normally added
*after* the PR is open; with the default trigger set, applying the label
emits a `labeled` event that starts no run at all, so the PR stays red on a
check that would now pass. Listing `labeled`/`unlabeled` is what makes the
escape valve actually take effect. (Untrusted event data — labels, base ref
— is passed through `env:`, not interpolated into the shell line, so a
crafted branch or label name can't inject a command.)

## What this builds on

This is the same shape as a spending limit with an approval workflow for
exceptions (a purchase order over a threshold needs a named sign-off, not
a blanket policy change), or a linter's inline suppression comment that's
grep-able and requires a reason. The general idea, a rule with exactly one
visible, attributable way around it, is common wherever a hard rule would
otherwise get quietly eroded the first time it's inconvenient.

## Limits to understand before using this

**The exception must require a specific human action, not something the
agent under review can trigger itself.** If the same identity that's
opening the oversize PR can also apply the exception label, the escape
valve is not an exception process, it's just a bypass with extra steps.

**Track how often the exception is used.** If `oversize-approved` shows
up on every third PR, the limit itself is probably wrong for this
project, and the fix is to reconsider the number, not to keep granting
exceptions indefinitely. A rising exception rate is a signal, not noise.

**Splitting "product code" from "everything else" needs a real
definition, kept up to date.** If tests or generated files start counting
against the product budget because the split logic didn't account for a
new file pattern, you get false positives that teach people to reach for
the exception label reflexively instead of actually checking whether the
PR's real scope grew.
