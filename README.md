# Agentic Harness Cookbook

Practical, reusable patterns for building delivery systems around coding agents.

These implementation notes come from a working engineering harness. They cover
the controls and evidence around agent work, as well as the durable orchestration
needed to keep workflow state outside any one agent session. This is not a
complete framework, and applying the patterns does not make an agent autonomous
or safe by itself.

> **Patterns, not a product.** Nothing here is audited, supported or warranted. Security patterns carry documented limitations. Read [DISCLAIMER.md](DISCLAIMER.md) before implementing one.

## Start here

If you are new to the repository, read these first:

1. [Turn engineering principles into agent-enforced standards](patterns/agent-enforced-engineering-standards.md)
2. [The complete guardrail contract](patterns/complete-guardrail-contract.md)
3. [Three-outcome script contract](patterns/script-three-outcome-contract.md)
4. [Claim-discipline rules](patterns/claim-discipline-rules.md)

The source harness began as a mostly linear conversational pipeline. As it
evolved, another boundary became clear: **governance inside the agent loop is not
enough if the workflow depends on one long-lived conversation.** [Durable
controller, disposable agent workers](patterns/durable-controller-agent-workers.md)
covers the next step.

## Patterns

The patterns are grouped below in a suggested reading order.

| Category | Pattern | What it helps with |
|---|---|---|
| **Architecture and standards** | [Durable controller, disposable agent workers](patterns/durable-controller-agent-workers.md) | keeping workflow state and recovery outside disposable agent sessions |
|  | [Agent-enforced engineering standards](patterns/agent-enforced-engineering-standards.md) | turning external guidance and local decisions into checked ways of working |
|  | [ADR management](patterns/adr-management.md) | keeping architecture decisions current and reviewable |
|  | [Machine-checked documentation](patterns/machine-checked-docs.md) | checking documentation claims that can be made deterministic |
| **Delivery controls** | [Complete guardrail contract](patterns/complete-guardrail-contract.md) | designing a guard, its failure routing, tests and wiring together |
|  | [Direct-push guard](patterns/direct-push-guard.md) | enforcing the pull-request boundary |
|  | [Diff-budget escape valve](patterns/diff-budget-escape-valve.md) | controlling change size without blocking justified exceptions |
|  | [Three-outcome script contract](patterns/script-three-outcome-contract.md) | separating pass, findings and could-not-assess |
|  | [Agent beats and heartbeat](patterns/agent-beats-heartbeat.md) | distinguishing agent progress from controller liveness |
| **Testing and CI evidence** | [Fast feedback and merge evidence](patterns/test-evidence-layers.md) | using smoke tests locally while keeping full required CI evidence |
|  | [Characterization tests before agent-led refactoring](patterns/characterization-tests-before-refactoring.md) | preserving observed behaviour while poorly understood code is changed |
|  | [Human-readable test and coverage evidence](patterns/human-readable-test-and-coverage-evidence.md) | turning machine reports into honest GitHub Actions summaries without creating a second gate |
|  | [Parallel-safe browser testing](patterns/parallel-safe-e2e-harness.md) | isolating ports, containers, data and artifacts |
|  | [Required checks always report](patterns/required-checks-always-report.md) | avoiding skipped required jobs that appear successful |
|  | [Self-hosted runner admission control](patterns/self-hosted-runner-admission-control.md) | protecting scarce runner capacity without reducing merge evidence |
| **Security and supply chain** | [Layered security guidance](patterns/layered-security-guidance.md) | assigning clear jobs to threat models, local pattern rules, scanners and review |
|  | [Release SBOM and built-image scanning](patterns/release-sbom-and-image-scanning.md) | recording and grading what actually ships rather than trusting source manifests alone |
| **Review and merge trust** | [Reviewer isolation](patterns/reviewer-isolation.md) | separating author, reviewer and publishing credentials |
|  | [Review evidence bound to a commit](patterns/review-evidence-commit-binding.md) | preventing stale verdicts from approving a new head |
|  | [Codex code review external signal](patterns/codex-external-review.md) | adding an observed cross-model review signal without overstating its authority |
| **Measurement and learning** | [Mistake ledger](patterns/mistake-ledger.md) | learning from where defects were introduced and caught |
|  | [Claim-discipline rules](patterns/claim-discipline-rules.md) | keeping reports and dashboards honest about their evidence |

## Skills

A reliable agent workflow needs more than one large instruction file. Skills
give an agent focused guidance for the work in front of it. External skills can
bring established engineering techniques and knowledge of particular tools.
Bespoke skills can capture the repository's architecture, domain rules, testing
approach and ways of working.

Treat skills as dependencies rather than optional reading. Select them from the
activity and changed paths, load them explicitly for each worker, and review
their provenance and licence before adoption.

See [Agent-enforced engineering standards](patterns/agent-enforced-engineering-standards.md)
for a practical skill set, where to configure invocation, how to handle nested
workers and why some skills should remain optional.

> **Coming soon:** a separate repository containing reusable skills developed
> for the source harness. They will be published after project-specific content
> has been removed and the guidance and examples have been prepared for reuse.

## Repository documents

- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Disclaimer](DISCLAIMER.md)
- [Documentation licence](LICENSE-docs.md)
- [Software licence](LICENSE)
- [Notices](NOTICE)

## Licence

Code samples, workflows and configuration use the [Apache License 2.0](LICENSE). Prose and diagrams use [CC BY 4.0](LICENSE-docs.md). See [NOTICE](NOTICE).

## Disclaimer

These patterns were extracted from a private system. They have not been independently audited and come with no warranty. A partly implemented security or approval gate can create false confidence; read each pattern's limitations and the full [disclaimer](DISCLAIMER.md).

## No vendor affiliation

This project is not affiliated with, endorsed by or sponsored by Anthropic PBC or OpenAI. Product and company names identify the tools used.

## Contributing

Contributions are accepted under the [Developer Certificate of Origin](https://developercertificate.org/). Sign off each commit with `git commit -s` to confirm you have the right to submit the work under this repository's licences.
