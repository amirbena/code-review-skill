# Rulesets vs. Classic Branch Protection — Required Status Check Research

Repository-development research for GitHub Issue
[#93](https://github.com/amirbena/code-review-skill/issues/93) (relates to
#34, unblocks #95). It compares the two GitHub mechanisms that can make the
aggregated review status a **required check**, so the setup and detection
behavior in
[`review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md)
("Enforcement-state detection (read-only)", "Explicit opt-in required-check
setup") rests on documented GitHub behavior.

This is a research record, not a policy. It does not re-derive detection or
mutation-safety rules (those are canonical in the policy above) and performs
no mutation. Claims are taken from the official GitHub documentation cited in
[Sources](#sources); anything not stated there is marked *unverified*.

---

## Summary

| Question | Rulesets | Classic branch protection |
| --- | --- | --- |
| Rules per branch | Many rulesets can apply to one branch at once | One protection rule applies to a branch |
| Required-check surface | `required_status_checks` rule inside a ruleset | `required_status_checks` on the branch protection rule |
| Context entry | `{context, integration_id?}` | `checks: [{context, app_id?}]` (`contexts` string list is being phased out) |
| Up-to-date requirement | `strict_required_status_checks_policy` (required boolean) | `strict` |
| Source pinning | optional `integration_id` | `app_id`; omit = auto-select recent provider; `-1` = any app |
| Bypass | Named bypass actors (users, teams, GitHub Apps) | Admins bypass by default unless "Do not allow bypassing the above settings" is on |
| Visibility | Anyone with read access can view active rulesets | Not stated as read-visible in the cited docs |
| Enable/disable | `Active` / `Disabled` enforcement status, no deletion needed | Delete or edit the rule |
| Scope | Repository, plus organization-wide rulesets on Enterprise plans | Per repository branch pattern |
| Add one context atomically | No: `PUT` replaces the ruleset body | Yes: `POST .../required_status_checks/contexts` adds without replacing the list |

## Capabilities

Both can require a named status context to be successful before merge. Classic
protection treats `successful`, `skipped`, and `neutral` as passing, and lets
a check be pinned to a specific GitHub App or accepted from any source.
Rulesets express the same via `integration_id` and add layering, bypass
actors, an enforcement toggle, and (on Enterprise plans) org-wide targeting.
GitHub itself recommends rulesets over branch protection because only one
protection rule applies at a time. Both mechanisms warn that duplicate check
names across workflows make results ambiguous, which matters because this
capability publishes exactly one stable context.

## API surface

**Classic** (`/repos/{owner}/{repo}/branches/{branch}/protection/required_status_checks`):
`GET`/`PATCH` on the resource, and `GET`/`POST`/`PUT`/`DELETE` on `/contexts`.
Updating requires admin or owner permission, and branch protection must
already be enabled. `POST .../contexts` is an additive operation, which fits
the "add one context, remove nothing" constraint natively.

**Rulesets** (`/repos/{owner}/{repo}/rulesets`): list, create, get, update
(`PUT`), delete, plus history endpoints; and
`GET /repos/{owner}/{repo}/rules/branches/{branch}`, which returns the
rules that apply to a branch. That last endpoint is the natural read-only
detection call because it already aggregates every applicable ruleset, so a
reader does not have to evaluate targeting and enforcement itself.
The ruleset docs do not document a per-context add endpoint. Adding one
context means reading the ruleset, appending to `required_status_checks`, and
writing the whole ruleset back, so the read-normalize-diff-verify procedure in
the policy is load-bearing for rulesets in a way it is not for classic
`POST .../contexts`. Per-endpoint permission details were not stated in the
cited REST page (*unverified*; check the fine-grained token permission before
implementing).

## Precedence when both exist on one branch

There is no precedence or override: they run in parallel and all applicable
rules are enforced together. Multiple rulesets are aggregated, and "the most
restrictive version of the rule applies". Consequences for this capability:

- A context is `ENFORCED` if **either** mechanism requires it, matching the
  existing policy definition.
- A context required by only one mechanism is still enforced. It cannot be
  "outvoted" by the other mechanism omitting it.
- `NOT ENFORCED` is only correct when **both** were readable and neither
  lists it, hence the policy's `UNKNOWN` fallback when either read fails.
- Removing the context from one mechanism does not un-require it if the other
  still lists it. Setup should therefore target one mechanism and report the
  other's state, never assume one supersedes the other.

## Migration and compatibility

The docs present rulesets as the successor and note the two can coexist, so no
forced migration exists. Practical considerations:

- Repositories mid-migration may legitimately have the same context in both
  places, so duplicates are not an error to "fix".
- A ruleset cannot be inferred from a branch-protection API response, and vice
  versa. Detection needs both reads.
- Org-level rulesets can require the context for a repository without any
  repository-local configuration, so a repo-only read can yield a false
  `NOT ENFORCED`. The branch rules endpoint above is expected to include them
  (*unverified*; confirm before relying on it).
- `do_not_enforce_on_create` exists only for rulesets; classic protection has
  no equivalent.

## Recommendation for #95

1. **Detection:** read `GET .../rules/branches/{branch}` and classic
   `.../protection/required_status_checks`; `ENFORCED` if either lists the
   context, `UNKNOWN` if either read fails.
2. **Setup target:** prefer the mechanism already governing the branch. If a
   ruleset requires status checks, edit that; if only classic protection
   exists, use additive `POST .../contexts`. Do not create a new mechanism on
   a branch that already has the other, without an explicit request.
3. **Pin the source** (`integration_id` / `app_id`) to the publishing App
   where known, to keep another app from satisfying the check.
4. Keep the read-back verification from the policy for both paths.

## Sources

- [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
- [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [REST API: branch protection](https://docs.github.com/en/rest/branches/branch-protection)
- [REST API: repository rules and rulesets](https://docs.github.com/en/rest/repos/rules)
