#!/usr/bin/env python3
"""Machine-checked documentation claims. Parses a `claude-md-facts`-style
fenced table out of a doc and verifies every row against the tree.
Three-outcome exit codes: 0 clean, 1 a claim is false, 2 could-not-assess
(missing doc, missing source, malformed row, bad regex) -- never folded
into a pass."""
from __future__ import annotations

import re
import sys
from pathlib import Path

VERDICT_EXIT = 1
COULD_NOT_ASSESS_EXIT = 2

SUPPORTED_KINDS = ("symbol-present", "symbol-absent", "numeric")
FENCE_RE = re.compile(r"```facts-table\s*\n(.*?)```", re.DOTALL)


class Malformed(Exception):
    """A row that couldn't be parsed at all -- could-not-assess, not a verdict."""


def parse_facts_table(text: str) -> tuple[list[tuple[str, str, str, str]], list[str]]:
    """Returns (rows, malformed_descriptions). A row is (kind, symbol, source, expect).
    Never silently drops a malformed row -- it's reported, not skipped."""
    rows: list[tuple[str, str, str, str]] = []
    malformed: list[str] = []
    fence = FENCE_RE.search(text)
    if not fence:
        return rows, malformed  # no table at all is not an error -- nothing to check

    lines = [ln.strip() for ln in fence.group(1).splitlines() if ln.strip()]
    data_lines = [ln for ln in lines if not re.fullmatch(r"\|?[\s:|-]+\|?", ln)]
    # Drop the header row itself (starts with "| kind" case-insensitively)
    data_lines = [ln for ln in data_lines if not ln.lower().lstrip("|").strip().startswith("kind")]

    for lineno, line in enumerate(data_lines, start=1):
        cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
        if len(cells) != 4:
            malformed.append(f"row {lineno} (`{line}`): expected 4 columns, got {len(cells)}")
            continue
        kind, symbol, source, expect = cells
        if kind not in SUPPORTED_KINDS:
            malformed.append(f"row {lineno}: unknown kind {kind!r}")
            continue
        if not symbol or not source:
            malformed.append(f"row {lineno}: symbol/source column is empty")
            continue
        if kind == "numeric":
            try:
                compiled = re.compile(symbol)
            except re.error as exc:
                malformed.append(f"row {lineno}: symbol `{symbol}` is not a valid regex: {exc}")
                continue
            if compiled.groups != 1:
                malformed.append(
                    f"row {lineno}: symbol `{symbol}` must have exactly one capture group, "
                    f"has {compiled.groups}"
                )
                continue
        rows.append((kind, symbol, source, expect))
    return rows, malformed


def evaluate_row(kind: str, symbol: str, source: str, expect: str, repo_root: Path) -> tuple[bool, str]:
    """(holds, detail). Raises FileNotFoundError if `source` itself is missing --
    that's could-not-assess, not a false claim."""
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
        return COULD_NOT_ASSESS_EXIT, f"{doc_path} not readable: {exc}"

    rows, malformed = parse_facts_table(text)
    failures, could_not_assess, passed = [], list(malformed), 0
    for kind, symbol, source, expect in rows:
        try:
            ok, detail = evaluate_row(kind, symbol, source, expect, repo_root)
        except FileNotFoundError as exc:
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


if __name__ == "__main__":
    # python check_docs_facts.py --path CLAUDE.md --repo-root .
    args = sys.argv[1:]
    path = Path(args[args.index("--path") + 1]) if "--path" in args else Path("CLAUDE.md")
    root = Path(args[args.index("--repo-root") + 1]) if "--repo-root" in args else Path(".")
    code, report = check(path, root)
    print(report, file=sys.stderr if code else sys.stdout)
    sys.exit(code)
