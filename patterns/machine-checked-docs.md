# Pattern: machine-checked documentation claims

> **Status:** Reference implementation · **Last verified:** 2026-08-31  
> **Tested against:** `scripts/check_docs_facts.py` (`tests/test_check_docs_facts.py`)  
> **Enforcement:** CI check, or a report-only run for docs not present on every checkout  
> **Reference implementation:** `scripts/check_docs_facts.py`

## Problem

Documentation makes factual claims about the repository: “the coverage gate is
95%,” “this setting is defined only in `vite.config.ts`,” or “the loop runs as
identity X.”

Those claims may be correct when written and wrong a month later. A threshold
changes, a file moves, or a second configuration path appears while the
documentation continues to sound certain. That is worse than a missing detail
because it sends the reader in the wrong direction.

“Remember to update the docs” is not a control. The useful facts need checks that
fail when the code and documentation drift apart.

## How it works

Pick whichever document in your repository states facts that go stale
easily, the kind of file this pattern is aimed at is something like
`CLAUDE.md`, `AGENTS.md`, or a `README.md` "how this project works"
section. Put a small, machine-readable table of claims directly inside
*that* file, as its own section, and write one script,
`check_docs_facts.py` below, that reads the table out of the file and
checks every row against the actual tree. A drifted claim becomes a
failing check, not a sentence nobody re-reads.

Here's what the section looks like inside, say, `CLAUDE.md`:

```markdown
## Machine-checked facts

The rows below are claims in this file that a script can verify.
`check_docs_facts.py` reads this table and fails naming any row that no
longer holds.

​```facts-table
| kind          | symbol                | source                  | expect |
|---------------|------------------------|--------------------------|--------|
| numeric       | --cov-fail-under=(\d+) | .github/workflows/ci.yml | 95     |
| symbol-absent | OLD_CONFIG_FLAG        | .github/workflows/ci.yml |        |
| symbol-present| DEFAULT_TIMEOUT        | src/config.py            |        |
​```
```

A small, closed set of claim kinds keeps the checker itself simple. Here's
the core, three-outcome exit codes included. This is `check_docs_facts.py`,
the same script named in the markdown section above and invoked again
further down; the full, tested version — including the real
`parse_facts_table` — is in
[`scripts/check_docs_facts.py`](../scripts/check_docs_facts.py):

```python
# scripts/check_docs_facts.py (core; parse_facts_table is in the file)
import re
from pathlib import Path

VERDICT_EXIT = 1
COULD_NOT_ASSESS_EXIT = 2

def evaluate_row(kind: str, symbol: str, source: str, expect: str, repo_root: Path):
    """(holds: bool, detail: str). Raises FileNotFoundError if `source`
    itself is missing -- that's could-not-assess, not a false claim."""
    text = (repo_root / source).read_text()
    if kind == "symbol-present":
        return symbol in text, f"`{symbol}` in `{source}`"
    if kind == "symbol-absent":
        return symbol not in text, f"`{symbol}` absent from `{source}`"
    if kind == "numeric":
        match = re.search(symbol, text)
        if match is None:
            return False, f"pattern `{symbol}` not found in `{source}`"
        return match.group(1) == expect, f"`{symbol}` == {expect} in `{source}`"
    raise ValueError(f"unknown claim kind: {kind}")

def check(doc_path: Path, repo_root: Path) -> tuple[int, str]:
    try:
        text = doc_path.read_text()
    except OSError as exc:
        # Missing is the normal case in some checkouts (a private doc that
        # isn't tracked everywhere), never a pass, never a hard crash.
        return COULD_NOT_ASSESS_EXIT, f"{doc_path} not readable: {exc}"

    # parse_facts_table returns (rows, malformed): malformed rows (bad column
    # count, unknown kind, a regex with no capture group) are could-not-assess
    # from the start, never silently dropped.
    rows, malformed = parse_facts_table(text)
    failures, could_not_assess, passed = [], list(malformed), 0
    for kind, symbol, source, expect in rows:
        try:
            ok, detail = evaluate_row(kind, symbol, source, expect, repo_root)
        except (FileNotFoundError, ValueError) as exc:
            could_not_assess.append(f"{source}: {exc}")
            continue
        if ok:
            passed += 1
        else:
            failures.append(detail)

    if could_not_assess:
        return COULD_NOT_ASSESS_EXIT, "; ".join(could_not_assess)
    if failures:
        return VERDICT_EXIT, "; ".join(failures)
    return 0, f"{passed} claim(s) held"
```

