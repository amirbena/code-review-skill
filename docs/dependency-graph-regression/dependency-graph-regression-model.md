# Dependency-Graph Regression Model

Repository-development design record for
**[#723](https://github.com/amirbena/code-review-skill/issues/723)**. Not
packaged; explanatory. The normative text is
[`../../shared/policies/dependency-graph-regression.md`](../../shared/policies/dependency-graph-regression.md)
(unwired until #724). This document explains why the contract is shaped as
it is and carries the worked examples; it does not restate the contract's
tables. Acquisition, threat model, and the Epic-scope decision are in
[`resolution-acquisition.md`](resolution-acquisition.md); the root-cause
investigation is in [`root-cause-replay.md`](root-cause-replay.md).

## 1. Problem and goal

A PR bumped a Maven BOM. The one-line manifest diff did not show that the
resolved tree now carried a second family of the same libraries. A human
reviewer caught it; the review did not
([`root-cause-replay.md`](root-cause-replay.md) explains why). The goal is a
contract under which a review can obtain Base and Head graph evidence,
compute what changed, and say what that means — while never claiming more
than the evidence supports.

## 2. Two stages and why they are separate

| Stage | Input | Output | Properties |
| --- | --- | --- | --- |
| 1. Graph-delta detection | Two normalized graphs and their evidence states | Delta records | Deterministic, no compatibility judgment, testable without a model |
| 2. Compatibility analysis | Delta records and allowed knowledge sources | Observations and conclusions | May use judgment; never adds a node, edge, or version absent from Stage 1 |

Separating them is what makes the reasoning auditable. A model that sees a
raw graph can invent a path; a model that only sees delta records cannot.
It also lets #725 measure each stage on its own: Stage 1 against exact
expected records, Stage 2 against conclusions with their cited evidence.

## 3. Worked example — the incident (synthetic equivalent)

The real repository is not available to this record, so the graphs below
are a **synthetic equivalent**. The Head path below was verified against
public POMs read as inert data (see
[`metadata-only-resolution.md`](metadata-only-resolution.md) §5); the Base
graph and the BOM's own managed versions are unknown and written as `‹…›`
rather than invented.

**Declaration change** (`pom.xml`): the imported BOM `jsk-bom` goes from
`2.16.29` to `2.16.39`.

| Node (Maven) | Base | Head | Edge path in Head |
| --- | --- | --- | --- |
| `org.bouncycastle:bc-fips` | 1.0.2.4 | 1.0.2.4 | direct |
| `org.bouncycastle:bcpkix-fips` | 1.0.7 | 1.0.7 | direct |
| `org.springframework.cloud:spring-cloud-starter-bootstrap` | ‹Base› | 3.1.8 | managed by `jsk-bom` |
| `org.springframework.cloud:spring-cloud-starter` | ‹Base› | 3.1.8 | via `spring-cloud-starter-bootstrap` |
| `org.springframework.security:spring-security-rsa` | ‹Base› | 1.0.12.RELEASE | via `spring-cloud-starter` |
| `org.bouncycastle:bcpkix-jdk18on` | ‹Base: absent; `bcpkix-jdk15on` 1.64–1.69 is present for any Base starter-bootstrap 3.0.0–3.1.7› | 1.73 | via `spring-security-rsa` |
| `org.bouncycastle:bcprov-jdk18on` | ‹Base› | 1.73 | via `bcpkix-jdk18on` |
| `org.bouncycastle:bcutil-jdk18on` | ‹Base› | 1.73 | via `bcpkix-jdk18on` |

The Head BouncyCastle versions assume the BOM does not override them. Every published
`spring-cloud-starter-bootstrap` from 3.0.0 to 3.1.7 already pulls the older
non-FIPS `jdk15on` family ([`fidelity-study.md`](fidelity-study.md) §4), so
unless the real Base lacked the dependency or excluded it, the delta is a
rename and version change rather than a new family; the fixture must use the
real Base.

**Stage 1 output (deterministic, assuming the Base lacks these keys):** one
`version-changed` for `spring-cloud-starter-bootstrap`; `added` for
`spring-cloud-starter`, `spring-security-rsa`, `bcpkix-jdk18on`,
`bcprov-jdk18on`, `bcutil-jdk18on`. Each carries its
shortest relevant path from the `jsk-bom` line, for example
`pom.xml:<jsk-bom line> → spring-cloud-starter-bootstrap →
spring-cloud-starter → spring-security-rsa → bcpkix-jdk18on →
bcprov-jdk18on` (length 5). The
`bc-fips` nodes produce no record.

**Stage 2 — what is concluded depends on the knowledge source, not on the
model's recollection:**

| Knowledge available | Claim strength | Outcome |
| --- | --- | --- |
| None. | speculative | An observation only: both `bc-fips` and the non-FIPS family are selected. A bounded question to the engineer or a P2 credible risk if the evidence bar is met; never blocking. |
| A curated, versioned family entry stating the two BouncyCastle families must not coexist on one classpath. | documented | P1 on a runtime-reaching scope. |
| A repository-declared mandatory FIPS-only requirement and the non-FIPS provider on a runtime-reaching scope. | documented, compliance-sensitive | P0 only if the existing P0 bar is met by that evidence; otherwise P1. |

**Deduplication.** The `added` records share one root: the edge
`spring-cloud-starter → spring-security-rsa` introduced by the
BOM bump. They yield **one** finding at `pom.xml:<jsk-bom line>`, listing
the affected artifacts as evidence, never four.

**Finding, in the existing shape** (abridged): `location` = the `jsk-bom`
line (canonical fix/action location; the graph artifacts are the evidence
location); `evidence` = Base and Head path, the three non-FIPS artifacts,
the existing `bc-fips` pair, claim strength, evidence state; `impact` =
classpath and crypto-provider boundary; `fix` = an exclusion of the
non-FIPS family on the `spring-security-rsa` edge or a version alignment,
plus the command that confirms it; `confidence` = `credible`;
`defect_kind` = `incompatible-library-family`.

### 3.1 Incident regression target — status

The incident stays a required regression target. Its **exact Base/Head delta
is unavailable** until the private evidence is supplied, and nothing in this
record claims the BOM upgrade first introduced non-FIPS dependencies.

| Item | Status |
| --- | --- |
| Head dependency path to the `jdk18on` family | **Verified** from public POMs and real Maven ([`fidelity-study.md`](fidelity-study.md) §4). |
| Non-FIPS BouncyCastle in the Base | **Unknown.** Every `spring-cloud-starter-bootstrap` from 3.0.0 to 3.1.7 already pulls `bcpkix-jdk15on`; the Base is only known to differ if it lacked or excluded the dependency. |
| Base and Head `jsk-bom` (2.16.29 and 2.16.39) | **Unavailable.** Not published on a public index; managed versions and exclusions unknown. |
| The repository's own POMs and effective Base/Head trees | **Unavailable.** |
| Profile and property inputs of the real build | **Unavailable.** |
| FIPS/non-FIPS compatibility record | **Unwritten.** Needs the "Compatibility knowledge-source contract"; none is `verified`. |
| Stage 1 delta | **Cannot be stated.** Two cases are possible: new family added, or `jdk15on` keys removed and `jdk18on` keys added (a rename, recognized only by a `same-family` record in Stage 2). |

To make the target executable, a maintainer must supply: the Base and Head
`jsk-bom` POMs, the repository's root and parent POMs at both commits, the
resolved Base and Head trees from the real build, and the profile/property
inputs the real build uses (production-enablement gate G8). Until then any
fixture is explicitly synthetic and must say so.

## 4. Worked example — npm, from a lockfile with nothing pre-supplied

`package.json` bumps `ui-kit` from `^4.1.0` to `^5.0.0` (synthetic names).
Base and Head `package-lock.json` (`lockfileVersion` 3) are read from the
Git objects, so they are bound to the reviewed commits by blob digest.
`ui-kit@5.0.1` declares `peerDependencies: { "react": "^18" }`; the Head
lockfile selects `react@17.0.2`.

**Stage 1:** `version-changed` `npm::ui-kit::` 4.9.2 → 5.0.1; and
`newly-conflicting` for the edge `ui-kit` → `react` whose `requested`
(`^18`) is not satisfied by the `resolved` `17.0.2`. Path:
`package.json:<ui-kit line> → ui-kit → react (peer)`.

**Stage 2:** the unmet peer is **demonstrated** by the lockfile itself, so
no external knowledge is needed: P1 (`unmet-peer-dependency`) on the
runtime-reaching scope. This is the case the static path serves fully, and
it is why `static-lockfile` is the realistic no-caller-graph route.

## 5. Worked example — Gradle, partial coverage

`libs.versions.toml` raises a platform BOM. `gradle.lockfile` is read from
both commits; it locks `runtimeClasspath` but not `testRuntimeClasspath`.

**Stage 1** on the locked portion shows `jackson-databind` `newly-evicted`
in Head: a direct constraint requested 2.16.0, a platform constraint
selected 2.15.3. **Evidence state:** `partial` — the unlocked configuration
is unresolved and is named in the Context gap. **Stage 2:** a convergence
problem with no documented break caps at P2 (a lower version selected than
requested is a fact, not by itself a failure), and claim strength is capped
at `documented` because the evidence is partial. The unlocked test
classpath is explicitly not assessed.

## 6. Evidence-state worked examples

| State | Example | Result |
| --- | --- | --- |
| `available` | The npm example above: both lockfiles bound by blob digest, within caps. | Stage 1 and 2 run; finding eligible. |
| `missing` | The incident repo: Maven, no lockfile, nothing supplied, repository CI publishes no SBOM. | Diff-text deepening only. Gap: "Dependency-graph evidence for Base and Head was not available (Maven has no lockfile and no graph was supplied); the resolved impact of the BOM bump was not assessed. To obtain it, run `mvn dependency:tree -DoutputType=json -DoutputFile=tree.json` at each commit yourself and supply the output." No finding. |
| `partial` | The Gradle example. | Findings only on the locked portion, capped at `documented`; gap names the unlocked configuration. |
| `stale` | A caller supplies a `dependency:tree` whose recorded `pom.xml` digest differs from the reviewed Head blob. | Not used. Gap: "The supplied graph for Head was resolved from different inputs than the reviewed commit; it was not used." |
| `untrusted` | A Head SBOM comes from the PR's own workflow run, which executed PR-controlled build code. | Not used. Gap states the reason. A forged "clean" or "alarming" SBOM therefore cannot move a decision. |
| `mismatched` | Base resolved under JDK 11 with profile `legacy`, Head under JDK 17 with none. | Per-side observations only; no delta, because a delta would show phantom additions and removals. |

## 7. Claim strength and why memory is not a source

A resolved graph shows that two things are *present*, not that they
*conflict*. The distinction is the Epic's central risk: a review that says
"these two families break each other" from recollection will sometimes be
right and sometimes confidently wrong, and a graph makes the claim look
verified. The contract therefore requires every conclusion above
`speculative` to cite either the graph alone (demonstrated: an unmet peer, a
duplicate selection) or an allowed knowledge source. Curated family data
does not exist yet; creating it is a reviewable-data deliverable for #724,
not something this record invents.

## 8. Severity calibration rationale

The table in the policy maps claim strength and scope to P0/P1/P2 without
touching [`severity.md`](../../shared/policies/severity.md):

- P0 stays rare and evidence-bound: only a demonstrated or repository-declared
  *mandatory* compliance violation, or a production-breaking conflict the
  evidence shows. A graph alone never reaches it.
- Test/dev/optional scope caps at P2: it cannot break the shipped artifact.
- Convergence alone caps at P2 (see §5).
- Missing, stale, untrusted, or mismatched evidence never escalates and
  never produces a finding.
- **No literal P3 exists.** A lower-impact signal is a P2 or the existing
  severity-less observation precedent in `code-hygiene.md`. Introducing P3
  is a maintainer decision this record does not make.

## 9. Interaction decisions

| Mechanism | Decision | Why / rejected alternative |
| --- | --- | --- |
| Existing diff-text deepening | **New lens, separate file.** It keeps running unchanged in every state and is never presented as graph analysis. #724 adds only a pointer to `review-scope.md`. | Extending the section would grow `review-scope.md` (~660 lines, over the AGENTS.md size trigger) and would blur observation of diff text with analysis of a resolved graph. Extracting the existing section is a separate refactor owned by the large-file decomposition work, not folded in here to keep this change behavior-neutral. |
| `repository-expansion.md` | **Not an expansion class.** "Relevant dependency" stays out of that policy's relationship classes; graph facts never count as `resolved_relevant`. | Expansion follows repository-local relationships by ring; a resolved graph is acquired evidence with its own state vocabulary. Merging them would give graph claims a ring/coverage meaning they do not have. |
| External contract and workspace sibling context | **No linkage.** A dependency declaration or SBOM never nominates a repository to read; `externalReferences`, `purl` VCS qualifiers, and `resolved` URLs are ignored. | Identity comes only from the caller's grant (#133, #645, #662). |
| Reasoning check, Context gaps, `confidence`, `capability`, `defect_kind` | Context gaps carry the state wording. `confidence` is a finding field (`credible`, or `insufficient-context` for a missing material piece); a graph never raises it. `capability` and `defect_kind` are annotations only. A gap is never a Reasoning-check question. | Reuses the existing single epistemic field; adds no value. |
| Placement | Finding on the changed manifest line (fix/action location). The graph artifact is the evidence location, possibly a non-diff path, and is never promoted to the fix location. | Follows the finding template's "no silent promotion". |

## 10. Hand-off to #724 and #725

The contract is owned once, by the unwired policy; the issues point to its
sections and do not restate them. Nothing below changes the contract.

**#724 (implementation).** Implements the policy's sections, by name, and
adds nothing that weakens them: "Normalized graph model", "Base/Head delta
semantics", "Evidence acquisition", "Accepted evidence formats and safe
handling", "Completeness versus fidelity", "Fail-closed resolution inputs",
"Compatibility knowledge-source contract", and the finding contract. It also
wires both adapters, capability metadata and packaging, and the Context-gap
kind (an additive template change stated as such). It may deliver the
`static-lockfile`, `caller-supplied`, and `repository-ci-artifact` paths. It
must **not** enable `metadata-resolution`: that path stays disabled until
every gate in "Production-enablement gates" passes and a maintainer records
it. Network and credential access remain unauthorized.

**#725 (benchmark and gate).** Measures the policy's stages and gates:

- Stage 1 against exact expected records; Stage 2 against conclusions and
  their cited, `verified` knowledge records; end to end from a normal review
  target.
- The fidelity gates G1 and G2: the real-world differential corpus and the
  pre-registered thresholds, which a maintainer fixes and commits by SHA
  before the counted run.
- The security and regression gate G6, including the fail-closed table and
  the network and credential negative controls.
- The incident fixture, which stays marked synthetic and `unavailable` until
  G8's private evidence is supplied. A pass that needs pre-supplied graphs,
  or that exercises only `caller-supplied`, does not satisfy an end-to-end
  criterion for Maven.

**Proposed issue-body amendments (not applied; for a maintainer to apply or
reject):** in #724, reference the policy sections above and add "must not
enable `metadata-resolution`"; in #725, add layers for fidelity (G1, G2) and
security (G6) and mark the incident fixture dependent on G8.

## 11. Acceptance-criteria map

| Criterion | Where |
| --- | --- |
| Root cause recorded and classified | [`root-cause-replay.md`](root-cause-replay.md) |
| Design record and unwired policy, schema, delta, worked examples | This document §3–§5; the policy |
| Acquisition decision, rejected alternatives, threat-model entries | [`resolution-acquisition.md`](resolution-acquisition.md) |
| Severity table consistent with `severity.md`/`evidence.md` | Policy "Severity calibration"; §8 |
| Interaction decisions; fail-closed | §9; policy "Budgets and failure behavior" |
| Safe acquisition rules per format | Policy "Accepted evidence formats"; [`resolution-acquisition.md`](resolution-acquisition.md) §4 |
| End-to-end workflow, with a path needing no pre-supplied graph | [`resolution-acquisition.md`](resolution-acquisition.md) §3 |
| Evidence-state table with examples | Policy "Evidence states"; §6 |
| Two stages with an interface | §2; policy "Two stages" |
| Boundary policies unchanged; threat entries | [`resolution-acquisition.md`](resolution-acquisition.md) §5–§6 |
