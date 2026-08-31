# Pattern: three-outcome contract for guardrail scripts

> **Status:** Reference implementation · **Last verified:** 2026-08-31  
> **Tested against:** `scripts/check_records.py` (`tests/test_check_records.py`)  
> **Enforcement:** Convention applied per guardrail: 0 clean / 1 verdict / 2 could-not-assess  
> **Reference implementation:** `scripts/check_records.py` (worked example)

## Problem

Most scripts and CI checks return pass or fail. That works when the script can
actually decide between the two.

Sometimes it cannot: an API times out, a required file is unavailable, or the
state is incomplete. Reporting that as a pass hides a gap. Reporting it as a
normal failure creates a false alarm. The script needs a third result:
**could not assess**.

## How it works

Give every guardrail script three possible exit codes, not two, and treat
the third one as seriously as a failure:

- **0**: checked, and it's clean.
- **1**: checked, and it's a verdict, something is actually wrong.
- **2**: could not be checked. Missing data, an unreadable file, an API
  that didn't respond, a state too ambiguous to score. **Never reported
  as 0.**

```python
def check_something() -> int:
    try:
        data = load_state()
    except (FileNotFoundError, TimeoutError) as exc:
        print(f"COULD NOT ASSESS: {exc}", file=sys.stderr)
        return 2  # never silently pass here

    if not data:
        print("COULD NOT ASSESS: no data to evaluate", file=sys.stderr)
        return 2

    if data.is_broken():
        print(f"FAIL: {data.reason}", file=sys.stderr)
        return 1

    print("PASS: clean")
    return 0
```

The part that actually matters is what calls this script do with exit
code 2. A CI pipeline that treats "2" the same as "0" (both are "green,"
functionally) has silently rebuilt the two-outcome problem one layer up.
Wire could-not-assess to block or flag the same way a failure would, or
at minimum surface it distinctly, never fold it into a pass.

## A real example

Here's a scrubbed, condensed version of an actual guardrail built this
way: a check that catches two decision-record files being numbered the
same by two different branches, something a single branch's own git
history can never see, because each branch only knows its own commits.
This is the general form of the ADR number-collision check described in
[adr-management.md](adr-management.md) — the same script, applied to
whatever kind of numbered record file your project keeps.

This is `check_records.py` (full, tested version in
[`scripts/check_records.py`](../scripts/check_records.py)):

```python
# scripts/check_records.py
import re
import subprocess
import sys
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Claim:
    number: str
    source: str   # "local" or a branch/PR identifier
    path: str     # the specific file claiming this number

def local_claims(records_dir: str) -> list[Claim]:
    claims = []
    for path in sorted(Path(records_dir).glob("*.md")):
        m = re.match(r"(\d{4})-", path.name)
        if m:
            claims.append(Claim(number=m.group(1), source="local", path=str(path)))
    return claims

def remote_claims(open_branches: list[str], records_dir: str) -> list[Claim] | None:
    """Returns None (not a verdict) if the remote listing can't be read.
    Pass only SAME-REPO branch names -- a fork PR's headRefName isn't
    fetchable as a local ref, so `git ls-tree <that name>` resolves to
    nothing (or the wrong local branch of the same name). For fork PRs,
    fetch each PR's headRefOid via the API instead."""
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

    # A collision is more than one distinct (source, path) claiming a number.
    # Keying on (source, path) -- not path alone -- catches BOTH two files in
    # one source (two local 0047- files) AND two different branches that
    # independently created the identical path (path alone would dedupe those
    # to one and miss it). See the caveat below for the sharper API-based check.
    by_number: dict[str, list[Claim]] = {}
    for c in all_claims:
        by_number.setdefault(c.number, []).append(c)
    collisions = {n: cs for n, cs in by_number.items()
                  if len({(c.source, c.path) for c in cs}) > 1}

    if collisions:
        for number, claims in sorted(collisions.items()):
            holders = ", ".join(f"{c.path} ({c.source})" for c in claims)
            print(f"FAIL: {number} claimed by multiple files: {holders}", file=sys.stderr)
        return 1

    print(f"PASS: {len(all_claims)} records, no collisions")
    return 0

if __name__ == "__main__":
    # python check_records.py <records_dir> <branch1> <branch2> ...
    records_dir, branches = sys.argv[1], sys.argv[2:]
    sys.exit(evaluate(records_dir, branches))
```

The exit-2 branch is doing real work here, not boilerplate. Without it, a
branch that can't be read (a permissions hiccup, a network blip listing a
fork) would silently drop out of the comparison, and the check would
report a clean pass while actually comparing against fewer branches than
it thinks it is. That's a false "0" that looks identical to a real one
unless the "couldn't read this branch" case is a distinct, loud outcome.

**This is the cheap approximation, and it has a known blind spot.** It lists
each branch's *entire* `docs/adr/` tree, so it can't distinguish a file a
branch *introduced* from a baseline file it merely *inherited* from the base
branch: two branches that both already contain an old, already-merged
`0047-…md` read as a collision that isn't one. The robust version compares
each PR's **changed** ADR files (against the base branch) using each PR's
**head SHA** from the API, not a locally-resolvable branch name — which also
sidesteps the fork-branch ref problem noted in `remote_claims`. Keying on
`(source, path)`, as above, is the minimum that avoids the worst false
*negative* (two branches independently creating the same path); a
changed-files/API implementation is what you'd build for a repo where this
runs for real.

## Where to set this up

Save the script above as `scripts/check_records.py`, and run it as its
own CI job, on every pull request, not folded into a larger "lint" step
where its exit code would get merged with unrelated checks:

```yaml
# .github/workflows/records-collision.yml
on: pull_request
jobs:
  records-collision:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }   # need full history to list other branches
      - run: |
          BRANCHES=$(gh pr list --state open --json headRefName -q '.[].headRefName')
          python scripts/check_records.py records/ $BRANCHES
        env:
          GH_TOKEN: ${{ github.token }}
```

Required as a status check on the branch. A job that exits 2 must fail
the required check the same way exit 1 does; GitHub Actions itself
already treats any non-zero exit as a failed job, so the three-outcome
discipline survives into CI without extra glue, as long as nothing
downstream (a wrapper script, a "continue-on-error" step) collapses it
back down.

## What this builds on

This is the same idea as a three-valued logic system (true, false,
unknown) applied to shell exit codes, and it echoes how good test runners
already distinguish "failed" from "errored" instead of lumping both into
one red result. What's specific to this pattern is applying that
distinction consistently across an entire suite of guardrail scripts in
an agent harness, where "couldn't check" is common (agents touch flaky
APIs, half-finished state, in-progress work) and easy to accidentally
paper over.

## Limits to understand before using this

**A three-outcome contract is only useful if something downstream
actually treats the three outcomes differently.** If your CI step just
checks `exit_code == 0` for "pass" and anything else for "fail," you've
merged 1 and 2 back into a binary anyway, just with extra steps to get
there. The value is entirely in what happens after the exit code, not in
having three of them.

**Resist the urge to default 2 to 0 "just this once."** The tempting case
is always something like "the API was down, but the code obviously
hasn't changed, so it's probably still fine." That reasoning is exactly
how a could-not-assess quietly becomes an unearned pass. If it's
genuinely fine, that's worth a human decision (an explicit override,
logged), not a script inferring it.

**Applying this to an agent's own natural-language claims, not just to
scripts, needs a different mechanism.** This pattern covers exit codes
from actual programs. Getting a language model to apply the same
three-outcome discipline to what it says in prose is a related but
separate problem (see the claim-discipline-rules pattern in this
repository).
