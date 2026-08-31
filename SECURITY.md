# Security policy

## What this repo is

This is a documentation cookbook with small, illustrative reference scripts. The
scripts in [`scripts/`](scripts/) are meant to show a mechanism clearly, not to
be dropped into production unchanged — each pattern page says as much. They
handle no secrets, expose no network service, and are not a supported product.

That said, the patterns describe **security controls** (reviewer isolation,
push guards, review-evidence binding), and a subtly wrong control is worse than
none. If you spot a flaw in the reasoning or the reference code that would cause
an implementer to build an insecure guardrail, we want to know.

## Reporting

Please report privately, not in a public issue, if the finding is a real
weakness in a described control:

- Use GitHub's **private vulnerability reporting** ("Report a vulnerability" on
  the Security tab of this repo), which opens a private advisory thread. This is
  the only private channel; there is no security-contact email by design.

For ordinary correctness bugs in a snippet (a wrong exit code, a parsing edge
case that isn't a security issue), a normal public issue or PR is fine and
preferred.

## Scope

- In scope: reasoning errors in a pattern that would lead to an insecure
  implementation; reference code that fails open where the pattern says it fails
  closed.
- Out of scope: "this script isn't production-hardened" (that's stated by
  design), dependency CVEs in a local dev-only test toolchain, and anything
  requiring a threat model the pattern explicitly excludes.
