# Metadata-Only Maven Resolution — Fidelity Study

Repository-development design record for
**[#723](https://github.com/amirbena/code-review-skill/issues/723)**.
Research only; not packaged. It follows
[`metadata-only-resolution.md`](metadata-only-resolution.md), which classified
the approach as class B, and answers the maintainer's direction to measure a
pinned, reviewer-owned metadata resolver against Maven's real behavior. **It
authorizes nothing.** The shared policy stays inactive and unwired, no
production resolver exists, and #724 has not started. The research harness
and every script are in [`fidelity-study/`](fidelity-study/README.md).

## Maintainer decisions recorded

| ID | Decision |
| --- | --- |
| D1 | Approved in principle; **not enabled**. |
| D2 | **Network access is not authorized.** |
| D3 | **Credential access is not authorized.** |
| D4 | Engine pinning is required. |
| D5 | A dedicated, read-only cache is approved in principle. |
| D6 | Unsupported resolution inputs fail closed. |

No production resolver execution is authorized. The normative contract for
all of the below is the unwired
[`shared/policies/dependency-graph-regression.md`](../../shared/policies/dependency-graph-regression.md):
"Completeness versus fidelity", "Fail-closed resolution inputs",
"Compatibility knowledge-source contract", and "Production-enablement
gates". This document records the evidence behind them and does not restate
them.

## 1. Summary

| Question | Answer |
| --- | --- |
| Does a library-only resolver match Maven's tree? | **Yes, on every category tested** where inputs and environment are pinned: 31 of the 33 comparable synthetic runs (the two exceptions are the input-driven cases in §3.1 and §3.3) and 19 of 19 real-incident runs were identical to `mvn dependency:tree`, including ordering. |
| Where does it differ? | Only where the input is not the same: unpinned profile activation (false negative), and mutable version metadata (partial). Both are detectable and are fail-closed rules below. |
| Where is Maven itself unsafe to mirror? | Offline Maven **silently treats a missing POM as a leaf** with only a warning. The resolver must surface that as `partial`. |
| Is the original regression detectable? | The Head path and the non-FIPS family: **yes**. The claim "non-FIPS was first introduced by the BOM upgrade": **not supportable** — see §4. |
| Is a dedicated cache preferable to `~/.m2`? | **Yes** (§6). |
| Ready for maintainer approval? | **Approved in principle by the maintainer** (D1, D4, D5, D6; D2 and D3 not authorized). **Not enabled:** gates G1–G8 are all open (§11). |

**Engine under test:** Maven 3.9.16 and Maven Resolver 1.9.27 (jars taken
unmodified from the Maven distribution), JDK 17.0.19 Temurin, macOS arm64.
Nothing else was tested (§8).

## 2. Method and safety envelope

- **Authoritative baseline:** real `mvn` 3.9.16 running
  `maven-dependency-plugin:3.8.1:tree`, in a trusted, scrubbed environment:
  `env -i`, an empty `HOME`, explicit empty user and global `settings.xml`,
  and an isolated local repository. Every baseline comparison ran **offline
  (`-o`) inside a macOS sandbox with `(deny network*)`**.
- **Candidate:** a ~120-line harness
  ([`MetaResolve.java`](fidelity-study/MetaResolve.java)) that is
  **research-only and not a production resolver**. It builds the effective
  model with Maven's own model builder (plugin processing off, minimal
  validation), then calls Maven Resolver's `collectDependencies` with
  Maven's own session defaults. It registers **no HTTP or Wagon transport**
  (only the file transport), uses an empty repository list, ignores every
  project-declared repository, reads no settings, and cannot start Maven.
- **Inputs:** synthetic, hermetic POMs for each required scenario (about 35
  projects), plus the real Spring Cloud chain from public POMs (§4). All
  synthetic artifacts are POM files only; collection needs nothing else.
- **Not done:** no repository-controlled plugin, extension, or build ran;
  the user's `~/.m2` was never read or written by any run (file count
  unchanged at 1,840, nothing newer); no credential was available to either
  tool; the baseline plugin download happened once, online, into the
  isolated cache, before any offline comparison.

