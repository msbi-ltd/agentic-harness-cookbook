# Pattern: direct-push guard (Claude Code hooks)

> **Status:** Reference implementation · **Last verified:** 2026-08-31  
> **Tested against:** `scripts/git_push_target.py` (`tests/test_git_push_target.py`)  
> **Enforcement:** Local pre-tool hook (fast net) **plus** server-side branch protection (the real boundary)  
> **Reference implementation:** `scripts/git_push_target.py` + `.claude/hooks/git-guard.sh`

> **Scope:** the example below uses a Claude Code pre-tool-use hook, which
> intercepts a shell command before it runs and can block it. Other
> harnesses have different extension points (a wrapper script, a git
> `pre-push` hook, a CI-side branch protection rule). The idea, refusing a
> destructive action at the point it's about to happen instead of relying
> on the agent remembering not to do it, applies everywhere. The
> mechanism below is specific to Claude Code.

## Problem

An agent with shell access can eventually run `git push origin main` by
mistake. It may be on the wrong branch, reuse a command from another repository,
or simply slip during a long session.

Writing “never push directly to main” in the instructions helps, but it does not
stop the command. Once the push succeeds, the problem has moved from prevention
to recovery.

## How it works

Intercept the command **before** it runs, at the tool-execution layer,
not inside the agent's own reasoning. A Claude Code pre-tool-use hook
receives the exact shell command about to be executed and can block it
outright:

```bash
#!/usr/bin/env bash
# git-guard.sh: blocks direct pushes to main/master.
# Claude Code calls this before every Bash tool call.
# Exit 0 = allow. Exit 2 = block (stderr becomes the reason the agent sees).
set -euo pipefail
HERE="$(dirname "$0")"

cmd=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')

# Only bother if this looks like a push at all.
if printf '%s' "$cmd" | grep -qE '(^|[;&|]|\s)git\s+push'; then
  # Delegate destination parsing to git_push_target.py, which classifies the
  # actual ref being pushed and FAILS CLOSED (exit 1) on anything it can't
  # resolve -- a bare `git push`, `--all`, `--mirror`. It exits 1 for a
  # protected target OR an ambiguous one, 0 only when it's sure the push
  # misses main/master. `# shellcheck disable=SC2086` -- we want word-splitting
  # here so the push args reach the parser as argv.
  # shellcheck disable=SC2086
  if ! python3 "$HERE/git_push_target.py" --protected main master -- $cmd; then
    echo "BLOCKED: this push could target a protected branch. Push a feature branch and open a PR instead." >&2
    exit 2
  fi
fi

exit 0
```

Save the script as `.claude/hooks/git-guard.sh`, and the helper it calls,
[`git_push_target.py`](../scripts/git_push_target.py), beside it in the same
directory. The parser is deliberately conservative: it classifies
`git push origin HEAD:main`, force variants, and `refs/heads/main` as hits,
and it refuses to classify a bare `git push`, `--all`, or `--mirror` —
returning "unknown", which the guard treats as a block, because those depend
on git config the hook can't see. Register the hook in `.claude/settings.json`,
the file Claude Code reads for project-level configuration:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": ".claude/hooks/git-guard.sh" }
        ]
      }
    ]
  }
}
```

With this in place, the hook runs on every shell command the agent
attempts, not just the ones it thinks to double-check. A blocked command
returns immediately with a reason, which the agent sees as a normal tool
failure and can react to (push a branch, open a PR) rather than something
it needs to be told about after the fact.

## What this builds on

This is the same idea as a git `pre-push` hook or a CI branch-protection
rule, both long-standing practice for exactly this failure mode in human
workflows. Applying it at the tool layer of an agent harness instead of
(or as well as) the git layer is the only difference, and it matters
because it can also catch destructive patterns that aren't specifically
about git, like a bulk `rm -rf` or a blanket `git add .` that risks
staging secrets.

## Limits to understand before using this

**Match on the actual destination, not a substring of the command text.**
An early, naive version of a guard like this can trip on a branch name
that happens to contain "main" (`maintenance`, `domain`) or a commit
message that mentions the protected branch name. Parse the command enough
to know what ref is actually being pushed to, not just whether the string
"main" appears anywhere in it. Getting this wrong in either direction is
costly: too loose and it blocks legitimate work, too strict and someone
starts routing around it.

**A missing helper script must fail closed, not open.** If the hook
depends on a separate parsing script and that script is absent (a fresh
checkout, an old branch, a worktree missing a file), the safe failure
mode is to fall back to a stricter check, even a blunt substring match,
rather than silently allowing every push through unexamined.

**Know the enforcement hierarchy — this hook is the middle layer, not the
boundary.** Three levels, in increasing order of how hard they are to get
around:

1. **Prompt guidance** ("never push to main" in the instructions) — advisory
   only; the agent can simply not apply it in the moment. Free, weakest.
2. **This local hook** — a fast, deterministic net that catches the honest
   mistake before it leaves the machine. But it only runs if the command
   goes through Claude Code's Bash tool; a subshell, a different tool, an
   `alias`, or a harness without the hook installed all route around it. It
   raises the cost of an accidental push to near zero, and does nothing
   against a determined bypass.
3. **Server-side branch protection** on the remote — the *actual* boundary.
   It doesn't care how the push was produced; the remote refuses it. This is
   the only layer that holds against a crafted bypass or a machine that never
   had the hook.

Use the hook for fast, local, good-mistake prevention, but treat
server-side branch protection as the thing that actually enforces the rule.
If you can only have one, make it the server-side rule.
