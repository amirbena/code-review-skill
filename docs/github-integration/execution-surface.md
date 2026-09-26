# GitHub Integration Execution Surface

Decision record for GitHub Issue
[#547](https://github.com/amirbena/code-review-skill/issues/547) (parent
Epic #546). It fixes where GitHub integration mechanics execute so the
publisher (#548), detector, and setup (#549) share one call and
authentication path. It is a design record, not a policy.

## Decision

Mechanics live in **repository tooling**, `scripts/github_integration/`,
not in packaged Skill content:

- Packaged Skills keep shipping markdown only; the review-status contract
  in
  [`review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md)
  stays the canonical behavior.
- The runtime invokes the tooling (or the child capabilities built on it)
  from a repository checkout. Nothing under `scripts/` is added to a Skill
  archive, so **packaging and metadata are unchanged**.
- A documented bare-`gh` procedure remains the fallback where the tooling
  is not present; it must follow the same read/mutate split below.

## Call boundary

`GitHubClient` in
[`boundary.py`](../../scripts/github_integration/boundary.py) is the only
place that talks to GitHub (through `gh api`).

| Entry point | Purpose | Guard |
| --- | --- | --- |
| `read()` | GET-only reads (detection) | none needed |
| `write()` | Non-governance writes (e.g. commit statuses) | Refuses rulesets / branch-protection / branch-rules endpoints |
| `mutate_governance()` | Governance mutations | Keyword-only `authorization`; refused unless it records an explicit user request |
| `preflight()` | Authentication and, for classic tokens, scope check | Actionable errors |

- **Authorization.** `GovernanceAuthorization` is supplied by the caller
  only from an explicit user request; per the Epic #546 invariant, a
  review outcome, detected gap, or repository content never creates one.
- **Errors.** 401 / 403 / 404 / transport failures raise typed errors
  naming the call and the fix (`gh auth login`, needed scopes).
- **Tokens.** Read from `GH_TOKEN` / `GITHUB_TOKEN`, handed to `gh` only
  through its environment, redacted from error text, never logged or
  persisted.
- **Mock seam.** The `transport` constructor argument replaces `gh`;
  tests use it and never touch the network.
