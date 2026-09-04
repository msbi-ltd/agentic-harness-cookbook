"""Generate user-facing release notes from an explicit Git revision range."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

HEADER = re.compile(
    r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<breaking>!)?:\s*(?P<description>.+)$",
    re.IGNORECASE,
)
SECTION_FOR_TYPE = {"feat": "Features", "fix": "Fixes", "perf": "Fixes"}
SECTION_ORDER = ("Breaking", "Features", "Fixes")


@dataclass(frozen=True)
class Commit:
    message: str
    paths: tuple[str, ...]


def is_product_change(
    paths: tuple[str, ...],
    product_prefixes: tuple[str, ...],
    excluded_prefixes: tuple[str, ...],
) -> bool:
    """Classify audience from changed paths, not a commit-message scope."""
    return any(
        path.startswith(product_prefixes)
        and not path.startswith(excluded_prefixes)
        for path in paths
    )


def group_sections(
    commits: list[Commit],
    product_prefixes: tuple[str, ...],
    excluded_prefixes: tuple[str, ...] = (),
) -> list[dict[str, object]]:
    grouped: dict[str, list[str]] = {heading: [] for heading in SECTION_ORDER}
    for commit in commits:
        subject, _, body = commit.message.strip().partition("\n")
        match = HEADER.match(subject)
        if match is None or not is_product_change(
            commit.paths, product_prefixes, excluded_prefixes
        ):
            continue

        breaking = bool(match.group("breaking")) or "BREAKING CHANGE:" in body
        heading = "Breaking" if breaking else SECTION_FOR_TYPE.get(match.group("type").lower())
        if heading:
            grouped[heading].append(match.group("description").strip())

    return [
        {"heading": heading, "items": grouped[heading]}
        for heading in SECTION_ORDER
        if grouped[heading]
    ]


def git_commits(base: str, head: str, repo: Path) -> list[Commit]:
    """Read messages and paths for the exact half-open range base..head."""
    completed = subprocess.run(
        ["git", "log", "--format=%x00%B%x01", "--name-only", f"{base}..{head}"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    )
    commits: list[Commit] = []
    for record in completed.stdout.split("\0"):
        if not record.strip():
            continue
        message, separator, path_block = record.partition("\x01")
        if not separator:
            raise ValueError("git log record contained no path boundary")
        paths = tuple(line.strip() for line in path_block.splitlines() if line.strip())
        commits.append(Commit(message.strip(), paths))
    return commits


def upsert(path: Path, entry: dict[str, object]) -> None:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    existing = data.get(entry["version"])
    if existing and existing.get("sections") and not entry.get("sections"):
        raise ValueError("refusing to replace non-empty release notes with an empty entry")
    data[entry["version"]] = entry
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def generate(
    *,
    repo: Path,
    output: Path,
    version: str,
    released_at: str,
    base: str,
    head: str,
    product_prefixes: tuple[str, ...],
    excluded_prefixes: tuple[str, ...] = (),
) -> dict[str, object]:
    entry = {
        "version": version,
        "released_at": released_at,
        "source": {"base": base, "head": head},
        "sections": group_sections(
            git_commits(base, head, repo), product_prefixes, excluded_prefixes
        ),
    }
    upsert(output, entry)
    return entry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--released-at", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--product-prefix", action="append", required=True)
    parser.add_argument("--exclude-prefix", action="append", default=[])
    args = parser.parse_args()

    entry = generate(
        repo=args.repo,
        output=args.output,
        version=args.version,
        released_at=args.released_at,
        base=args.base,
        head=args.head,
        product_prefixes=tuple(args.product_prefix),
        excluded_prefixes=tuple(args.exclude_prefix),
    )
    print(f"wrote {args.output} for {entry['version']} at {args.head}")


if __name__ == "__main__":
    main()
