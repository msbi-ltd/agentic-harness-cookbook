# Contributing

Thanks for looking. This repo is a cookbook of small, self-contained harness
patterns extracted from a real agent-driven delivery system, plus a tested
reference implementation of each in [`scripts/`](scripts/).

## The one rule that matters here

**Every code snippet in a pattern page must correspond to real, tested code in
`scripts/`, and the tests must cover the could-not-assess path, not just
pass/fail.** This repo argues, at length, that a guardrail you haven't executed
is not evidence. That claim has to hold for the repo's own examples first. A PR
that adds or changes a snippet without a matching, tested script is the exact
failure mode the patterns warn about.

If you find a snippet that drifts from its script, or a script that isn't
exercised for all three outcomes (0 clean / 1 verdict / 2 could-not-assess),
that's a bug — please open an issue or PR.

## Working locally

```bash
pip install -r requirements-dev.txt   # pinned pytest + ruff
python -m pytest -q                    # all scripts, all three exit paths
ruff check scripts/ tests/             # lint
```

**CI** runs on every pull request via `.github/workflows/ci.yml`: a `test`
job (pytest + ruff), a `shellcheck` job on the hook example, and a `docs`
job (YAML lint + Markdown-link validation). Run the same checks locally with
the commands above before opening a PR. A maintainer makes the `test` job a
required status check on the default branch so it actually gates merges.

## Scope

- **Patterns** are small and standalone. If a write-up needs a diagram and three
  pages of setup, it belongs in the separate deep-dives repo, not here.
- **Prose voice:** plain, lead with the mechanism, name the failure mode. Match
  the existing pages.
- **Honesty over polish.** If a pattern has a limitation, the "Known limitations"
  section says so in plain words. Don't oversell.

## Licensing

Code contributions are under Apache 2.0; documentation under CC BY 4.0. See
[LICENSE](LICENSE), [LICENSE-docs.md](LICENSE-docs.md), and [DISCLAIMER.md](DISCLAIMER.md).
By opening a PR you agree your contribution is licensed under those terms.