## 3. Fidelity results

All rows are in
[`fidelity-study/results-summary.json`](fidelity-study/results-summary.json).
"Equal" means identical depth, coordinate, scope, optional flag, and order.

| Required scenario | Runs | Result | Notes |
| --- | --- | --- | --- |
| Parent POM inheritance | S1a (parent from cache), S1b (parent via `relativePath`) | **Equal** | Properties, inherited dependencies, and inherited `dependencyManagement` all match. |
| Imported BOMs | S2a (nested BOM), S2b (explicit version vs BOM) | **Equal** | BOM-managed versions, nested import, and explicit-version-wins all match. |
| `dependencyManagement` overrides | S3a (transitive version), S3b (transitive scope), S3c (direct version) | **Equal** | Root management reaches transitive nodes identically. |
| Transitive dependencies | S4 (depth-5 chain, shared subtree) | **Equal** | |
| Exclusions | S5a single, S5b `*:*`, S5c mid-graph | **Equal** | |
| Nearest-wins mediation | S6a depth, S6b tie, S6c tie swapped | **Equal** | The tie is broken by declaration order in both, and swapping order flips the winner in both. |
| Dependency scopes | S7 | **Equal** | `provided` and `test` propagate as Maven does. |
| Optional dependencies | S8 | **Equal** | A dependency's optional dependency is dropped; the root's own optional is kept. |
| Profile activation | S9a–S9f, S9h | **Equal** when the harness is given the same inputs | Property, `activeByDefault`, JDK range, file, OS family, CLI `-P`, `-P !id`, `dependencyManagement` inside a profile, and a profile declared in a parent. |
| Profile activation, **inputs not mirrored** | S9g | **Differs** | See §3.1. |
| Missing offline artifacts | S10a–S10d | See §3.2 | |
| Conflicting dependency families | S11a both, S11b excluded, S11c optional, S11d test scope | **Equal** | The tools agree on what is present; deciding it conflicts needs a knowledge source (policy "Claim strength and knowledge sources"). |
| Relocation (extra) | S12 | **Equal** | Both show only the target. |
| Version ranges (extra) | S13a, S13b | See §3.3 | |

### 3.0 Completeness versus environment fidelity

The study's two kinds of divergence are different failures and are kept
apart in the contract:

| Axis | Question | Study evidence | Failure direction |
| --- | --- | --- | --- |
| **Completeness** | Does the graph hold every node its inputs produce? | S10a/S10b (a missing POM becomes a silent leaf in both tools), S13 (a range cannot be resolved), a cap hit. | False negative: the missing node may be the one that matters. |
| **Environment fidelity** | Is the resolution context the real build's context? | S9g (profile inputs not mirrored), S14 (an extension the resolver ignores), a differing engine or JDK. | **Either direction:** a real dependency absent, or an assumed one that the real build does not have. |

A graph can be complete and unfaithful (S9g: every POM resolved, wrong
profile set), and faithful and incomplete (S10a). `available` requires both.
All fidelity measurements above are therefore statements about equal
*inputs*, and say nothing about whether a reviewer's inputs equal the real
build's.

### 3.1 Profile activation (S9g) — false negative

With `-Dfeature=1` Maven activates a profile that adds `pf-prop`. A harness
run without that property omits it. **This is the largest fidelity risk:** the
graph is internally correct for the inputs it was given, and wrong for the
real build. It can only produce a **false negative** (a dependency the real
build has is missing), never a false positive. The cause is not the engine but
the *input*: the reviewer cannot know which `-P`/`-D` the team's CI uses.

**Rule:** the contract's "Fail-closed resolution inputs" table makes this
`partial`, eligible only on paths independent of the profile. The authoritative
source of activation inputs is a production-enablement gate (G4); reading
`.mvn/maven.config` as inert text is a candidate this study did not test.
The error can also be a **false positive** (a profile active by default in the
harness that the real build deactivates), which is why fidelity is a separate
axis from completeness.

