# Metadata-Only Maven Resolution — Research

Repository-development design record for
**[#723](https://github.com/amirbena/code-review-skill/issues/723)**,
follow-up research directed by the maintainer: before concluding that Maven
has no safe end-to-end acquisition path, investigate whether a Maven graph
can be reconstructed from POM **metadata** without executing
repository-controlled code. Not packaged; explanatory. Nothing here
implements a resolver, relaxes a policy, or runs untrusted build code. The
normative text stays in the unwired
[`../../shared/policies/dependency-graph-regression.md`](../../shared/policies/dependency-graph-regression.md).

## 1. Verdict

| Class | Meaning | Result |
| --- | --- | --- |
| A | Feasible under the existing boundaries | **Only a degenerate form** (parse in-repo POMs as data). It cannot reach an external BOM or parent, so it cannot see the incident. |
| **B** | **Feasible only with explicitly approved new boundaries** | **The useful forms.** Recommended classification. |
| C | Infeasible, with concrete evidence | **Not supported by the evidence.** The incident's chain was reconstructed from public POMs read as inert data (§5). |

**Status: the maintainer approved the offline variant in principle (not enabled; D2 and D3 not authorized) — see [`fidelity-study.md`](fidelity-study.md).** Variant M-2 (online) is **not authorized**.

**Recommendation: do not reduce Maven scope.** Maven metadata resolution is a
viable architecture that needs maintainer-approved new boundaries (§7). It
is not available today, and nothing in this record grants it.

## 2. Three things that must not be conflated

| | What it is | Executes repository-controlled code? | Admitted today? |
| --- | --- | --- | --- |
| 1. **Running Maven against an untrusted project** | `mvn dependency:tree` and equivalents. Loads `<build>` plugins, `.mvn/extensions.xml`, `.mvn/maven.config`/`jvm.config`, the wrapper, and Maven's own lifecycle. | **Yes.** | No (path 4 rejected; path 3 not admitted). |
| 2. **Parsing Maven metadata as inert data** | Reading POM XML (and parents/BOMs) as a document and extracting declarations. | **No.** | Yes for files in the review target; but parsing alone cannot reach POMs that live in a repository (the BOM, the parent, every transitive POM). |
| 3. **Resolving through an isolated resolver** | A reviewer-owned, pinned Maven model builder plus Maven Resolver run as a library: it builds effective models, collects the graph from POMs, applies Maven's own mediation. It downloads **POM files only**, never JARs, and loads no plugins. | **No repository-controlled code** — but it *is* a reviewer-owned executable and it needs POMs from somewhere. | **No.** It is a new boundary class. |

Option 3 is the architecture under evaluation. Its safety rests on
resolver-as-library never loading what the project declares: not plugins,
not build extensions, not project-declared repositories, not `settings.xml`.

## 3. Evaluation

### 3.1 What a resolver reproduces

Maven Resolver documents the model: collection builds a "dirty graph" by
reading only parts of each effective POM — `dependencies`,
`dependencyManagement`, and `repositories` — and downloads **POM files, not
JARs**. A separate in-memory step then resolves conflicts, duplicates, and
cycles. Artifact download is a later, separate step that this architecture
never performs. (Maven Resolver, "How Resolver Works"; the Maven 4
`DependencyCollector` documentation says the same.) `dependency:tree`
reports this collected-and-mediated graph, so using the same engine with
Maven's own session defaults is the highest-fidelity route to the same tree.
Parent POMs, imported BOMs (`<scope>import</scope>` + `<type>pom</type>`),
`dependencyManagement`, exclusions, scope derivation, and nearest-wins
mediation are all engine behavior, not plugin behavior.

### 3.2 Criteria

| Criterion | Finding | Residual risk |
| --- | --- | --- |
| **Parent POMs, imported BOMs, profiles** | Handled by the model builder: parent inheritance, interpolation, profile activation, and BOM import before resolution. Profile activation depends on JDK, OS, properties, and file existence — an environment the reviewer must **pin and record**, not inherit. Which `-P` profiles and `-D` properties the team's real build uses live in CI and `.mvn/maven.config`, which a reviewer cannot assume. | Profile selection is the largest fidelity gap. It is recorded in provenance; when the repository's real activation cannot be established the graph is `partial` or `mismatched`, never `available`. |
| **Exact Base/Head reconstruction** | Possible when both sides resolve from the same pinned engine, environment, and repository snapshot. Release versions are immutable, so a recorded **closure digest** (SHA-256 of every POM consumed) makes a side reproducible. Version ranges, `LATEST`, `RELEASE`, and `SNAPSHOT` depend on mutable `maven-metadata.xml`. | Mutable inputs make a side non-reproducible: record them and downgrade to `partial` unless pinned to a captured metadata snapshot. |
| **Metadata provenance and repository trust** | Every POM is recorded with its repository host, checksum, and digest. Trust is a property of the **reviewer-chosen** repository (for example Maven Central, or an organization's mirror), never of the project. Release artifacts in a public repository are immutable, so a closure digest is meaningful. | A repository serving a modified POM is a supply-chain compromise of the repository itself, out of scope here; recorded checksums make it at least detectable after the fact. POM signature verification is not assumed. |
| **Network and artifact retrieval** | Online collection needs HTTP reads of POMs and `maven-metadata.xml` from reviewer-allowlisted repositories. Offline collection needs no network but depends on a pre-populated local repository. Project-declared `<repositories>` must be **ignored**: they are attacker-controlled endpoints, and a URL can embed interpolated values (an exfiltration channel). | Offline coverage is limited to what is cached; Head versions the author never built may be absent. Online needs a new egress boundary. |
| **Credential isolation** | The resolver must run with a reviewer-owned minimal configuration: no `settings.xml`, no `~/.m2/settings.xml`, no inherited environment, no project `.mvn/` content. A private organization BOM (very likely for an internal BOM such as `jsk-bom`) needs a read-only credential for a **reviewer-allowlisted** host only, supplied by a trusted channel, never forwarded to any project-declared repository. | Credential custody for private repositories is a distinct maintainer decision (D3). |
| **Extensions, plugins, repository-controlled code** | The resolver-as-library loads no plugin and no build extension. But Maven *itself* would load `.mvn/extensions.xml` and `<build><extensions>`, and extensions can alter the model (version-rewriting, polyglot POM formats, lifecycle participants). A library harness cannot reproduce that behavior. | **Detect and fail closed:** the presence of `.mvn/extensions.xml`, `<build><extensions>`, a non-XML POM, or a model-altering extension makes the side `partial` or `missing` with a Context gap — never a silently incorrect graph. |
| **Fidelity versus real Maven** | The tree can differ by Maven and Resolver version (the Resolver documentation notes dependency-management scoping differs between 1.x and 2.x, and conflict-resolution strategies are pluggable). Maven 3 and Maven 4 differ. | Pin the engine, record its version, and mark `mismatched` when Base and Head used different engines. A differential fidelity test against real `mvn dependency:tree` on trusted projects is owed (§8) and is **not** done here. |
| **Execution limits and DoS** | Needs caps on POM count, bytes, parent/import depth, collected nodes, version-range fan-out, wall time, and process memory; import and parent cycles are detected by the model builder. | Caps are a policy decision (new DOS entry added). XML-parser hardening against entity expansion is a property of the pinned engine and must be verified, not assumed. |
| **Applicability: local and GitHub PR review** | See §6. | |
| **Original regression detectable?** | **Yes** for the dependency path, from public metadata alone (§5). Detecting that it *matters* is a separate knowledge-source question, independent of acquisition. | The BOM, if private, must be reachable; the Base graph must be known to attribute the change. |

### 3.3 Candidate variants

| Variant | How POMs are obtained | Class | Network | Credentials | Verdict |
| --- | --- | --- | --- | --- | --- |
| **M-0** Parse in-repo POMs only | Files already in the review target | **A** | None | None | Safe but insufficient: no external BOM, parent, or transitive POM. Useful only as the declaration layer (`declared_at`) and to detect what must be fetched. |
| **M-1** Offline over a caller-granted local Maven repository | A read-only repository root the caller grants (the `~/.m2/repository` pattern), plus in-repo POMs | **B** | None | None | Smallest new boundary. Strong for a local review of the author's own change (their build populated the cache); weak for someone else's PR. |
| **M-2** Online metadata-only collection | Allowlisted repositories (Central, an organization mirror) | **B** | New allowlisted egress | Private mirror needs custody | Most coverage; largest boundary. |
| **M-3** Organization- or CI-hosted resolution service | A read-only API the organization operates | **B** | Read integration | Held by the service | Same class as path 5 (`repository-ci-artifact`); trust rule applies. |
| **M-4** The agent "resolves by reading POMs" itself | Model reads POMs and reasons | — | — | — | **Rejected.** Non-deterministic, unmeasurable, and cannot satisfy Stage 1's deterministic contract. |

## 4. Comparison with the admitted approaches

| | `caller-supplied` | `static-lockfile` | `repository-ci-artifact` | **M-1 offline** | **M-2 online** |
| --- | --- | --- | --- | --- | --- |
| Works for Maven with nothing pre-supplied | No | **No lockfile** | Only if CI publishes | **Yes**, when cache holds the POMs | **Yes** |
| Executes anything in the reviewer | No | No | No | **Yes** (pinned, reviewer-owned) | **Yes** |
| Network | None | None | Read integration | None | **New egress** |
| Credentials | None | None | Integration's | None | **Custody needed** |
| Boundary change required | None | None | None | **Admit a pinned executable class + a root grant** | **Also: egress allowlist + credential custody** |
| Base/Head binding | Caller digests | Blob SHA | Run SHA + digests | **Closure digest + pinned engine** | Same |
| Fidelity to real Maven | Whatever the caller ran | n/a | Whatever CI ran | High if pinned; gaps in §3.2 | Same |
| Handles `.mvn/extensions.xml` | Yes (caller's Maven did) | n/a | Yes | **No — fails closed** | **No — fails closed** |
| Reproducible | Per artifact | Yes | Per artifact | Yes for immutable releases | Yes for immutable releases |

## 5. The original regression, reconstructed as inert data

The following was derived **only by reading public POM files as documents**
(Maven Central), with no Maven run, no plugin, and no resolver:

```text
spring-cloud-starter-bootstrap 3.1.8
  -> spring-cloud-starter 3.1.8
     -> spring-security-rsa 1.0.12.RELEASE   (excludes spring-core and spring-security-crypto only)
        -> bcpkix-jdk18on 1.73
           -> bcprov-jdk18on 1.73
           -> bcutil-jdk18on 1.73
```

So the incident's non-FIPS family is reachable by a pure metadata walk. The
exact edges in `jsk-bom` and the repository's own POMs were not available.

Two facts from the same POMs correct the earlier synthetic example and
matter for any fixture:

1. The real path has **one more hop** (`spring-cloud-starter`) than the
   Epic's shorthand. Stage 1's shortest-path output must show it.
2. `spring-security-rsa 1.0.11.RELEASE`, which `spring-cloud-starter 3.1.4`
   pulls in, depends on `bcpkix-jdk15on 1.69` — **already a non-FIPS
   BouncyCastle artifact under the older `jdk15on` name**. The follow-up
   [`fidelity-study.md`](fidelity-study.md) §4 resolved every published
   `spring-cloud-starter-bootstrap` version from 3.0.0 to 3.1.9 with real
   Maven: all of them pull non-FIPS BouncyCastle, so any Base at 3.0.0–3.1.7
   already had it. Whether the real
   Base graph already contained non-FIPS BouncyCastle depends on the Base
   BOM's managed `spring-cloud` version, which is unknown here. If it did,
   the Base→Head delta is `removed bcpkix-jdk15on` / `added bcpkix-jdk18on`
   (a rename, not a new family), and "introduced by this change" would be
   wrong; the existing-risk framing from the contextual-evidence model
   would apply instead. The fixture in #725 must be built from the real Base
   and Head BOM versions, and Stage 1 must not infer a `replaced` relation
   without relocation data.

This confirms detectability of the *dependency path* but not of the Base
state, and it shows why a faithful fixture cannot be invented.

## 6. Applicability

| Adapter | M-1 offline | M-2 online | M-3 service |
| --- | --- | --- | --- |
| `local-code-review` | **Natural fit.** A caller-granted local repository root follows the existing grant pattern. Works for the author reviewing their own change. | Needs the new egress boundary; the local adapter has no network authority today. | Needs a read integration the local adapter lacks. |
| `github-pr-review`, repository-backed | Only if the reviewing machine has a populated repository, which a PR author's does not. | Plausible, with egress and credential decisions. | Plausible. |
| `github-pr-review`, API-only | Unavailable; unchanged. | Unavailable; unchanged. | Unavailable; unchanged. |

## 7. Boundaries that would need explicit approval

None of these is granted here.

| ID | Decision | Notes |
| --- | --- | --- |
| D1 | Admit a **reviewer-owned, pinned, non-repository executable** class for resolution only. | Packaged Skills ship no executables today; the rendered-inspection environment policy is the precedent for a tool the user installs and the Skill only detects. |
| D2 | **Egress** allowlist for POM and metadata reads (Central and named mirrors); project-declared repositories ignored. | Needed for M-2 only. |
| D3 | **Credential custody** for private repositories: read-only, allowlisted-host-only, supplied by a trusted channel, never forwarded elsewhere. | Needed for private BOMs. |
| D4 | **Engine pinning policy**: which Maven/Resolver versions are supported and how `mismatched` is decided. | |
| D5 | **Root grant** for a local Maven repository (M-1), modeled on the workspace grant. | |
| D6 | Whether **fail-closed on extensions** is acceptable, or whether such repositories are simply out of the Maven reference. | |

M-1 needs D1, D4, D5, D6 and no network or credentials — the smallest
approval set. M-2 adds D2 and D3.

## 8. Recommended handoff

- **Do not revise Epic #722.** The earlier proposed Maven reduction in
  [`resolution-acquisition.md`](resolution-acquisition.md) §7 is withdrawn
  pending the maintainer's response to D1–D6.
- **Architecture:** extend the acquisition path set with
  `metadata-resolution` (variants M-1 and M-2) as a **candidate, not
  admitted** path. The policy lists it as such and stays unwired.
- **#724 split:** (a) wire the shared policy, the lockfile path, and the
  caller/CI paths; (b) the Maven metadata resolver path, **gated on D1–D6**.
- **#725:** the real-incident fixture is built from the real Base and Head
  BOM versions (§5, point 2), resolved once by the pinned engine in an isolated
  harness and checked in as data. Stage 1/Stage 2 layers can be measured
  before D1–D6 land; the Maven end-to-end layer needs a real acquisition
  path.
- **Done in the follow-up study** ([`fidelity-study.md`](fidelity-study.md)): a differential fidelity study against real Maven on synthetic projects and the incident chain; the dedicated-cache decision; verification of entity-expansion and cycle handling in the pinned engine's model builder. **Still owed:** a real-world corpus, a Linux sandbox, and the profile-input source of truth. The original list follows for reference:
- **Originally owed:** a differential fidelity study of
  the pinned engine against real `mvn dependency:tree` on a trusted corpus
  (graph equality rate, per category of divergence); verification of the
  engine's XML-parser hardening and import/parent cycle limits; and
  measurement of how often real repositories use extensions or non-default
  profile activation. Each is research, none requires untrusted code.

## 9. Sources and limits

- Maven Resolver, "How Resolver Works" (collection reads effective-model
  `dependencies`, `dependencyManagement`, `repositories`; downloads POMs
  only; conflict resolution is in-memory; Resolver 1.x vs 2.x
  dependency-management scoping differs; strategies are pluggable).
- Apache Maven 4 `DependencyCollector` API documentation (collection does
  not download artifacts; only POM files).
- Maven Model Builder documentation (two-phase effective-model build;
  plugin processing is an optional enrichment, not a statement that no
  plugin code ever runs).
- Public POMs on Maven Central read as documents: `spring-cloud-starter-bootstrap
  3.1.8`, `spring-cloud-starter 3.1.4` and `3.1.8`, `spring-security-rsa
  1.0.11.RELEASE` and `1.0.12.RELEASE`, `bcpkix-jdk18on 1.73`.
- **Not verified:** Coursier's BOM/profile fidelity (no authoritative source
  was found; an old reported gap was not confirmed or refuted), Maven 4
  differences beyond the cited notes, the model builder's XML hardening,
  and every behavior of a resolver this research did not run.
