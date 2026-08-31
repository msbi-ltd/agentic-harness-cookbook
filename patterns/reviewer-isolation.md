# Pattern: capability-isolated reviewer (GitHub Actions / GitHub Apps)

> **Status:** Reference sketch (GitHub-specific YAML) · **Last verified:** 2026-08-31  
> **Tested against:** live reviewer-persona workflow; no standalone script  
> **Enforcement:** isolated reviewer capability + commit-bound evidence + required source provenance  
> **Reference implementation:** workflow YAML in this page

> **Scope:** this pattern is written specifically for GitHub. It relies on GitHub Apps as the credential mechanism and GitHub Actions as the execution platform. The underlying idea is broader: the authoring actor must not possess the capability needed to manufacture the review evidence that the merge policy trusts.

## Problem

An autonomous loop writes code, opens a pull request and eventually merges it. Somewhere in that path you want a reviewer step that can actually say no.

The common shortcut is a second prompt using the same credentials: "you are now a strict code reviewer." That may add a useful second cognitive pass, but it is not separation of authority. The same actor can still edit the branch, alter the workflow or manufacture whichever evidence the gate trusts.

The required property is not "different display name." It is:

> **The reviewer can produce evidence the author cannot forge, and the merge policy can verify the provenance of that evidence for this exact commit.**

That is a capability boundary.

## Identity is metadata; capability is the invariant

GitHub exposes the same App or bot through several API surfaces, and those surfaces can render different login strings (for example bare bot names, `[bot]` suffixes, or App-style names). A gate that relies on an exact display-login spelling can silently become inert after an identity migration or API change while still looking mechanically enforced.

Treat login strings as useful diagnostic/audit metadata, not as the primary trust primitive.

Prefer evidence that carries or can be verified against:

- the stable GitHub App / installation that produced it;
- the capability assigned to that App (for example `independent-reviewer`);
- the exact head SHA reviewed;
- a fixed evidence context/name;
- a timestamp or freshness rule;
- a policy that the author cannot rewrite for the current change.

Conceptually:

```json
{
  "type": "review-attestation",
  "subject": "pull-request:123",
  "head_sha": "abc123",
  "producer": {
    "app_id": 123456,
    "installation_id": 789
  },
  "capability": "independent-reviewer",
  "verdict": "clean"
}
```

GitHub commit statuses/checks are one implementation of that attestation model; the JSON above is the invariant, not a required wire format.

## How it works (GitHub Actions)

Give the reviewer step a **distinct credential the authoring loop cannot reach**.

1. Create a separate GitHub App (reviewer bot) with only the permissions it needs.
2. Keep its private key outside the authoring loop's reachable secret scope.
3. Run the reviewer in a separately protected workflow/context.
4. Mint the App installation token inside that job only.
5. Bind the verdict to the exact PR head SHA.
6. Publish the verdict using the reviewer App's credential.
7. Configure the merge policy / branch rule to trust that required evidence only when it comes from the expected App/source.

Example shape:

```yaml
review:
  permissions:
    contents: read
    pull-requests: read
    statuses: write

  steps:
    - uses: actions/create-github-app-token@<audited-sha>
      id: reviewer-token
      with:
        app-id: ${{ vars.REVIEWER_APP_ID }}
        private-key: ${{ secrets.REVIEWER_APP_PRIVATE_KEY }}

    - name: Resolve reviewed head SHA
      id: head
      env:
        GH_TOKEN: ${{ steps.reviewer-token.outputs.token }}
      run: |
        echo "sha=$(gh pr view "$PR_NUMBER" --json headRefOid -q .headRefOid)" \
          >> "$GITHUB_OUTPUT"

    - name: Run review and publish verdict
      env:
        GH_TOKEN: ${{ steps.reviewer-token.outputs.token }}
        HEAD_SHA: ${{ steps.head.outputs.sha }}
      run: |
        # ... review produces clean/findings/error ...
        # Convert that policy result into the status representation your
        # protected branch requires, using the reviewer App token.
        gh api "repos/$GITHUB_REPOSITORY/statuses/$HEAD_SHA" \
          -f state="$verdict_state" \
          -f context="reviewer-app/verdict" \
          -f description="isolated reviewer verdict"
```

There is no need for `id-token: write` merely to mint a GitHub App installation token from its private key. OIDC is a separate mechanism used when federating to another provider.

## Protect the definition of review

Credential isolation stops the author forging evidence after the fact. It does not stop the author weakening the code or prompt that decides what counts as clean.

Protect the review-defining workflow and policy separately. For high-risk systems, changes to:

```text
.github/workflows/reviewer-*.yml
review prompts / policy
merge-policy code
reviewer App configuration
```

should themselves be treated as control-plane changes and require stronger approval than ordinary product code.

A useful rule is:

> A change must be judged under the base branch's review policy, not a weakened policy introduced by the same change.

See [Durable controller, disposable agent workers](durable-controller-agent-workers.md) for the broader control-plane pattern.

## Review execution and review verdict are different facts

Do not overload process execution failure with a review-policy result.

These are distinct:

```text
review execution: SUCCESS
review verdict: FINDINGS
```

and:

```text
review execution: ERROR
review verdict: UNKNOWN
```

A controller or merge-policy evaluator can then decide whether findings block the change. This is easier to reason about than making every finding look like a crashed CI job.

The same three-outcome discipline applies here: `clean`, `findings`, and `could-not-assess/error` must remain distinct.

## What isolation buys, and what it does not

There are several different kinds of separation:

### Credential/capability isolation

The author cannot mint the reviewer credential or publish the trusted attestation. This is mechanically enforceable and is the main subject of this pattern.

### Context isolation

The reviewer starts with a fresh context rather than inheriting the author's rationale. Useful, but an orchestration property rather than a cryptographic guarantee.

### Model/provider separation

A different model or provider may reduce correlated reasoning failures. It can improve review quality but does not replace capability isolation.

### Human authority

A human reviewer adds genuinely independent judgement and authority. Keep it for changes whose risk warrants it, especially changes to the autonomous system's own trust boundary.

A Claude reviewer under a separate App is therefore useful, but it should not be described as independent **reasoning** merely because it has an independent credential.

## Commit binding

A good reviewer identity is insufficient if its clean verdict floats free of the code that was actually reviewed.

Always bind the evidence to the exact head SHA. A later push must invalidate the previous verdict and require a new one.

See [Review evidence bound to a commit](review-evidence-commit-binding.md).

## What this builds on

This is separation of duties through distinct credentials and protected signing/attestation capability: the same reasoning used for service accounts, release signing keys, deployment roles and four-eyes controls.

In an agent workflow, the author and reviewer may both be LLM workers. The
authority boundary still needs to exist independently of their prompts.

## Limits to understand before using this

**Capability isolation does not guarantee reasoning independence.** The reviewer can share the author's blind spots, especially when it uses the same model family or context.

**A trusted App can still run weak review logic.** Protect the workflow/prompt/policy that produces the verdict.

**A missing verdict must not become a pass.** Token mint failure, workflow errors, permissions failures and timeouts should produce `unknown/could-not-assess`, never silently satisfy merge policy.

**Do not key critical trust to display login strings.** They are representation details. If a platform forces you to inspect strings, normalize them only as an adapter at the boundary and verify the stable App/source wherever possible.

**Test provenance failures.** Verify that a status/check with the same name but from an untrusted source cannot satisfy the gate. Verify that evidence from an older SHA cannot satisfy the current one.

**The reviewer App is itself a security-sensitive capability.** Rotate and protect its key, minimize permissions and audit changes to its configuration.
