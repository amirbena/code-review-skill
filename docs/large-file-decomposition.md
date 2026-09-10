# Large-File Decomposition — Inventory and Sequence

Repository-development planning document for the structural-decomposition
maintainability pass tracked in issue #192. It is **explanatory**, not
canonical: the behavioral rule it serves lives in
[`../AGENTS.md`](../AGENTS.md) ("File size is a review trigger, not a
limit"). This file is a working inventory — rows are retired as the
matching decomposition step lands.

## Guiding principle

**One behavioral rule → one authoritative home.** Skills, runbooks,
templates, and secondary documentation reference canonical contracts
instead of substantially restating them. Size is decomposed only where it
reflects a real seam — multiple responsibilities, a restated contract,
orchestration mixed with implementation, or a natural extraction boundary.
A genuinely cohesive large file is kept as-is; line count alone is never a
reason to split and is never CI-enforced.

## Classification vocabulary

| Tag | Meaning |
| --- | --- |
| **keep** | Cohesive; single responsibility; size is inherent. No action beyond optional pruning. |
| **reduce duplication** | Substantially restates a contract owned elsewhere. Trim to a summary + pointer. |
| **extract** | One file, several separable responsibilities/modules. Pull sub-modules out; keep a thin core. |
| **split** | Distinct architectural sub-domains bolted into one file. Separate them into sibling canonical files. |

## Preservation constraints (every step)

- No change to behavior or public contracts: the finding schema, script
  CLI surfaces, workflow triggers/outputs, and Skill discovery metadata
  stay byte-stable.
- Packaged Skill archive contents and layout stay identical; if a packaged
  resource set does change, `scripts/package-skills.sh` and
  `scripts/package-skills.ps1` are updated together and the
  packaging-runtime-boundary tests still pass.
- `scripts/*.sh` ↔ `scripts/*.ps1` parity is preserved; CI-only Linux
  automation needs no PowerShell counterpart, but that is stated where it
  applies.
- Test semantics are unchanged; doc-structure policy tests
  (`tests/policy/test_*_docs.py`) still pass against any moved sections.
- One step per pull request. After each step run
  `python3 -m unittest discover -s tests -t .`, the Skill-metadata
  validator, both `package-skills` scripts, and `git diff --check` before
  starting the next.

## Priority 1 — executable and CI material

| File | Lines | Tag | Rationale and target shape |
| --- | ---: | --- | --- |
| `scripts/validate-skill-metadata.py` | 725 | split + extract | ~335 lines of module-level expectation tables (per-file required headers/markers mirroring the invocation-options model, OpenAI interface field maps, forbidden-phrase lists) precede the logic, then generic helpers, a ~175-line `validate()`, and `validate_github_policy_family()`. Target: a `scripts/skill_metadata/` package — expectation data in one module, focused checkers (frontmatter, declared-resources, markdown-link containment, github-policy-family), a thin `validate()` orchestrator + `main()`. Mirrors the existing `release_lib/` split. Dev/CI validator only — not shipped; the path is referenced by `package-skills.sh`, so a moved entrypoint updates both package scripts. |
| `scripts/release_lib/cli.py` | 445 | extract | Already packaged, but now holds eight `_cmd_*` handlers plus `assess()` / `Assessment` and GitHub-output helpers. Target: command handlers in focused modules (e.g. `release_lib/commands/`), the assessment domain type in `release_lib/assessment.py`, `cli.py` reduced to parser wiring + dispatch. |
| `.github/workflows/release-worthiness.yml` | 346 | completed | Issue #197 moved the reusable `run: |` logic into tested helpers: base-ref resolution and release-commit identity resolution are `release_worthiness.py` subcommands (`resolve-base-ref`, `resolve-app-identity` in `release_lib/commands/workflow.py`), and the shared "package + `unzip -t` + confirm both zips" sequence is `scripts/release/verify-skill-archives.sh`. The YAML keeps triggers, permissions, `needs`/gating, concurrency, the publish sequence, and step summaries. Release automation is CI-only (Linux); the helper states it has no `.ps1` counterpart. |
| `scripts/package-skills.ps1` | 354 | completed | Issue #196 moved the shared and per-Skill resource mappings, archive names, and required entries into `scripts/package-manifest.json`; both platform scripts now consume it. |
| `scripts/package-skills.sh` | 330 | completed | Paired with the PowerShell implementation above. Platform-specific staging, validation, containment, link adaptation, and archive creation remain in each script; archive contents and layout are preserved. |
| `scripts/claim_issue.py` | 389 | extract (optional) | Single responsibility (reconcile claim state from trusted receipts), but the receipt-parsing/replay primitives (`_receipts`, `_checkpoints`, `_replay_anchor`, `_repository_history`, `_active_restriction`) could move to a `scripts/claim_lib/` module, leaving `reconcile()` + `main()`. Lowest priority in this tier; acceptable to keep if it still reads as one responsibility. |

## Priority 2 — Skill-runtime canonical material

| File | Lines | Tag | Rationale and target shape |
| --- | ---: | --- | --- |
| `shared/templates/finding.md` | 528 | completed | Issue #198 split the field/quality contract (kept in `finding.md`) from the canonical rendering exemplars (full / inline / human-inline / summary-pointer), now in `shared/templates/finding-rendering.md`; the two are cross-linked and both packaged. |
| `shared/policies/review-context.md` | 441 | completed | Issue #198 extracted the **Jira context resolution** sub-domain (transport-neutral procedure, comment classification, precondition rules) into `shared/policies/jira-context.md`; `review-context.md` keeps the four-concepts model, precedence, boundaries, and a linking overview. |
| `shared/policies/review-scope.md` | 593 | completed | Issue #198 extracted the root-cause / model-completeness consolidation sub-domain into `shared/policies/root-cause-consolidation.md` and the affected-test / test-impact analysis sub-domain into `shared/policies/affected-test-analysis.md`; `review-scope.md` keeps base scope, architectural-placement fidelity, and a linking overview under each moved heading. |
| `skills/github-pr-review/SKILL.md` | 368 | reduce duplication | Sections 6–7 (Reviewer Ownership & Delta Re-Review; Review Action Authority & Mutation Boundary) restate material owned by `policies/stateful-delta-rereview.md` and `policies/review-action-authorization.md`. Target: entry contract + navigation + high-level flow + pointers. |
| `skills/github-pr-review/runbooks/active-pr-review.md` | 510 | reduce duplication | Two headers only (`## Flow`, `## Steps`) over a ~400-line step monolith. Target: procedure only; behavioral invariants restated from `review-output.md` / `review-action-authorization.md` / `stateful-delta-rereview.md` move to (or stay in) those policies and are referenced. Split step groups only if it stays procedural. |
| `skills/local-code-review/runbooks/local-review.md` | 363 | reduce duplication | `## Re-review discipline` and `## Constraints` overlap `policies/invocation-approval.md` and shared review-scope. Target: keep the procedure, reference the contracts. |
| `skills/github-pr-review/policies/stateful-delta-rereview.md` | 353 | reduce duplication | Section 1 is literally "Reuse, do not redefine"; change classes and identity are owned by `docs/findings/delta-re-review-contract.md` and the finding-identity docs. Target: hold only the github-pr-review execution specifics, reference the contracts. |
| `skills/local-code-review/templates/local-review-report.md` | 376 | reduce duplication | The ~150-line `## Rules` section is semi-normative and the repeated `### Decision` / `### Findings` variants restate structure. Target: fixed report skeleton separated from rules narrative; rules must not restate shared finding/severity contracts. |
| `skills/github-pr-review/templates/external-review-summary.md` | 353 | reduce duplication | Six near-duplicate `## Code Review` example blocks plus a `## Rules` section. Target: keep the canonical examples, factor the shared preamble, move any normative rules to `review-output.md` where they belong. |
| `skills/github-pr-review/policies/review-action-authorization.md` | 423 | keep | One tightly coupled security domain (modes, trusted authorization, reviewer independence, merge boundary). Cohesive — keep; only check `## Composition with existing guarantees` / `## Reporting` for restatement. |
| `skills/github-pr-review/policies/review-output.md` | 375 | keep | Cohesive (analysis vs. publication, batching, summary, decision, ordering). Keep; verify overlap with the external-review-summary template resolves toward this policy. |
| `skills/local-code-review/policies/invocation-approval.md` | 333 | keep | Single invariant (approval is non-persistent and must originate in the current interaction) explored thoroughly. Keep; optional trim of `## Why this exists`. |

## Priority 3 — long-form canonical / reference documentation

Lowest priority. These are **not** split for exceeding the threshold —
only where a real boundary or genuine duplication exists.

| File | Lines | Tag | Rationale and target shape |
| --- | ---: | --- | --- |
| `docs/ARCHITECTURE.md` | 621 | completed | Issue #200 pruned the drift: `### Implemented since the initial design` became `### Optional capabilities` (present tense), the benchmark harness and the now-packaged stateful delta re-review moved to a new `### Repository-development instrumentation (not packaged)` subsection, and `### Future work (not implemented)` was trimmed to the three genuinely-unbuilt items. No structural split; §-numbering and role as the system map preserved. |
| `docs/findings/finding-identity-requirements.md` | 497 | completed | Issue #200 made this document the single declared owner of the input inventory (§4) and the must-survive / must-change scenario set (§2, §3), with ownership markers under those headings. |
| `docs/findings/finding-stable-identity.md` | 410 | completed | Paired with the row above: §2 keeps its derivation-specific rules and a short rationale but no longer re-lists the guaranteed inputs, referencing `finding-identity-requirements.md` §4 as owner. |
| `docs/findings/finding-matching-strategy.md` | 693 | keep | Explicitly a research recommendation — longer content is the point. Keep; ensure normative algorithm text is not a competing copy of the identity/lifecycle contracts. |
| `docs/findings/reviewed-sha-state-contract.md` | 647 | keep | Canonical contract; the A–G required examples serve two-reader determinism. Keep. |
| `docs/findings/finding-lifecycle-contract.md` | 386 | keep | Distinct canonical contract. Keep; verify the "Terminology and ownership" section does not diverge from the delta-re-review contract. |
| `docs/findings/delta-re-review-contract.md` | 371 | keep | As above. |
| `docs/benchmark/fixture-format.md` | 438 | keep | Canonical benchmark schema with worked examples; `tests/policy/test_benchmark_fixture_docs.py` asserts its sections. Keep. |
| `docs/benchmark/missed-and-incorrect-findings.md` | 351 | keep | Canonical metric contract with asserted structure. Keep. |
| `docs/CODE_REVIEW_COMPARISON.md` | 316 | keep | Explanatory comparison, cohesive, just over the threshold. Keep; watch growth. |
| `CHANGELOG.md` | 308 | n/a | Generated by release automation; not hand-authored. Excluded from the pass. |

## Below the trigger — watch list only (no action now)

`skills/github-pr-review/runbooks/passive-pr-review.md` (298),
`AGENTS.md` (293, governed by its own "Maintainability and extension"
section), `docs/benchmark/match-criteria.md` (289),
`docs/benchmark/severity-accuracy.md` (285),
`docs/benchmark/duplicate-noise.md` (285),
`skills/local-code-review/policies/pr-context.md` (284),
`docs/benchmark/regression-report.md` (283).

## Execution sequence

Each numbered item is an independently reviewable, independently closable
step. Line counts are from `main` at the time of writing and drift; the
tags above, not the numbers, decide whether a step is still worth doing.

1. `scripts/validate-skill-metadata.py` → `scripts/skill_metadata/` package.
2. `scripts/release_lib/cli.py` → extract command handlers + `assess()`.
3. `scripts/package-skills.{sh,ps1}` → shared declarative package manifest.
4. `.github/workflows/release-worthiness.yml` → shell logic into tested helpers.
5. *(optional)* `scripts/claim_issue.py` → `scripts/claim_lib/` primitives.
6. `shared/templates/finding.md` → contract / rendering split. *(done — Issue #198, `finding-rendering.md`.)*
7. `shared/policies/review-context.md` → extract Jira resolution policy. *(done — Issue #198, `jira-context.md`.)*
8. `shared/policies/review-scope.md` → extract root-cause-consolidation and affected-test sub-policies. *(done — Issue #198, `root-cause-consolidation.md` + `affected-test-analysis.md`.)*
9. `skills/github-pr-review/SKILL.md` → trim restated ownership/authorization detail to pointers.
10. `active-pr-review.md` + `local-review.md` runbooks → procedure-only.
11. `stateful-delta-rereview.md`, `local-review-report.md`, `external-review-summary.md` → de-duplicate against canonical owners.
12. `docs/ARCHITECTURE.md` → prune drift sections (no structural split). *(done — Issue #200.)*
13. `finding-identity-requirements.md` ↔ `finding-stable-identity.md` → single owner for the shared tables. *(done — Issue #200.)*

Steps 1–5 land before 6–11, and 6–11 before 12–13: executable and
Skill-runtime material is decomposed before long-form documentation.