### 3.2 Missing offline artifacts

| Case | Real Maven offline | Harness | Risk and rule |
| --- | --- | --- | --- |
| S10a transitive POM absent | **Succeeds with a warning**; the node appears as a leaf | Same tree, plus a `DESCRIPTOR-MISSING` event | **False negative if treated as complete**: the missing POM may be exactly the one that carries the non-FIPS family. Rule: any `DESCRIPTOR-MISSING`/`INVALID` makes the side `partial`. |
| S10b direct POM absent | Same | Same | Same. |
| S10c parent POM absent | **Fails** | Model error | Side is `missing`; Context gap names the artifact. |
| S10d imported BOM absent | **Fails** | Model error | Side is `missing`. This is the shape of an unreachable private BOM. |

### 3.3 Mutable metadata

`[1.0,2.0)` needs `maven-metadata-*.xml`. With none, Maven fails; with a
`central` metadata file Maven picks 1.5, while the harness (no repository
list) cannot read it and reports a collection exception. This is a **false
negative** if ignored and is detected, so: any version range, `LATEST`,
`RELEASE`, or `SNAPSHOT` makes the side `partial` unless pinned to a captured
metadata snapshot.

### 3.4 Unsupported cases and fail-closed rules

| Case | Observed | Fail-closed rule |
| --- | --- | --- |
| `.mvn/extensions.xml` present (S14) | Maven errors here (the synthetic extension is absent offline); the harness **ignores it silently and returns a graph** | An explicit pre-check, never a resolver outcome: side is `missing` (D6, decided). |
| Build extensions, non-XML (polyglot) POMs | Not exercised; the model builder cannot read them | Detect and fail closed: `missing`. |
| Project-declared repository (S15) | Harness ignores it and records it | Always ignored (§5). |
| Missing descriptor / collection exception / version range | See §3.2–3.3 | `partial`. |
| Unknown or extension-defined packaging type | Not exercised | `partial`. |
| Resolver or Maven version other than the pinned tuple | Not tested | `mismatched` (D4). |

## 4. The original regression, reconstructed

**Method.** The Head-side chain was resolved from real public POMs with real
Maven (online once, into the isolated cache) and then re-resolved offline by
Maven and by the harness: 19 of 19 runs identical (17 versions, plus two
reruns with a different local-repository manager). Direct dependencies added
to each run were `bc-fips 1.0.2.4` and `bcpkix-fips 1.0.7`, as in the Epic.

**Exact graph results, by `spring-cloud-starter-bootstrap` version** (all
other nodes omitted; every run also holds the two FIPS artifacts):