A malformed row (wrong column count, an unknown `kind`, a regex with no
capture group) is reported the same way as a missing source file: as
could-not-assess, never silently skipped and never folded into a clean
pass. A checker that half-parses its own contract and still exits 0 is
worse than no checker.

Adding a new claim is a data change, a new row in the table, not a code
change. Adding a genuinely new *kind* of claim (something the three above
can't express) is a deliberate, rare change to the checker itself, which
is what keeps the table from becoming an ad hoc scripting language nobody
can audit at a glance.

## Where this runs

The obvious place is a CI job on every pull request, and that's the right
default if the document being checked (`CLAUDE.md` in the example above,
or whatever you picked) is a normal, tracked file that every checkout has.
But it isn't always. Some projects keep their agent-instructions file, or
an internal ops doc, out of the public tree on purpose, gitignored, or
only present in a private overlay. A file like that will not exist on
some checkouts, including CI runners. Wired in as a plain CI step, that
reads as "could not assess" on every single run, permanently, since the
file is never there to begin with, which trains people to ignore the
check entirely.

For a doc like that, wire `check_docs_facts.py` into whatever routinely
runs *alongside* the work instead, on the machine where the file actually
exists, report-only rather than a merge gate: a pre-task hook, a periodic
sweep, a step in an agent's own startup routine. The three-outcome
contract still matters just as much here (missing file is still
could-not-assess, not a silent skip), it's just that "could not assess"
means something different and less alarming on a checkout that was never
expected to have the file, versus one that should.

```bash
# invoked at the start of an agent session, not in CI, because CLAUDE.md
# here is gitignored and only present in this project's main checkout
python3 check_docs_facts.py --path CLAUDE.md --repo-root .
# exit 2 on a fresh agent worktree just means "this checkout doesn't carry
# CLAUDE.md" -- expected there, worth investigating on the main checkout
```

Two design choices are worth calling out:

- **File paths mentioned in backticks can be checked automatically**,
  without a table row at all: does the path exist. That's unambiguous
  enough not to need an explicit claim.
- **Every other kind of claim needs the explicit table**, rather than
  trying to infer the check from the surrounding prose. Inferring "this
  paragraph is claiming X" from natural language is itself something that
  can silently break the moment someone rewords a sentence, which
  reintroduces the exact false-confidence problem this pattern exists to
  close.

## What this builds on

This is the same idea as a doctest, or a README code block that's
actually executed in CI rather than just displayed. What's different here
is applying it to plain factual assertions in prose, not code samples,
which is a much less common use of the same principle: a claim that can
be checked should be checked, automatically, not trusted by inspection.

## Limits to understand before using this

**This only covers claims you remembered to add a row for.** A stale
claim with no corresponding table row is invisible to the checker, same
as before. The pattern shrinks the blast radius of doc drift; it doesn't
eliminate the discipline of adding a row when you write a new checkable
claim.

**A malformed row must fail the check, not skip it silently.** A table
row with the wrong number of columns, an unknown claim kind, or a regex
that fails to compile is a broken contract, not an empty one. Report it
as a failure alongside any genuine claim violations, never as if the row
was not there.

**Keep the claim kinds few and boring.** The value of this pattern comes
from the checker being small enough that anyone can read it in a few
minutes and trust what it's actually verifying. A checker that's grown
elaborate inference logic to "understand" more complex claims has quietly
turned back into the same fragile, hard-to-trust thing the pattern was
meant to replace.
