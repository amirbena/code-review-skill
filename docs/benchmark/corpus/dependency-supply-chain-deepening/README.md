# Dependency / Supply-Chain Deepening Regression Fixture Corpus

Repository-development artifact for GitHub Issue
[#188](https://github.com/amirbena/code-review-skill/issues/188), a
deterministic fixture corpus for the Dependency / Supply-Chain deepening
capability tracked by parent Issue
[#181](https://github.com/amirbena/code-review-skill/issues/181) and its
own parent, the adaptive specialist-depth composition contract
[#82](https://github.com/amirbena/code-review-skill/issues/82). This is a
**focused sub-corpus** of [`benchmark-case/v2`](../../fixture-format.md)
fixtures pinning representative Dependency / Supply-Chain deepening
outcomes as follow-up quality hardening — it validates domain correctness
after the capability exists and does not define, gate, or redesign it.
The capability itself is designed and packaged in
[`../../../dependency-supply-chain/dependency-supply-chain-model.md`](../../../dependency-supply-chain/dependency-supply-chain-model.md)
and
[`../../../../shared/policies/review-scope.md`](../../../../shared/policies/review-scope.md),
"Dependency / supply-chain deepening review," which this corpus's
expectations must stay consistent with.

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of [`../`](../README.md)
and [`../../`](../../README.md) this is **not** packaged into either Skill
archive and no packaged Skill resource depends on it — it is consumed only
by this repository's own test suite, through the single reference
validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
(never a second one).

## Selection principle

Issue #188's scope lists six required outcome shapes; each case isolates
one so a regression in any one is unambiguous. The cases split evenly
between "the capability engages and flags a real, evidenced risk" and
"the capability correctly stays quiet," following the same discipline the
Database / Migration and Security deepening corpora use for their own
negative cases — **each `clean` case fails a distinct precondition**, so a
regression in either negative reason is caught even if the other stays
correct:

- **Major-version bump with a known breaking API change** — a dependency
  crosses a semver-major boundary, and a call site elsewhere in the diff's
  own base still uses an API that version removed. Flagged. Mirrors the
  capability doc's "Major-version compatibility" concern area.
- **Runtime/platform minimum raised** — a manifest's minimum runtime
  version is raised while an unrevised, still-present supported-versions
  claim elsewhere in the repository now contradicts it. Flagged. Mirrors
  "Runtime/platform requirement changes."
- **Large unexpected transitive dependency expansion** — one new direct
  dependency is added to the manifest, but the lockfile diff also adds
  several unrelated packages that new dependency's own entry does not
  require. Flagged. Mirrors "Dependency expansion."
- **Unpinned GitHub Actions reference** — a new automation step is pinned
  to a mutable tag while every existing step in the same workflow is
  already pinned to a commit SHA, an inconsistency with the repository's
  own established convention. Flagged. Mirrors "Provenance / trust and
  unpinned automation references."
- **Safe patch-level bump** — a dependency moves a patch version with
  proportionate, fully explained lockfile churn and no other concern area
  implicated. `clean`. This case *does* touch a qualifying manifest and
  lockfile — it fails the concern-area evidence bar in §3 of the
  capability doc, not the diff-recognition signal in §2.
- **No manifest/lockfile/Dockerfile/Actions file touched at all** — an
  ordinary application-code rename with no dependency-related file in the
  diff. `clean`. This case fails the diff-recognition signal itself (§2):
  there is nothing for this pass to reason about, distinct from the safe
  patch-bump case where a qualifying file changes but is not flagged.

Each case is a crafted, self-contained patch (`input.patch` + `input.base`)
against small, purpose-built npm/`pyproject.toml`/GitHub-Actions fixtures,
keeping the corpus runnable without network access and consistent with the
other corpora under [`../`](../README.md). Per Issue #188's non-goals, this
corpus is deliberately small, adds no new severity/evidence semantics, and
does not redefine the capability's concern areas — every case mirrors a
concern area already documented in
[`dependency-supply-chain-model.md`](../../../dependency-supply-chain/dependency-supply-chain-model.md).
It also contains no cross-domain composition fixture; that is
[#85](https://github.com/amirbena/code-review-skill/issues/85)'s job,
reusing this corpus.

## Cases

| File | Outcome shape | A correct review must… | Decision |
|---|---|---|---|
| [`dependency-supply-chain-deepening-major-version-breaking-api-change.yaml`](dependency-supply-chain-deepening-major-version-breaking-api-change.yaml) | major-version bump with a known breaking API change | report one **P1**: lodash crosses its 3.x → 4.x boundary and `reports.js` still calls the removed `_.pluck` | `changes-required` |
| [`dependency-supply-chain-deepening-runtime-minimum-raised.yaml`](dependency-supply-chain-deepening-runtime-minimum-raised.yaml) | runtime/platform minimum raised, contradicting a documented claim | report one **P1**: `requires-python` is raised to `>=3.11` while README.md still documents 3.8+ support | `changes-required` |
| [`dependency-supply-chain-deepening-transitive-dependency-expansion.yaml`](dependency-supply-chain-deepening-transitive-dependency-expansion.yaml) | large unexpected transitive dependency expansion | report one **P1**: adding `csv-stringify` also drags in five unrelated webpack/enzyme packages the new dependency does not require | `changes-required` |
| [`dependency-supply-chain-deepening-unpinned-github-actions-reference.yaml`](dependency-supply-chain-deepening-unpinned-github-actions-reference.yaml) | unpinned GitHub Actions reference inconsistent with repo convention | report one **P1**: a new deploy step is pinned to a mutable tag while every existing step in the same workflow is pinned to a commit SHA | `changes-required` |
| [`dependency-supply-chain-deepening-safe-patch-bump-clean.yaml`](dependency-supply-chain-deepening-safe-patch-bump-clean.yaml) | safe patch-level bump | report **nothing** — proportionate, explained lockfile churn with no concern area implicated | `clean` |
| [`dependency-supply-chain-deepening-no-manifest-touched-not-implicated-clean.yaml`](dependency-supply-chain-deepening-no-manifest-touched-not-implicated-clean.yaml) | no manifest/lockfile/Dockerfile/Actions file touched | report **nothing** — the domain is not materially implicated, no diff-recognition signal exists to reason from | `clean` |

Per-case provenance and a one- or two-sentence rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`) and in the
header comment.

## Validation

[`../../../../tests/unit/benchmark/test_dependency_supply_chain_deepening_corpus.py`](../../../../tests/unit/benchmark/test_dependency_supply_chain_deepening_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
used for the worked example and every other corpus. It never defines a
second one, and asserts: the sub-corpus stays small and documented; every
required outcome shape is present; every case pins an explicit `decision`
consistent with its required findings; every flagged case's required
finding is `P1`; every strictly clean case carries no findings at all;
the two clean cases fail distinct non-activation reasons; and every
finding's anchor resolves inside its own case's patch or base. Matching a
reviewer's output to these expectations and scoring it are out of scope
here (Issues #41 / #52 / #54). Peer review of the expected findings
themselves happens on the pull request.
