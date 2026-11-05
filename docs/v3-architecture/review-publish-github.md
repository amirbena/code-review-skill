# `review-publish-github` — disposition record

Explanatory record for [#844](https://github.com/amirbena/code-review-skill/issues/844),
under the [v3 ADR](adr-v3-review-core.md) (§3, §5, S7). The Skill itself is
[`skills/review-publish-github/`](../../skills/review-publish-github/SKILL.md);
a canonical rule there wins any conflict with this page. Nothing here is
packaged, and v2 behavior is unchanged until the cutover
([#851](https://github.com/amirbena/code-review-skill/issues/851)).

## Where the v2 publication rules went

| v2 source | In v3 |
| --- | --- |
| `review-action-authorization.md` (PASSIVE / SEMI / ACTIVE) | Invoking the Skill is the request (`SKILL.md` step 1). SEMI is removed; a preview is the Core report. |
| `review-authority.md` | `rules/authority.md`: self-review and shared authority give `COMMENT`; unresolved facts and missing permission fail closed. |
| `review-output.md` (batched submission, HEAD revalidation) | `SKILL.md` steps 7–8. A moved HEAD is also Core trigger 3. |
| `finding-placement.md`, `review-evidence.md` | `rules/placement.md`. |
| `inline-finding.md`, `external-review-summary.md` | `templates/review.md`. |

## Benchmark cases

| Corpus | Disposition |
| --- | --- |
| `publication-mode` | Re-mapped to this Skill. The `passive`/`active`/`self_review`/`authority_boundary` shapes become [`test_review_publish_github.py`](../../tests/integration/github/test_review_publish_github.py) (no request → nothing published, self-review → `COMMENT`, stale HEAD, permission denied). The `semi` and `mode_invariant` shapes are removed: SEMI no longer exists. The v2 corpus stays until the cutover. |
| `github-enforcement-authorization` | Removed with the status check and required-check setup it guards (ADR §6). v3 has no governance mutation to authorize. |
| `finding-placement` | Re-mapped to this Skill for the inline-vs-summary decision ([`rules/placement.md`](../../skills/review-publish-github/rules/placement.md)). The fix-location derivation cases belong to `review-core`. |

The corpora and the v2 policies they exercise are deleted at the cutover,
not here.

## `scripts/github_integration/`

Kept only where it implements S7: `boundary.py` (the authenticated call
boundary and the write allow-list, which admits review and review-comment
POSTs and nothing else). `enforcement.py`, `status_publisher.py`,
`required_check_setup.py` and `lifecycle_proof.py` implement the removed
status and required-check machinery and are deleted at the cutover.

## Test model

[`tests/reference/review/publish_github.py`](../../tests/reference/review/publish_github.py)
is a test-only model of the Skill with an in-memory PR fake; it is never
imported at Skill runtime.

## Manual publish

Validation asks for one manual publish to a test PR. That needs a live
GitHub PR and write access, so it is recorded in the PR description rather
than here.
