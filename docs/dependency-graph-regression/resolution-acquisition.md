# Resolution Acquisition, Threat Model, and Epic-Scope Decision

Repository-development design record for
**[#723](https://github.com/amirbena/code-review-skill/issues/723)**. Not
packaged; explanatory. The normative acquisition rules are in
[`../../shared/policies/dependency-graph-regression.md`](../../shared/policies/dependency-graph-regression.md),
"Evidence acquisition" and "Accepted evidence formats and safe handling".
This document records *why* those paths were admitted or refused, the
end-to-end workflow, and the one decision that needs a maintainer.

## 1. Decision summary

| Path | Decision |
| --- | --- |
| 1. `caller-supplied` Base/Head graph artifacts | **Admitted**, as one input — not the only one. |
| 2. `static-lockfile` parsing | **Admitted.** The path that needs nothing pre-supplied. |
| 3. Offline resolution from a local cache in the sandbox | **Not admitted.** Needs a maintainer-approved amendment to `runtime-validation.md` (candidate A-1, §7). |
| 4. Resolution under `trusted-host-execution.md` | **Rejected.** |
| 5. `repository-ci-artifact` for the exact Base/Head commits | **Admitted**, with a trust rule; `github-pr-review` repository-backed only. |
| 6. `metadata-resolution` (reviewer-owned, offline resolver over POM metadata) | **Approved in principle; not enabled.** Class B. Researched in [`metadata-only-resolution.md`](metadata-only-resolution.md) and measured in [`fidelity-study.md`](fidelity-study.md). It cannot run until every production-enablement gate passes. Network (D2) and credentials (D3) are not authorized. |

No path grants execution or network access. `runtime-validation.md`,
`repository-checkout.md`, and `trusted-host-execution.md` are **unchanged**
by this record; no amendment to any of them is made or approved here.

## 2. Options, threats, and why

**Why resolution is dangerous.** Resolving a Maven or Gradle graph is not
reading a file; it runs build tooling over attacker-controllable input.

| Surface | What an attacker (the PR author) controls | Consequence if the reviewer resolves |
| --- | --- | --- |
| Maven plugins and build extensions | `pom.xml` `<build>` plugins, `.mvn/extensions.xml` | Code runs at resolution time with the resolver's privileges. |
| `.mvn/` config, wrapper (`mvnw`, `gradlew`) | `.mvn/maven.config`, `jvm.config`, wrapper scripts and distribution URL | Arbitrary flags, JVM options, or a downloaded tool run. |
| Gradle init/build scripts, settings plugins | `build.gradle(.kts)`, `settings.gradle`, `buildSrc` | Scripts are code and execute during configuration. |
| npm lifecycle hooks | `preinstall`/`postinstall`/`prepare` | Run on install; resolution-only modes still read hostile metadata. |
| Repository scripts and hooks | Anything the build invokes | Same. |
| `settings.xml`, `.npmrc`, `.yarnrc.yml`, `gradle.properties` | Mirrors, registries, and tokens | Credentials exposed to the build, or traffic redirected to an attacker mirror. |
| Dependency downloads | Which coordinates, from where | Fetching and (for some ecosystems) unpacking attacker-chosen artifacts. |
| Local cache | A poisoned or pre-seeded cache entry | A resolved graph the reviewer trusts that the attacker shaped. |

**Path 1 — caller-supplied graphs.** Nothing executes in the reviewer. The
threat moves to the artifact: it can be forged, stale, oversized, or carry
instruction-like text. All of that is handled by data-only parsing, caps,
and Base/Head binding (policy "Accepted evidence formats and safe
handling"). Alone it is not realistic: it requires the caller to resolve
two graphs first. Admitted as one supported input.

**Path 2 — static lockfile parsing.** Reads `package-lock.json`,
`pnpm-lock.yaml`, `yarn.lock`, `gradle.lockfile` from Git objects. No
execution, no network, and the Git blob digest binds each lockfile to its
commit. Coverage is bounded by what the lockfile holds: npm/pnpm/Yarn
lockfiles are complete for installed dependencies; `gradle.lockfile` covers
only locked configurations. Maven has no lockfile, so this path does not
exist for Maven. Admitted.

**Path 3 — offline resolution by running Maven from a pre-populated cache.** Inside the
runtime-validation sandbox (filesystem-isolated, no credentials, no
network) this is the only resolution route that could be contained.
Rejected *for this contract* because: the sandbox contract admits only
exact declared repository commands and forbids dependency installation;
Maven plugins and `.mvn/extensions.xml` still execute inside the sandbox
(contained, but the resolution still runs hostile code to produce evidence
the hostile code can shape); and populating the cache needs a network
fetch of attacker-chosen coordinates, which is the cache-poisoning surface.
This is a candidate for a future maintainer-approved amendment (§7), not
something the graph policy can grant.

**Path 4 — trusted-host execution.** Rejected. That backend has no
filesystem, credential, or network isolation by its own contract, so
resolving a PR's build on the reviewer's host is arbitrary code execution on
that host. It is also scoped to the same admitted declared command, which a
reviewer-chosen resolution command is not.

**Path 5 — repository-CI artifacts for the exact commits.** The
repository's own CI may already produce a `dependency:tree`, SBOM, or
dependency-submission snapshot. Retrieval is read-only and nothing runs in
the reviewer. The risk is provenance: a workflow that ran PR-controlled
code can emit a forged graph. Rule: a Head artifact from the PR's own
workflow is `untrusted` by default; a Base artifact built from the merged
Base commit by the default branch's own workflow may be trusted; any
artifact must still bind to the reviewed commit by SHA and manifest digests.
A platform-produced comparison endpoint (for example a hosting platform's
dependency-review comparison between two commits) is the same class: its
trust and its transitive coverage must be verified by #724 against live
behavior before it is relied on — this record does not assert them.

## 3. End-to-end review workflow

Starting from the normal review target, with nothing pre-supplied:

```text
review target (local change or PR)
    -> activation: does a changed declaration alter the resolved set?
    -> for Base, then Head, try admitted paths in order:
           static-lockfile  ->  repository-ci-artifact  ->  caller-supplied
    -> parse as data under caps, confine paths, exclude credentials
    -> bind to Base/Head (commit SHA / digests); recompute and compare
    -> assign an evidence state per side
    -> Stage 1 (deterministic delta) -> Stage 2 (compatibility analysis)
    -> findings and Context gaps; diff-text deepening ran regardless
```

Per adapter and path:

| Adapter / path | Who produces | When | From which commit | Tool | What executes | Binding |
| --- | --- | --- | --- | --- | --- | --- |
| local / `static-lockfile` | The repository (committed lockfile) | Before the review | Base: Git object at the base ref. Head: the working tree or HEAD. | Reviewer's own read-only parser | Nothing | Base: blob SHA at the base ref. Head: SHA-256 of the file as read, recorded at review time. |
| local / `caller-supplied` | The caller | Before the review, from the commit(s) the caller resolved | Caller states it | Caller's own resolver (`mvn dependency:tree`, `gradle dependencies`, an SBOM tool) | Runs on the **caller's** machine, outside the review | Caller's digests recomputed against Base/Head. |
| local / `repository-ci-artifact` | — | — | — | — | — | **Not admitted** until the local adapter has an existing read-only remote retrieval capability. An uncommitted Head has no CI artifact in any case. |
| github repo-backed / `static-lockfile` | The repository | At PR time | Base and Head SHAs, both fetched as objects | Reviewer's own read-only parser over checkout objects | Nothing | Blob SHAs at the reviewed SHAs. |
| github repo-backed / `repository-ci-artifact` | Repository CI | After push, before or during review | Exact Base and Head SHAs | CI's tool (for example a dependency-tree or SBOM generator); retrieval through the existing read integration | CI runs the build on **CI**, never in the reviewer | Workflow-run `head_sha` plus recomputed manifest digests; trust rule above. |
| github repo-backed / `caller-supplied` | The caller | Before the review | Caller states it | Caller's resolver | Caller's machine | As local. |
| github API-only | — | — | — | — | — | **Expected unavailable; behavior unchanged.** |

Where the path ends with no graph, the evidence state is `missing` and the
Context gap names a command the **user** runs on their own trusted machine.
The reviewer never runs it.

**Which ordinary change gets which path.**

| Ecosystem | No-pre-supplied path | Result without any graph |
| --- | --- | --- |
| npm, pnpm, Yarn | `static-lockfile` (complete). | `available` for the reviewed commits. |
| Gradle with dependency locking | `static-lockfile` (locked configurations). | `partial`. |
| Gradle without locking | `repository-ci-artifact` if published. | `missing`. |
| **Maven** | `repository-ci-artifact` **only if** the repository's CI publishes a graph or SBOM. | **`missing`.** |

## 4. Safe handling per format

The general rules (data only, caps, confinement, credential exclusion,
binding, identity) are in the policy and apply to every row. Format-specific
hazards the parser must close:

| Format | Hazard | Control |
| --- | --- | --- |
| CycloneDX / SPDX JSON | Instruction-like text in `description`, `name`, `properties`, `licenses`; `externalReferences`, `purl` VCS qualifiers, `bom-ref` URLs; deeply nested or huge arrays | Free text stored but never rendered as instruction; URLs and references never dereferenced; depth, array, and size caps; schema validated per declared `specVersion`. |
| Maven `dependency:tree` | Text with injected lines; scope/optional spoofing | Fixed line grammar; any non-conforming line makes the artifact `untrusted` rather than skipped. |
| Gradle report / `gradle.lockfile` | Same; locked-config coverage claims | Fixed grammar; configurations not present are `partial`, never inferred. |
| `package-lock.json` | `resolved` URLs, `integrity`, `hasInstallScript`, `bin` | URLs recorded as host only and never fetched; the install-script flag is recorded as a fact and never run; version 1 unsupported. |
| `pnpm-lock.yaml`, Berry `yarn.lock` | YAML aliases and custom tags (expansion, object construction) | Safe loader only, no tags, aliases capped. |
| Classic `yarn.lock` | Hand-written grammar edge cases | Fixed grammar; unknown constructs make the artifact unsupported. |

## 5. Threat-model coverage

The catalog entries added for this record, each with an enforcement owner
(#724, the implementation that must enforce it) and an expected safe
outcome, are in
[`../threat-model/catalog/`](../threat-model/catalog/README.md):

| Scenario | Covers |
| --- | --- |
| INJECT-021 | Instruction-like text inside a graph, SBOM, or lockfile free-text field. |
| INJECT-022 | A graph, SBOM, or lockfile reference steering a fetch, checkout, or repository identity. |
| INJECT-023 | Credential or registry configuration read into evidence, logs, or published output. |
| INJECT-024 | Acquisition that would execute PR-controlled build code (plugins, extensions, `.mvn/`, scripts, lifecycle hooks). |
| INJECT-025 | Acquisition failure falling back to a less restrictive execution or network mode. |
| INJECT-026 | Dependency downloads, mirror redirection, and cache poisoning shaping the graph. |
| SCOPE-007 | A forged, stale, or mismatched artifact accepted as Base/Head finding evidence, or partial evidence escalated. |
| DOS-009 | Oversized, deeply nested, cyclic, or malformed input. |
| INJECT-027 | (candidate metadata resolver) Project-declared repositories or interpolated URLs steering requests. |
| INJECT-028 | (candidate metadata resolver) Credential forwarding or project-supplied credentials. |
| INJECT-029 | (candidate metadata resolver) Extensions or non-XML POMs loading code or altering the model. |
| DOS-010 | (candidate metadata resolver) Pathological POM graphs. |
| GIT-010 | Path traversal or symlink escape when reading artifacts and lockfiles. |

## 6. Boundary policies unchanged

- `runtime-validation.md`: still sandbox-required, network denied, no
  dependency installation, fail-closed. Not amended.
- `skills/github-pr-review/policies/repository-checkout.md`: still no builds
  or package installs. Not amended.
- `trusted-host-execution.md`: unchanged; not an acquisition route.
- The dependency-graph policy grants nothing. Any execution or network
  admission is a separate maintainer-approved amendment recorded here.

**Approved amendments: none.**

## 7. Maven scope: maintainer direction and open decisions

**Maintainer direction (recorded):** Maven remains a required target of the
Epic, because the original false negative was a Maven BOM upgrade. Maven
scope is **not** reduced and Epic #722 is **not** revised.

**Earlier finding, now qualified.** With only paths 1–5, Maven has no safe
acquisition path that needs no caller-supplied graph, except
`repository-ci-artifact` when CI already publishes one. That finding stands
for those five paths.

**New finding.** A sixth architecture, metadata-only resolution, is
researched in [`metadata-only-resolution.md`](metadata-only-resolution.md).
It is **class B**: viable, evidenced by reconstructing the incident's
dependency path from public POMs read as inert data, but available only if a
maintainer approves new boundaries (D1–D6 there). The smallest set (offline
resolution over a caller-granted local Maven repository, variant M-1) needs
no network and no credentials. The earlier "proposed reduction of the Epic"
is **withdrawn**.

**Maintainer decisions (recorded):** D1 approved in principle, not enabled;
D2 network not authorized; D3 credentials not authorized; D4 engine pinning
required; D5 a dedicated read-only cache approved in principle; D6 unsupported
inputs fail closed. See [`fidelity-study.md`](fidelity-study.md). Enablement
is blocked on the contract's production-enablement gates; this record asserts
no resolution.

**Candidate amendment A-1** (offline resolution of Maven inside the
runtime-validation sandbox, by running Maven) remains **not approved** and
is now subordinate: it is class 1 in the three-way distinction (running
Maven against an untrusted project), whereas metadata-only resolution is
class 3. Prefer variant M-1/M-2 over A-1 if any is approved.

## 8. Verification owed by #724

Facts this record deliberately does not assert, because it did not verify
them: how a hosting platform's dependency-comparison endpoint treats Maven
BOM imports and transitive resolution; which CI systems expose graph or SBOM
artifacts for an exact commit through the existing read integration; and
the exact `dependency:tree` JSON/text shapes per plugin version. #724 must
verify each against live behavior before wiring.
