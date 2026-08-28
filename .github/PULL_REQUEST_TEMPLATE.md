<!--
This template is written for the reviewer, not just the author.
A PR in this repository may touch any combination of Skill behavior,
policy, packaging, governance, or documentation — none of these are
"secondary." Use "None" / "N/A" for sections that genuinely don't apply;
do not fabricate content to fill a section.

Keep the body human-scannable (policies/github-issue-pr-authoring.md):
answer what changed / why / how it was validated / what needs reviewer
attention. Fill the sections that apply, mark the rest "None"/"N/A", and
link the Issue or a canonical doc instead of pasting execution logs, full
test output, restated requirements, or an implementation diary. Summarize
validation (e.g. "564 tests passed, git diff --check clean"); paste
detailed output only when a specific result helps the reviewer.
-->

## Summary

<!-- What does this PR change, and why? Explain in reviewer-oriented
terms (what changes for a consumer of this repository), not a
restatement of which files were touched. -->

## Change Type / Surface

<!-- Check every surface this PR touches. A PR may legitimately span
several — do not force a single choice. -->

- [ ] Skill behavior (`SKILL.md`)
- [ ] Skill-specific policy (`skills/<name>/policies/`)
- [ ] Shared policy (`shared/policies/`)
- [ ] Runbook (`skills/<name>/runbooks/`)
- [ ] Review/report template (`shared/templates/`, `skills/<name>/templates/`)
- [ ] Script / validator / tooling (`scripts/`) or test suite (`tests/`)
- [ ] Packaging / distribution (`package-skills.sh` / `.ps1`, `metadata/skill.yaml`)
- [ ] Runtime metadata / adapter (e.g. `agents/openai.yaml`)
- [ ] Repository governance / agent instructions (`AGENTS.md`, `CLAUDE.md`)
- [ ] Architecture (`docs/ARCHITECTURE.md`)
- [ ] README / documentation (root or Skill `README.md`, `docs/CODE_REVIEW_COMPARISON.md`, other docs)
- [ ] GitHub workflow / repository configuration (`.github/`)
- [ ] Other: <!-- describe -->

## Skills Affected

<!-- A repository-level or governance-only PR is a first-class case,
not an incomplete Skill PR — select "Neither / repository-level only"
without treating it as missing information. -->

- [ ] `local-code-review`
- [ ] `github-pr-review`
- [ ] Both
- [ ] Neither / repository-level only

## Behavioral Change

**Before:**
<!-- Previous behavior / rule / workflow. "N/A" if this PR adds something
that didn't exist rather than changing existing behavior. -->

**After:**
<!-- New behavior / rule / workflow. -->

**Intentionally unchanged:**
<!-- Adjacent behavior or governance that a reviewer might expect this
PR to touch but deliberately does not. Especially important when a
reasoning/documentation change sits next to governance rules that must
remain untouched. -->

## Governance Impact

<!--
State "None" if this PR does not alter governance.

If it does, describe exactly which governance contract changes and why —
e.g. self-review prevention, reviewer ownership, invocation approval,
reviewer identity, SHA/delta review boundaries, HEAD revalidation,
mutation boundaries, severity semantics, Approve/Request Changes
behavior, orchestration boundaries, or Git/branch/merge lifecycle rules.
-->

<details>
<summary>Governance areas touched (optional, for discoverability)</summary>

- [ ] Self-review prevention
- [ ] Reviewer ownership
- [ ] Invocation approval
- [ ] Reviewer identity
- [ ] SHA / delta review boundaries
- [ ] HEAD revalidation / TOCTOU protection
- [ ] Mutation boundaries
- [ ] Severity semantics
- [ ] Approve / Request Changes behavior
- [ ] Orchestration boundaries
- [ ] Git / branch / merge lifecycle

</details>

## Repository Instructions / Documentation

**Files affected:**
<!-- AGENTS.md, CLAUDE.md, docs/ARCHITECTURE.md, README.md, Skill README,
docs/CODE_REVIEW_COMPARISON.md, other docs, or None. -->

**Documentation impact:**
<!--
What repository behavior, architecture, usage, reviewer guidance, or
human/Agent understanding changed? Distinguish descriptive documentation
(explains existing behavior) from normative/operational documentation
(itself defines behavior — e.g. AGENTS.md orchestration rules, a
canonical policy, or an architectural contract in docs/ARCHITECTURE.md).
-->

## Skill / Policy Contract Impact

<!--
If applicable:
- What Skill contract changed (identity, inputs, output contract, stop
  conditions, mutation boundary)?
- What shared or Skill-specific policy changed?
- Did precedence or ownership move between shared/ and a Skill's own
  policies/runbooks?
Otherwise: None.
-->

## Packaging / Distribution

<!--
Does this change affect packaged Skill contents, package-relative links,
metadata/skill.yaml, archive independence, or runtime portability?

Distinguish repository-only files from files that enter a packaged Skill
archive, and confirm any references inside packaged files still resolve
correctly after packaging.

If not applicable: None.
-->

## Runtime / Portability Impact

<!--
Does this introduce or change assumptions about Claude Code, Codex,
Cursor, OpenCode, GitHub CLI/API, or another specific runtime/tool?

If no runtime-specific assumption changed: None.
-->

## Validation

**Automated:**
<!-- command → result. e.g. `python3 scripts/validate-skill-metadata.py` → pass -->

**Manual / semantic:**
<!-- behavior or contract independently verified by reading/reasoning,
not just running a script. -->

**Not run / not applicable:**
<!-- e.g. "documentation-only change; no validator applies" -->

## Reviewer Focus

<!--
Where should the reviewer spend attention? Call out:
- subtle behavior changes,
- governance boundaries,
- moved responsibilities,
- compatibility concerns,
- documentation that is normative rather than descriptive,
- validator assumptions,
- packaging implications,
- or anything intentionally easy to miss.
-->

## Change Map

<!-- Optional, responsibility-oriented — not a restatement of the
changed-files tab. Group related files by what role they play, e.g.:

- AGENTS.md — repository orchestration rule
- shared/policies/review-scope.md — canonical review invariant
- skills/github-pr-review/... — GitHub-specific consumption of the above
- scripts/... — validation/packaging tooling
- tests/... — test suite and test-only reference models
- README.md — documentation/discovery only
-->
