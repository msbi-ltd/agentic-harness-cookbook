#!/usr/bin/env python3
"""Optional scaffold for a new ADR: computes the next number and writes the
template. This removes a typo-prone step; it does NOT remove the need for the
CI collision check. `next_number` only sees the LOCAL branch — exactly like
picking a number by hand — so a sibling branch can still claim the same number.
The collision check (see check_records.py) is what makes either approach safe.

Not something the source system these patterns come from actually uses; there,
the number is picked by hand at close-out and CI catches collisions. Included
here as a hardening you can adopt if hand-numbering keeps colliding in practice.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ADR_DIR = Path("docs/adr")

TEMPLATE = """# ADR-{number}: {title}

- **Status:** Proposed
- **Supersedes:** nothing

## Context



## Decision



## Consequences


"""


def next_number(adr_dir: Path = ADR_DIR) -> str:
    existing = [
        int(m.group(1))
        for p in adr_dir.glob("*.md")
        if (m := re.match(r"(\d{4})-", p.name))
    ]
    return f"{(max(existing) + 1) if existing else 1:04d}"


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def create(title: str, adr_dir: Path = ADR_DIR) -> Path:
    adr_dir.mkdir(parents=True, exist_ok=True)
    number = next_number(adr_dir)
    path = adr_dir / f"{number}-{slugify(title)}.md"
    path.write_text(TEMPLATE.format(number=number, title=title))
    return path


if __name__ == "__main__":
    # python new_adr.py "Short decision title"
    if len(sys.argv) < 2:
        print('usage: new_adr.py "Short decision title"', file=sys.stderr)
        sys.exit(2)
    created = create(sys.argv[1])
    print(f"Created {created}. Fill in Context, Decision, Consequences, then open a PR.")
