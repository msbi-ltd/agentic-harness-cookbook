#!/usr/bin/env python3
"""Classify what branch(es) a `git push` command targets, for a pre-push guard.

This is the parser behind a "don't let the agent push straight to main" hook.
It does ONE job: given the argv of a git push, decide whether the push could
land on a protected branch. It deliberately fails *closed* — if it can't tell
what a push targets, it says so, and the caller should block rather than wave
it through. A guard that guesses "probably fine" on an argument shape it didn't
anticipate is worse than no guard, because it reports safe.

This only sees the command line. It does not resolve the remote's configured
push default, `push.default`, branch tracking, or refspec config in
`.git/config` — a bare `git push` with an upstream set can still land on a
protected branch, and this returns "unknown" for exactly that reason rather
than pretending the empty argv is safe. The real boundary is server-side
branch protection; see the pattern doc. This is the fast local net, not the
wall.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

# Everything before these is a `push` flag we understand and can skip; the rest
# is [remote] [refspec...]. Flags that TAKE a value are handled explicitly so we
# don't mistake their value for a remote.
_VALUE_FLAGS = {"-o", "--push-option", "--receive-pack", "--exec", "--repo"}
_BOOL_FLAGS_PREFIX = "-"  # any other dash-led token is treated as a valueless flag


@dataclass
class PushTarget:
    #: Branch names this push could write to, as best we can tell.
    branches: list[str] = field(default_factory=list)
    #: True when we could not determine the target at all (bare push, --all,
    #: --mirror, config-dependent). The caller must treat this as "block".
    unknown: bool = False
    reason: str = ""

    def could_hit(self, protected: set[str]) -> bool:
        """Would this push land on a protected branch — or might it, if we
        couldn't tell? Unknown counts as yes: fail closed."""
        if self.unknown:
            return True
        return any(b in protected for b in self.branches)


def _refspec_dest(refspec: str) -> str:
    """Destination branch of a refspec. `src:dst` -> dst; `branch` -> branch;
    a leading `+` (force) is stripped. `HEAD:main` -> main."""
    spec = refspec.lstrip("+")
    dst = spec.split(":", 1)[1] if ":" in spec else spec
    # refs/heads/main -> main; leave anything exotic (tags, refs/*) as-is,
    # a protected *branch* name won't match refs/tags/... anyway.
    if dst.startswith("refs/heads/"):
        dst = dst[len("refs/heads/") :]
    return dst


def classify(argv: list[str]) -> PushTarget:
    """argv is the push command WITHOUT the leading `git push` (or with — a
    leading `git` and/or `push` token is tolerated and skipped)."""
    tokens = list(argv)
    while tokens and tokens[0] in ("git", "push"):
        tokens.pop(0)

    positionals: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("--all", "--mirror"):
            return PushTarget(
                unknown=True,
                reason=f"{tok} pushes many refs at once; can't single out the target",
            )
        if tok in _VALUE_FLAGS:
            i += 2  # skip the flag and its value
            continue
        if tok.startswith("--") and "=" in tok:
            i += 1  # --flag=value, self-contained
            continue
        if tok.startswith(_BOOL_FLAGS_PREFIX) and tok != "-":
            # A valueless flag (-f, --force, -u, --set-upstream, -v, ...).
            # -u/--set-upstream still takes its remote/branch as POSITIONALS,
            # so we don't consume anything extra here.
            i += 1
            continue
        positionals.append(tok)
        i += 1

    # positionals is now [remote?, refspec...]. The first positional is the
    # remote; the rest are refspecs.
    if not positionals:
        return PushTarget(
            unknown=True,
            reason="bare push with no refspec: target depends on push.default and "
            "the branch's configured upstream, which this parser can't see",
        )

    refspecs = positionals[1:]
    if not refspecs:
        return PushTarget(
            unknown=True,
            reason="push to a remote with no explicit refspec: target is the "
            "current branch's upstream, which this parser can't see",
        )

    return PushTarget(branches=[_refspec_dest(r) for r in refspecs])


if __name__ == "__main__":
    # Exit 0 = safe to allow, 1 = blocked (hits or might hit a protected
    # branch). Protected branches come from argv after a `--protected` marker,
    # defaulting to {main, master}.
    #   git_push_target.py --protected main master -- git push origin HEAD:main
    raw = sys.argv[1:]
    protected = {"main", "master"}
    if "--protected" in raw:
        idx = raw.index("--protected")
        end = raw.index("--", idx) if "--" in raw[idx:] else len(raw)
        protected = set(raw[idx + 1 : end])
        raw = raw[end + 1 :] if "--" in raw[idx:] else []
    target = classify(raw)
    if target.could_hit(protected):
        why = target.reason or f"pushes to protected branch(es): {target.branches}"
        print(f"BLOCKED: {why}", file=sys.stderr)
        sys.exit(1)
    print(f"allowed: targets {target.branches}")
    sys.exit(0)
