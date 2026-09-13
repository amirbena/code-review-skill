# Dependency / Supply-Chain Deepening Model

Repository-development design record for **[#181](https://github.com/amirbena/code-review-skill/issues/181)**.
Not packaged; explanatory. It is the canonical home for the recognized
manifest/lockfile/build-file inputs and their diff-recognition signals,
the five concern areas with worked examples, the fail-closed rule for an
unrecognized format, and the smallest useful first implementation. The
packaged
[`shared/policies/review-scope.md`](../../shared/policies/review-scope.md),
"Dependency / supply-chain deepening review," defines the operative rule
a reviewer actually applies and references this document by name; it does
not restate this document's rationale or worked examples.

The follow-up fixture corpus tracked by
[#188](https://github.com/amirbena/code-review-skill/issues/188) pins
representative outcomes for the cases in §3 once it lands; per #181's
acceptance criteria, that corpus is quality hardening after this
capability exists, not a prerequisite for it.

## 1. Problem and goal

Dependency and build-system changes carry risk that diff-only review does
not evaluate on its own: a major-version bump, a raised runtime/platform
minimum, an unexpected transitive-dependency expansion, a dependency
source or automation reference that becomes less verifiable, or a
build/toolchain change the code's own evidence is incompatible with. A
manifest, lockfile, Dockerfile, or GitHub Actions workflow changing is
easy to detect — the reviewer's harder problem is reasoning about whether
that change actually carries one of those risks, without either inventing
a compatibility claim the diff cannot support or missing a real one.

The goal is a reviewer capability that reasons about materially
implicated dependency/supply-chain semantics and raises evidence-backed
findings for them, tied to the existing severity and evidence model — no
new severity, no probability score — that fails closed when a manifest,
lockfile, or build-file format cannot be recognized, and that never
activates merely because a qualifying file changed.

## 2. Recognized inputs and their diff-recognition signal

| Input | Diff-recognition signal |
| --- | --- |
| Package manifest / lockfile | A changed `package.json`/`package-lock.json`, `requirements.txt`/`poetry.lock`/`Pipfile.lock`, `go.mod`/`go.sum`, `Cargo.toml`/`Cargo.lock`, `pom.xml`/`build.gradle`, or an equivalent ecosystem manifest/lockfile pair. |
| Container base image | A changed Dockerfile `FROM` line, or an equivalent base-image reference in a container/build definition. |
| CI / automation action reference | A changed GitHub Actions workflow `uses:` line, or an equivalent pinned automation/action reference in another CI system. |

Recognition is a **diff-level signal that this pass may be in scope**,
never itself the finding: one of the five concern areas in §3 still has
to be reasoned about, from the change's own evidence, before anything is
reported. The same discipline "Evidence is semantic, not structural" in
[`review-scope.md`](../../shared/policies/review-scope.md) already applies
elsewhere in this policy applies here identically — a manifest, lockfile,
Dockerfile, or package-related filename changing is never, by itself,
sufficient to engage domain-specific deepening; it is not equivalent to
"run dependency/supply-chain specialist depth," per
[`specialist-depth.md`](../../shared/policies/specialist-depth.md),
"Activation: evidence-driven, never routed."

## 3. Concern areas and worked examples

| Concern area | Flag when | Do not flag when |
| --- | --- | --- |
| Major-version compatibility | A dependency bump crosses a semver-major (or ecosystem-equivalent) boundary and the diff's own evidence — a changelog/release-notes reference, a known breaking change, or call sites still using a removed/altered API — shows the bump requires an adaptation the diff does not make. | The bump is a minor/patch-level change, or a major bump whose consuming call sites in the diff already match the new API. |
| Runtime/platform requirement changes | The minimum language/runtime/platform version is raised (`engines`, `requires-python`, a Dockerfile base-image tag, a CI runner/toolchain version) and the codebase or its build/CI configuration still depends on a feature unavailable at the new minimum, or the change silently narrows the versions the repository claims to support. | The raised minimum is consistent with what the codebase already requires, and no supported-versions claim is contradicted. |
| Dependency expansion | A lockfile diff adds materially more transitive dependencies than the direct manifest change would explain, and the expansion is unaccounted for by the change's own evidence. | A routine patch-level bump's incidental lockfile churn, or an expansion the manifest change directly explains (e.g., one new direct dependency with a modest, proportionate transitive set). |
| Provenance / trust and unpinned automation references | A CI action or automation reference is pinned to a mutable ref (branch/floating tag) instead of an immutable commit SHA where the repository's own existing convention pins other references that way, or a dependency's source changes (registry, or a registry package replaced by a git/URL dependency) in a way that changes who is trusted to publish it. | The repository's own existing convention already uses mutable refs consistently (no inconsistency to flag), or the source change is to an equally or more verifiable source. |
| Build/runtime incompatibility | A build-file change (Dockerfile, `build.gradle`, `pom.xml`, a compiler/toolchain pin) changes the compiler/toolchain/runtime version code is built or run with, and the code's own evidence (syntax, an API it calls) is incompatible with that version. | The toolchain/runtime change is compatible with the code as written, with no evidenced incompatibility. |

### Worked example — dependency expansion vs. routine churn

A manifest change that adds one new direct dependency, and a lockfile
diff that adds a correspondingly modest set of that dependency's own
transitive dependencies, is routine churn: not flagged. The same manifest
change paired with a lockfile diff that adds dozens of unrelated packages
with no explanation traceable to the added dependency's own declared
requirements is a materially implicated expansion: flagged, with the
finding naming the specific unexplained additions the diff's own evidence
supports — never a blanket "the lockfile changed" claim.

### Worked example — a manifest change with no implicated concern

A `package.json` change that only reorders existing dependency entries,
or bumps a dependency by a patch version with an unchanged lockfile
transitive set, implicates none of the five concern areas: this pass
performs no deepening and raises no finding, exactly as "Semantic
change-implication reasoning"'s "no signal, no output" rule already
applies to every other dimension.

## 4. Fail-closed on an unrecognized format

When a manifest, lockfile, or build-file format cannot be parsed or
understood well enough to reason about any concern area in §3 — an
unfamiliar or repository-specific packaging format, a generated file this
pass cannot interpret — this pass raises no speculative finding for it.
This mirrors, and does not replace, the same fail-closed discipline
"API / contract compatibility review" and "Architectural placement and
execution-lifecycle fidelity" already apply to insufficient evidence: an
unrecognized format is a valid terminal outcome, not a license to guess.

## 5. Tie to the existing severity and evidence model

No new severity, finding category, or score is introduced. A
dependency/supply-chain finding is labeled confirmed defect / credible
engineering risk exactly like any other finding
([`evidence.md`](../../shared/policies/evidence.md)) and classified per
[`severity.md`](../../shared/policies/severity.md) on its own evidenced
impact — unlike the API/contract compatibility model's breaking-shape
findings, no single concern area here is pinned to a typical severity
tier, since the same concern area (for example, dependency expansion) can
range from a P2 maintainability concern to a P1 build-breaking risk
depending on what the diff's own evidence shows. Per
[`evidence.md`](../../shared/policies/evidence.md), "Findings beyond the
changed lines," the search for affected call sites or usages scales with
the change's actual blast radius, never a repository-wide dependency
audit.

## 6. Smallest useful first implementation

1. **This model** — the recognized inputs (§2), the five concern areas
   with worked examples (§3), and the fail-closed rule (§4) — consumed as
   reviewer discipline.
2. **One packaged section** —
   [`shared/policies/review-scope.md`](../../shared/policies/review-scope.md),
   "Dependency / supply-chain deepening review," so the capability is real
   in both Skills' review behavior, not only designed. It is wired as the
   depth owner of the "Infrastructure / deployment" dimension in "Semantic
   change-implication reasoning," composing under
   [`specialist-depth.md`](../../shared/policies/specialist-depth.md)
   (#82) exactly like every other domain-specific deepening capability.
3. **The follow-up fixture corpus** — tracked separately as
   [#188](https://github.com/amirbena/code-review-skill/issues/188);
   quality hardening after this capability exists, not a prerequisite for
   it, per #181's acceptance criteria.

**Deferred** (named here so scope stays fixed):

- a dedicated vulnerability/SCA scanner or CVE feed — this capability is
  semantic reasoning layered on the existing evidence model, never a
  second, competing tool (see [`README.md`](README.md), "Non-goals");
- resolving or installing dependencies to verify compatibility directly;
- enforcing a specific dependency policy (e.g., a mandated upgrade
  cadence, a banned-license list) this repository has not itself defined;
- any per-finding numeric or probabilistic risk score.

**Rejected alternatives:**

- **A dedicated `context-dependent` decision token**, mirroring the
  API/contract compatibility model's rejected alternative, so an
  ambiguous case (for example, a major bump with no changelog evidence
  either way) could be pinned directly as a decision. Rejected for the
  same reason: it would require a fixture-format change independent of
  this capability, duplicating what the existing evidence-labeling model
  (confirmed defect / credible risk / optional-improvement) and the
  fail-closed §4 rule already express — an unresolved case simply raises
  no finding, or at most an optional ambiguity note, exactly as "API /
  contract compatibility review" already does for its own unresolvable
  cases.
- **A standalone dependency-diff script or tool** (invoked as a build/CI
  step to mechanically flag major bumps or lockfile expansion) instead of
  reviewer prose. Rejected as the first implementation: it would require
  a parser per ecosystem manifest/lockfile format, duplicating existing
  SCA/dependency-scanning tooling this capability explicitly does not
  compete with (see [`README.md`](README.md), "Non-goals"), and would not
  generalize to the provenance/trust and build/runtime-incompatibility
  concern areas, which need the same semantic reasoning over the diff's
  actual code and CI context that reviewer prose already applies
  elsewhere in this policy.
- **Treating every manifest/lockfile/build-file change as review-depth
  `elevated`** (the simplest possible rule, reusing
  [`change-risk-signals.md`](../../shared/policies/change-risk-signals.md)'s
  existing infra/config signal instead of a dedicated deepening pass).
  Rejected: review-depth classification and domain-specific deepening are
  deliberately separate concerns — a file-type-triggered depth signal
  would activate on every routine patch bump, exactly the generic
  dependency-update-linter behavior #181 rules out; a materially
  implicated concern area is a semantic finding, not a depth-level signal.

## 7. Relationship to existing canonical policies

- [`review-scope.md`](../../shared/policies/review-scope.md), "Semantic
  change-implication reasoning," owns the "Infrastructure / deployment"
  dimension this capability is the depth owner of; it does not redefine
  the dimension or its activation signal.
- [`specialist-depth.md`](../../shared/policies/specialist-depth.md) (#82)
  owns the evidence-driven activation and composition contract this
  capability engages under; this document does not define a parallel
  opt-in or activation mechanism.
- [`repository-expansion.md`](../../shared/policies/repository-expansion.md)
  (#87) owns the bounded-expansion and stop-condition contract reused for
  any cascading deepening (for example, a dependency-expansion finding
  that surfaces a further performance concern); this document does not
  define a second expansion model.
- [`remediation-scope-boundary.md`](../../shared/policies/remediation-scope-boundary.md)
  (#258) owns whether remediation is required at all and how much belongs
  in the current change versus follow-up work; deeper dependency/
  supply-chain reasoning never expands that boundary by itself.
- [`evidence.md`](../../shared/policies/evidence.md) owns the code-evidence
  bar and the confirmed-defect / credible-risk labeling; §5 does not
  relax it.
- [`severity.md`](../../shared/policies/severity.md) owns severity and the
  mechanical decision derivation; §5 does not touch either.
