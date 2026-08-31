# Disclaimer

**Read this before implementing anything in this repository.**

## No warranty, no liability

This repository is published under the Apache License 2.0 (code) and CC BY 4.0
(documentation). Both licenses disclaim all warranties and limit liability;
this file restates the parts that matter most in plain words, and adds the
ones specific to what is published here.

Everything here is provided **as is**. Neither MSBI Ltd nor any
contributor accepts responsibility or liability for any loss, damage, outage,
data loss, security incident, cost or other harm arising from the use of, or
reliance on, anything in this repository — whether the material is used as
written, adapted, or merely used to inform a decision.

## These are patterns, not products

What is published here are **descriptions of engineering patterns**, extracted
from a private system and generalised. They are not a library, not a supported
product, and not a drop-in solution.

- Nothing here has been through an independent security audit.
- Nothing here carries a support commitment, a maintenance commitment, or a
  compatibility guarantee.
- Code samples are illustrative. They are written for clarity, not for
  production hardening, and they will not be correct for every environment.
- The patterns were developed against specific versions of specific
  third-party platforms. Those platforms change. A pattern that held when
  written may not hold when you read it.

## Security patterns carry particular risk

Some material here describes **security and approval-gating patterns** —
notably approaches to separating an automated actor from the credential that
approves its work.

A partially-implemented gate is more dangerous than no gate at all, because it
produces confidence without producing control. If you implement one of these
patterns incorrectly, or in a threat model it was not designed for, you may
believe you have an enforced control when you do not.

Specifically:

- **Validate every pattern against your own threat model.** These patterns
  address the threats that mattered in the originating system. Yours will
  differ.
- **Known limitations are documented alongside each pattern. Read them.**
  Where a control has a boundary — something it does *not* protect against —
  that boundary is stated deliberately, not as an afterthought. Implementing
  the control while ignoring the stated boundary is a misuse of the material.
- **Test the failure mode, not just the success path.** The failure worth
  fearing is a gate that reports success while enforcing nothing.
- **Get an independent review** before relying on any of this in an
  environment where a failure would matter.

## Not professional advice

Nothing in this repository constitutes security advice, legal advice,
compliance advice, or professional consulting advice, and no client or
advisory relationship is created by your use of it. Where the material touches
regulated or safety-relevant concerns, obtain qualified professional advice
that accounts for your circumstances.

## No affiliation

This project is not affiliated with, endorsed by, or sponsored by Anthropic
PBC or any other vendor named in this repository. Third-party names are used
only to identify the tools the patterns were developed against. See [NOTICE](NOTICE).

## Reporting a problem

If you believe something published here is wrong in a way that could cause
harm — particularly a security pattern with an undocumented weakness — please
open an issue, or use GitHub's private vulnerability reporting for anything
sensitive. Corrections are welcome and will be made promptly; that is the
practical remedy this project offers in place of a warranty.