| starter-bootstrap | `spring-security-rsa` | Non-FIPS BouncyCastle |
| --- | --- | --- |
| 3.0.0 – 3.0.2 | 1.0.9.RELEASE | `bcpkix-jdk15on` 1.64 → `bcprov-jdk15on` 1.64 |
| 3.0.3 – 3.0.5, 3.1.0 – 3.1.3 | 1.0.10.RELEASE | `bcpkix-jdk15on` 1.68 → `bcprov-jdk15on` 1.68 |
| 3.0.6, 3.1.4 – 3.1.7 | 1.0.11.RELEASE | `bcpkix-jdk15on` 1.69 → `bcprov-jdk15on`, `bcutil-jdk15on` 1.69 |
| **3.1.8** (the Epic's Head) | **1.0.12.RELEASE** | **`bcpkix-jdk18on` 1.73 → `bcprov-jdk18on`, `bcutil-jdk18on` 1.73** |
| 3.1.9 | 1.0.13.RELEASE | `bcpkix-jdk18on` 1.78 → `bcprov-jdk18on`, `bcutil-jdk18on` 1.78 |

Each row was read from the real Maven baseline tree for every listed version.

**What this shows.**

1. The Head path is
   `jsk-bom → spring-cloud-starter-bootstrap 3.1.8 → spring-cloud-starter
   3.1.8 → spring-security-rsa 1.0.12.RELEASE → bcpkix-jdk18on 1.73 →
   bcprov-jdk18on 1.73, bcutil-jdk18on 1.73`, with the `bc-fips` pair beside
   it. This is detectable by a metadata-only resolver.
2. **`spring-cloud-starter-bootstrap` exists only from 3.0.0** (the
   artifact's published versions are 3.0.x, 3.1.x, 4.x, 5.x). Every version
   from 3.0.0 through 3.1.7 already pulls non-FIPS BouncyCastle through
   `spring-security-rsa`, under the `jdk15on` name. **So if the real Base
   already carried `spring-cloud-starter-bootstrap` at any 3.0.0–3.1.7
   version, non-FIPS BouncyCastle was already on the Base classpath, and the
   BOM bump changed it to the `jdk18on` family rather than introducing
   non-FIPS BouncyCastle.** The claim that the upgrade first introduced it is
   not supported by public data and must not be assumed.
3. It is supportable only if the Base lacked the dependency or excluded the
   family — facts that live in the private repository and `jsk-bom`.

**Exact Base/Head delta: unavailable.** `jsk-bom 2.16.29` and `2.16.39` are
not published on any public index that was checked (Maven Central search
returned no `jsk-bom`), so their managed versions, any exclusions, and the
repository's own POMs are unknown. The real Base and Head graphs therefore
cannot be reconstructed here. Marking them unavailable is the honest result.

**Delta shape in each possible case**, which #725's fixture must resolve from
the real BOMs:

| Real Base | Stage 1 delta | What a finding may say |
| --- | --- | --- |
| Lacked `spring-security-rsa` | `added` rsa, `bcpkix-jdk18on`, `bcprov-jdk18on`, `bcutil-jdk18on` | Newly introduced non-FIPS family beside `bc-fips`. |
| Had it at 3.0.0–3.1.7 | `removed` `jdk15on` keys, `added` `jdk18on` keys (different keys; no `replaced` link without relocation data) | The non-FIPS family was already present; it moved to a new name and version. Attribution to this change is "version/name change", and the pre-existing risk follows the contextual-evidence model's pre-existing-risk note. |

**Compatibility evidence.** The graph proves co-presence of the FIPS and
non-FIPS BouncyCastle families on the compile scope. It does **not** prove
incompatibility. That requires a knowledge source (a repository-declared
policy or curated data) that does not exist yet; under the contract the
absence of one makes the claim `speculative`.

## 5. Security observations

| Requirement | Evidence | Strength |
| --- | --- | --- |
| No untrusted repository code | Only the model builder and resolver libraries ran; plugin processing off; no extension loader. | Structural (code) and observed. |
| **No network** | The harness registers no HTTP/Wagon transport, has an empty repository list, and ran under `(deny network*)`. Negative control: the same sandbox fails DNS for `curl` (exit 6). | Structural **and** OS-enforced. |
| **Project-declared repositories are an exfiltration channel** | A synthetic POM declared `http://127.0.0.1:18999/x/${env.SECRET_TOKEN}/${user.home}`. **Real Maven, run online, sent `GET /x/DECOY-ENV-TOKEN/Users/<user>/org/synth/...`**. The harness, run unsandboxed so it could have, sent **zero** requests. | Measured. Confirms INJECT-027. |
| No credentials | Decoy `settings.xml` (server password, mirror) and decoy SSH key were placed under the `HOME` both tools used. Both tools completed correctly while reads under that tree were **denied by the sandbox** (control: `cat` of the decoy failed). | Shows neither *needs* them. Whether either *attempted* a read was not provable (sandbox trace and denial logging were unavailable); for the harness that guarantee rests on the source, which names no settings API. |
| No writes to the user's cache | All runs used an isolated repository. Separately, the harness ran against a **read-only copy** (`chmod a-w`): five runs succeeded and a content/mtime digest was identical before and after (2,372 files). The user's real `~/.m2` file count stayed at 1,840 with nothing newer. | Measured. |
| No silent fallback to Maven | The harness has no code path that executes Maven; the sandbox runs it with no `mvn` on `PATH`. Policy must still forbid fallback. | Structural. |
| Resource abuse | Parent cycle and import cycle: refused by the model builder in 0.1 s. A 1,500-deep chain: 0.6 s. 5,000 direct dependencies: 1.3 s. A 22-layer diamond lattice: 0.2 s. A billion-laughs POM and an XXE (`file:///etc/hosts`) POM: both refused as non-parseable. All ran with `-Xmx256m`. | Measured on one machine; caps must still be enforced by the tool. |

## 6. Dedicated cache versus `~/.m2`

Facts about a real `~/.m2/repository` (names and counts only; no file
contents were read): 428 `_remote.repositories` files, 427 POMs, 212 JARs,
648 `.sha1`, 12 `maven-metadata*.xml`, 22 `.properties`, 3 `SNAPSHOT`
paths. The same directory tree also holds `settings.xml` and
`settings-security.xml` when a user has them.

| | Direct `~/.m2` | Dedicated cache |
| --- | --- | --- |
| Provenance | Mixed: every artifact keeps its source repository id; private and public mixed | Single, recorded source per POM |
| Integrity | Unknown; whatever any past build wrote or a hostile build poisoned | Digest manifest created at import, verified at read |
| Mutable state | `.lastUpdated` markers, SNAPSHOTs, `resolver-status.properties`, `maven-metadata-*.xml` | Release POMs only; metadata only if captured |
| Credentials nearby | `settings.xml` and `settings-security.xml` are siblings of `repository/` | None |
| Concurrency | A running Maven may write it | Immutable |
| Reproducibility / binding | Weak | Closure digest is meaningful (§7) |
| Coverage for the author's own change | **Best** — the author's build already cached Head | Needs an import step |

**Recommendation: a dedicated, read-only cache.** `~/.m2` can be an *import
source* for POM files, never the resolution root. The harness behaved
identically on a read-only copy, and with the enhanced local repository
manager despite 428 `_remote.repositories` files, so a dedicated store costs
nothing in fidelity. What was **not** tested: running against a user's real
`~/.m2` content.

## 7. Recommended offline architecture

```text
review target ──► activation: a changed declaration alters the resolved set?
                       │
        pre-checks (data only): .mvn/extensions.xml, build extensions,
        non-XML POMs, unsupported packaging  ──► partial / missing
                       │
   pinned resolver tool  (D1)  ── runs in a sandbox: no network, no write
                       │          outside its output directory, read only
                       │          target POMs + the cache + its own tool
        reads  ◄───────┴──────►  dedicated read-only POM cache (D5)
                       │
   normalized graph  +  events  +  closure digest (sha256 of every POM read)
                       │
   evidence state: available | partial | missing | mismatched ...
```

1. **Cache.** Populated by a separate **import** step outside any review,
   from allowlisted sources, with each POM's digest recorded. The review
   never writes to it.
2. **Tool.** Pinned, reviewer-owned, installed by the user and merely
   detected by the Skill (the rendered-inspection-environment precedent).
   Fixed arguments, no shell, scrubbed environment, an empty `HOME`, no
   settings, no HTTP transport.
3. **Sandbox.** Required. If the sandbox primitive is unavailable the side is
   `missing`; there is **no fallback** to unsandboxed or to Maven.
4. **Binding.** The closure digest was reproduced bit-for-bit across two runs
   (84 POMs for the 3.1.8 chain; none read from outside the cache or the
   project). Base and Head are `mismatched` unless produced by the same tool
   tuple and environment.
5. **Fail closed.** Every rule in §3 maps to `partial` or `missing`; nothing
   becomes a finding.

## 8. Limitations of this study

- **One engine tuple** (Maven 3.9.16 / Resolver 1.9.27) and one JDK. Maven 4
  and Resolver 2.x were not measured; Resolver's own documentation says
  dependency-management scoping differs between 1.x and 2.x.
- **One OS and one sandbox mechanism.** `sandbox-exec` on macOS. A Linux
  mechanism was not validated.
- **Mostly synthetic POMs.** Real-world POM quality (broken POMs, unusual
  profiles, parent chains of dozens of levels, BOMs with activation) was
  tested only through the Spring Cloud chain.
- **`${env.*}` and system-property interpolation** inside versions or
  coordinates was not tested for divergence (the harness uses a fixed
  environment).
- **Closure-digest binding and `.mvn/maven.config` parsing** are
  prototype-level or untested.
- No Windows, no concurrency, no multi-module reactor with inter-module
  dependencies.

## 9. Approved boundaries and their exact requirements

These are the conditions under which the maintainer approved the architecture
in principle. **Approval is not enablement:** every item below is subject to
the production-enablement gates, and nothing here runs a resolver. D2 and D3
are **not authorized**, so no variant that fetches a POM or uses a credential
exists in this contract; the dedicated cache is populated outside the review
by a step this contract does not define and does not authorize.

### D1 — admit a reviewer-owned, pinned, non-repository executable class

- A new class, `reviewer-owned-resolver`, in its own policy section, stating
  that `runtime-validation.md`, `repository-checkout.md`, and
  `trusted-host-execution.md` are **not** relaxed. It is not a repository
  command and is never selected from repository declarations.
- Identity: a named tool with a pinned engine tuple and a recorded SHA-256 of
  the distribution; built from reviewer-owned sources; never `mvn`, `mvnw`,
  `mvnd`, or a repository-supplied binary.
- Invocation: fixed argv, no shell, scrubbed environment, empty `HOME`, no
  settings, explicit profile and property inputs only.
- Containment: required OS sandbox with network denied, writes denied except
  the output directory, reads limited to the target's POM paths, the cache,
  and the tool. Unavailable sandbox ⇒ `missing`; no fallback.
- No transport other than file; no HTTP or Wagon classes on the classpath. **No network (D2) and no credentials (D3).**
- Distribution: installed by the user; the Skill only detects it.
- Limits: heap, wall time, POM count, depth, node count, and byte caps enforced
  **inside** the tool; a hit makes the side `partial`.

### D4 — engine pinning policy

- One supported tuple (the tested Maven/Resolver/JDK) until a wider one is
  measured; the tuple, environment (JDK, OS properties, empty env), and
  activation inputs are recorded in provenance.
- Base and Head must use an identical tuple and inputs, else `mismatched`.
- **Admission gate for any tuple change:** the §3 scenario set must pass with
  zero unexplained divergences, and a real-world differential corpus (§10)
  must meet a pre-registered threshold.
- Maven 4 / Resolver 2.x are unsupported until measured.
- Profile-activation inputs: who may state them (the caller; `.mvn/maven.config`
  as inert text if tested) and the `partial` rule of §3.1.

### D5 — the cache grant

- A **dedicated, read-only cache**, granted per invocation as an absolute
  path by the caller; never inferred from `~`, `$HOME`, `M2_HOME`, the
  environment, or any settings file.
- Realpath-confined; symlinks refused; only `.pom` files (and
  `maven-metadata-*.xml` only when a pinned-version policy captures it) are
  read; never `settings*.xml`, `settings-security.xml`, JARs, or
  `resolver-status.properties`; `.lastUpdated` is read only as "missing".
- Each POM's digest recorded; sibling checksum verified where present.
- `~/.m2` is an import source only, copy-in by explicit step, never the
  resolution root.

### D6 — fail-closed on extensions and unsupported inputs

- The exact states are in the contract's "Fail-closed resolution inputs"
  table: extensions, non-XML POMs, extension-defined packaging, and
  uninterpretable `.mvn` options are `missing`; missing descriptors,
  collection exceptions, version ranges, `LATEST`, `RELEASE`, `SNAPSHOT`,
  and unestablished profile inputs are `partial`; differing contexts are
  `mismatched`.
- Repositories that use extensions are outside the Maven reference scope
  until a later, measured decision supports specific extensions.

## 10. Remaining risks

1. **Real-world fidelity is unmeasured.** A differential corpus of public
   Maven projects (graph-equality rate, with every divergence categorized) is
   required before enabling; it should be pre-registered as in #725.
2. **Profile selection** remains the main false-negative source.
3. **Private BOMs** (such as `jsk-bom`) need the import step to reach a private
   repository, which reintroduces credential custody (D3) outside the review.
4. **Cache poisoning at import time** is moved, not removed.
5. **Knowledge source** for family compatibility does not exist and is
   independent of acquisition.
6. **Sandbox portability** (Linux) is unvalidated.
7. **Maven 4 / Resolver 2.x** drift.
8. The harness is research code; a production tool needs its own review.

## 11. Status after the maintainer decision

The architecture and the boundaries D1, D4, D5, and D6 are **approved in
principle**; D2 and D3 are **not authorized**. Enabling the capability
remains blocked on every gate in the contract's "Production-enablement
gates" (G1–G8). At the time of this record none is satisfied:

| Gate | Status |
| --- | --- |
| G1 Real-world differential corpus | Not started. |
| G2 Pre-registered fidelity thresholds | Not set; a maintainer must fix and commit them before the counted run. |
| G3 Validated Linux sandbox | Not validated (macOS `sandbox-exec` only). |
| G4 Profile-activation source of truth | Undecided and untested. |
| G5 Verified compatibility sources | None exist; the BouncyCastle FIPS/non-FIPS records are unwritten. |
| G6 Security and regression tests | Threat scenarios have `#724` pointers, not tests. |
| G7 Engine pinning | One tuple measured; no distribution digest or tool exists. |
| G8 Incident evidence | The private `jsk-bom` evidence has not been supplied. §12 proposes splitting this gate; not applied. |

**Maven stays in scope for Epic #722; nothing here reduces it.**

## 12. Gate G8 — scope proposal (for maintainer approval)

**Question.** Is private-BOM evidence necessary for *general* Maven resolver
enablement, or only for validating the *original incident*?

**Finding.** G8 currently reads as an enablement gate for the whole
capability. Its two halves have different reasons and different evidence:

| Half | What it protects | Is private evidence needed? |
| --- | --- | --- |
| **G8-general:** enabling the resolver for Maven graphs | That the resolver is faithful and safe on real projects, including projects whose BOMs are unreachable | **No.** General fidelity is measured by G1 and G2 on public projects, where private evidence is an n=1 sample that cannot substitute for the corpus. The *handling* of an unreachable private BOM is a fail-closed behavior already tested synthetically (S10d: missing BOM ⇒ `missing`) and under G6. |
| **G8-incident:** any claim that the original incident was reproduced or detected | That a result is about the real incident and not an analogue | **Yes.** Only the authentic Base/Head `jsk-bom` POMs, the repository's POMs, the real resolved trees, and the real build's profile and property inputs can establish the delta, whether non-FIPS BouncyCastle was newly introduced or merely renamed, and the profile context. |

**Proposed distinction (not applied).** Keep G8 verbatim in the contract until
a maintainer approves a split into:

- **G8a — private-BOM handling:** satisfied by the fail-closed tests for an
  unreachable BOM and parent (no private evidence required).
- **G8b — incident claim:** authentic Base/Head evidence supplied. It gates
  the incident-detection claim, the Epic's incident criterion, and the
  incident's end-to-end fixture, and **does not** gate enabling the resolver
  for other Maven projects.

**Consequences if approved.** Resolver enablement could proceed on G1–G7 plus
G8a without the private evidence, while Epic #722's incident criterion and
any statement that "the original incident is detected" would remain
**unsatisfied** until G8b. Nothing is silently removed: the incident evidence
stays required for the Epic, only its role as an enablement prerequisite for
unrelated projects is questioned. **If not approved, G8 stays as written and
blocks enablement.** Until a decision, the contract is unchanged and the
capability remains disabled either way.
