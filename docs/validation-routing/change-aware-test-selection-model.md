# Change-Aware Test Selection — Model

Contract-first design for [#624](https://github.com/amirbena/code-review-skill/issues/624).
Navigation: [`README.md`](README.md). Nothing here is implemented; every
"proposed" item needs maintainer agreement before an implementation issue is
opened (see [Proposed implementation issues](#proposed-implementation-issues)).

## 1. Evidence: what the current router does and why `docs/**` is FULL

`ci_test_route.py` is a fixed allowlist (`FAST_FILES`, `FAST_DIRS`) over a
three-dot, rename-split path set. Anything not on it — including every
`docs/**` path — is FULL, with the reason "a changed path is not on the FAST
allowlist". The #623 change (two files under `docs/rendered-inspection/`)
therefore ran FULL purely because the paths are unlisted, not because
anything consumes them.

#533 kept `docs/**` FULL on explicit readmission conditions: integration temp
roots no longer copy `docs/` **or** a guard proves no invoked script reads it,
and the guard is extended to cover it. The model below satisfies the guard
branch of that condition (§5).

### 1.1 Who actually consumes `docs/`

Measured on this tree (preliminary; the implementation must derive it, not
trust this table):

| Consumer kind | Example | Consequence |
| --- | --- | --- |
| Literal-path readers | ~140 test modules reference `docs`; e.g. `test_instruction_architecture` reads `docs/features/*`, `test_review_result_docs` reads `docs/findings`, `docs/finding-confidence` | The doc is a **test input**; editing it can fail that test |
| Directory-wide scanners | `test_forbidden_repository_terms` (every tracked text file via `git ls-files`), `test_benchmark_root_migration` (every tracked file and `.md` link), `tests/unit/governance/test_validate_markdown_links.py` (repo-wide link check) | Content-agnostic; they apply to **every** doc, pure or not |
| Script readers | `scripts/security/validate_threat_model*.py` read `docs/threat-model/catalog/*.yaml`; packaging/metadata generators cite capability docs in prose only | Directly consumed data |
| Integration temp-root copy | `TEMP_ROOT_INPUTS` in `tests/integration/packaging/_shared.py` copies `docs/` into a build root; two integration tests run packaging/release scripts there | A copy is a build input; inert only if no invoked script reads it |
| Release classification | `release_lib/classification.py` already maps `docs/` to the non-release `docs` category | Existing precedent for a docs notion; unrelated to test selection |

Observed asymmetry: several `docs/<dir>/` directories have **no** literal
consumer (for example `docs/rendered-inspection/`; its user-facing twin
`docs/features/rendered-inspection.md` *is* pinned by
`test_rendered_inspection_feature_docs`). So the same directory name can be
pure in one place and consumed in another — only per-path evidence is sound.

## 2. Classification

Classification is by dependency evidence. Extension never decides a class;
it only narrows the candidate set (§2.1).

| # | Class | Definition | Outcome |
| --- | --- | --- | --- |
| 1 | **Pure documentation** | Every changed path is a tracked Markdown file under `docs/` that the consumer index (§3) shows has **no** consumer other than the registered static scanners | Tier **DOCS**: static documentation validation only (§2.2); zero unit, integration, benchmark, or live suites |
| 2 | **Consumed / behaviorally significant documentation** | A docs path (or a root/`policies/` doc) with at least one consumer, or a non-Markdown file under `docs/` (JSON/YAML are data) | Only the validation its consumers require. **Phase 1: FAST** (all non-integration tests run); **phase 2 (optional): TARGETED** = the indexed consumer modules + static scanners |
| 3 | **Mixed docs + code/infrastructure** | Any non-doc path is present | Classified from the non-doc paths alone; docs contribute at most "at least FAST", never a lower tier |
| 4 | **Unknown / high-risk** | Empty, renamed-to/from an unindexed path, router/index error, unrecognized path, or a high-risk path (§2.3) | **FULL** |

Tier order is `DOCS < TARGETED < FAST < FULL`; a change set takes the
**maximum** tier of its paths. Any exception, timeout, or unrecognized state
resolves to FULL, exactly as `safe_route` does today.

### 2.1 Why Markdown-only for class 1

Class 1 is restricted to `docs/**/*.md` *and* proven unconsumed. The
restriction is a safety floor, not the criterion: a `.md` file that is
consumed is class 2, and a non-`.md` file under `docs/` (for example
`capability-loading-baseline.json`, `docs/threat-model/catalog/*.yaml`) is
never class 1 even if the index finds no reader, because data files are the
most likely hidden inputs.

### 2.2 What runs for each tier

| Tier | Runs | Does not run |
| --- | --- | --- |
| **DOCS** | `validate-markdown-links.py`; the registered static scanners (§3.3: forbidden-terms and benchmark-root-migration reference scans); the cheap non-test steps `validate.yml` runs on every tier today (metadata validation, canonical build, spec validation, parity jobs) | `tests.unit.*`, `tests.policy.*` (other than registered scanners), `tests.repository.*`, `tests.integration.*`, benchmark, live-model |
| **TARGETED** (phase 2) | Indexed consumer modules + registered scanners + non-test steps | Everything else |
| **FAST** | Unchanged from #533: full discovery minus `tests.integration.*` | `tests.integration.*` |
| **FULL** | Unchanged: `python -m unittest discover -s tests -t .` | nothing |

The `test` job and its required-check name are unchanged; tiers only change
which step body runs inside it. The cheap non-test steps are kept on every
tier so the workflow diff stays minimal (open question Q2).

### 2.3 Never small (always FULL, never DOCS/TARGETED/FAST)

Shared test infrastructure (`tests/support/**`, `tests/reference/**`, any
`tests/**` change), manifests (`package-manifest.json`, `capability.yaml`),
schemas, `benchmark/`, `runtime_platform/`, `scripts/packaging|release|sandbox|skill_metadata/**`,
`skills/**`, `shared/**`, `capabilities/**`, `distribution/**`, `CHANGELOG.md`,
`LICENSE`, `.github/workflows/**`, `requirements-dev.txt`, and the router,
classifier, or consumer-index code itself. This list is the default-deny
complement of "everything not positively proven small"; it exists so a bug in
the index cannot lower these paths. Today's FAST allowlist (root docs,
`policies/**`, issue/PR templates) is unchanged and remains class 2.

## 3. Mechanism: derived consumer index, no per-directory allowlist

Rejected alternatives:

| Option | Why not |
| --- | --- |
| Add `docs/<dir>/` to `FAST_DIRS` | The #623 anti-pattern: per-directory maintenance, no dependency knowledge |
| Treat all `docs/**/*.md` as pure | Wrong: tests pin docs (§1.1) |
| Opt-in `DEPENDS_ON` markers in tests | Unsafe default: an unmarked consumer is invisible |
| Runtime read-tracing as the primary signal | Needs a full run to classify; non-deterministic. Kept only as an optional offline cross-check of the static index |

**Proposed:** a stdlib-only classifier computes a *consumer index* by static,
over-approximating scan of the **base** tree (a docs-only PR cannot add a
consumer; one that also edits `tests/**` is class 3 and FULL). Scanned
producers: `tests/`, `scripts/`, `runtime_platform/`, `benchmark/`,
`capabilities/`, `distribution/`, `.github/`.

### 3.1 Resolution rules (all fail toward "consumed")

A doc path `D` is **consumed** if any scanned file contains:

1. `D` as a string, or any ancestor directory of `D` below `docs/` as a string
   (`docs/x/`) — so referencing a directory consumes everything under it;
2. a joined form (`REPO_ROOT / "docs" / "x"`, `joinpath`, `Path("docs", ...)`)
   that resolves to `D` or an ancestor;
3. a docs-root access with enumeration (`rglob`, `glob`, `iterdir`,
   `os.walk`, `git ls-files`) that is **not** a registered static scanner
   (§3.3) — consumes the enumerated subtree, or all of `docs/` if the base
   cannot be resolved;
4. an access whose path cannot be statically resolved (variable, f-string) and
   whose root is `docs` or `REPO_ROOT` — consumes the whole parent subtree.

A doc is **integration-inert** only if (a) `docs/` appears in an integration
temp-root copy list *and* (b) no integration test, and no script reachable
from the scripts those tests invoke, matches rules 1–4 for it. Where (b)
fails for a subtree (for example `docs/threat-model/` read by
`scripts/security/*`), that subtree is class 2 with integration retained.

### 3.2 Why derive instead of declare

A hand-kept list drifts silently. A derived index changes the moment a
consumer is added: the PR that adds the consumer touches `tests/**` or
`scripts/**` (class 3/4 → FULL), and the *next* doc-only PR is classified
against a base that already contains the consumer.

### 3.3 Registered static scanners

Content-agnostic scanners apply to every doc and are the DOCS-tier test set.
They are a small explicit registry (module IDs) in the classifier, not a
convention: `validate-markdown-links.py`, `tests.policy.governance.test_forbidden_repository_terms`,
`tests.policy.benchmark.test_benchmark_root_migration` (reference scans only —
confirm during implementation which of its tests are content-agnostic).
Adding a new tracked-file scanner without registering it fails the guard (§4).

## 4. Drift guard

A new policy test (always runs, FAST or FULL) asserts:

1. **Visibility** — every access to `docs/` or `REPO_ROOT` in the scanned
   producers matches one of resolution rules 1–4 or is a registered scanner.
   An unrecognized access form fails with the file and line, so the index can
   never silently under-report.
2. **Scanner registry** — any module using `git ls-files`, `rglob`, or
   `os.walk` over the docs tree is in the registry; an unregistered one fails.
3. **Reclassification** — in a synthetic repo, a pure `docs/new/x.md` is
   class 1; adding a test that references it makes it class 2; adding only a
   directory-wide non-registered reader makes the whole subtree class 2.
4. **Temp-root inertness** — if any integration copy list contains `docs/`,
   the integration-inert set excludes everything a reachable script reads.
5. **High-risk floor** — every path in §2.3 classifies FULL regardless of
   index contents (including with an empty or corrupt index).

This extends the existing `test_ci_test_routing.py` tripwire and discharges
the #533 readmission guard condition for `docs/**`.

## 5. Shared by CI and local validation

One module — **proposed** `scripts/validation/change_classifier.py` — owns
path classification, the index, tier ordering, and the human-readable
summary. Both entry points call it:

- **CI:** `ci_test_route.py route` delegates to it (the base-extraction trust
  model of #533 is unchanged: the classifier is read from the base commit, so
  a PR editing it is FULL). Output keeps `tier=` and adds `class=`; the step
  summary states class, tier, reason, and the first path that forced a
  broader tier.
- **Local:** `ci_test_route.py classify --base <ref>` (or `--working-tree`)
  prints the identical summary plus the exact commands for the tier
  (replacing the README prose table's role with a computed answer). Local
  `FULL` still means "optional, not required" per the existing policy; the
  tool only states what CI would select.

[#183](https://github.com/amirbena/code-review-skill/issues/183) (preflight)
is **not** a prerequisite and should not be blocked on this. Once both exist,
preflight's test step should consume `classify` output rather than re-encode
semantics. This keeps #183 orchestration-only, as its scope requires.

## 6. No-live-execution invariant

Selection never *adds* work and never executes the suites it selects. The
classifier and `classify`: read git output and repository files only;
perform no network, model, benchmark, or sandbox execution; and never set or
change `BENCHMARK_REQUIRE_RUNTIME`, `DISTRIBUTION_INSTALL_CHECK`, or
`BENCHMARK_MIGRATION_BASE`. Workflow tier steps keep today's env exactly
(`DISTRIBUTION_INSTALL_CHECK` stays on FAST/FULL; DOCS runs no suite so it
needs none). A test asserts the classifier module imports no network, model,
or subprocess-beyond-`git` facility.

## 7. Deterministic selector test plan

Pure-function tests over path lists plus a synthetic repo fixture (no live
git history required beyond `git init` in a temp dir):

| Case | Expected |
| --- | --- |
| #623 path set (`docs/rendered-inspection/README.md`, `…-contract.md`) | class 1, DOCS, reason names "no consumer" |
| Same set after adding a literal consumer test to the fixture | class 2 |
| `docs/features/rendered-inspection.md` alone | class 2 (pinned by feature-docs test) |
| New `docs/<new-dir>/x.md`, no consumer | class 1 without any list edit |
| Non-Markdown under `docs/` | class 2 minimum |
| Pure doc + any §2.3 path | class 4, FULL, forcing path reported |
| Pure doc + consumed doc | class 2 |
| Empty set; rename (D+A split); git failure; classifier exception; missing base/head; non-`pull_request` event | FULL |
| Corrupt or empty index | every non-pure-by-construction path FULL |
| Tier ordering is max over paths; reason and forcing path stable and deterministic | asserted |
| CI summary and local `classify` output identical for the same input | asserted |
| No label/flag/env input can select a lower tier | asserted |

## 8. Resolving the #533 blocker

`docs/**` leaves the blanket-FULL set only through §3–§4: per-path consumer
evidence plus the guard, which is the readmission route #533 allowed. #533's
invariants are untouched: FULL remains the default and the semantic
fallback; FAST still never removes a contract or correctness test; no label or
flag selects a tier. The DOCS tier is **new and separate** from FAST, and
skips unit/policy suites only for paths with positive no-consumer evidence
(the registered scanners still run, covering the content-agnostic tests that
read arbitrary docs). Whether a distinct DOCS tier is acceptable alongside
the #533 wording is the main maintainer decision (Q1).

## 9. Non-goals and security boundary

No nightly tier, no sandbox/adversarial test changes, no parallelization, no
required-check change, no change to #396–#400, runtime, packaged resources, or
review/benchmark semantics. Security-adjacent coverage ("Cluster 7" of #395)
is not reduced: `scripts/sandbox/**`, `docs/threat-model/**` consumers, and
`tests/integration/sandbox/**` stay FULL / consumed.

## 10. Open questions for the maintainer

- **Q1.** Is a distinct DOCS tier acceptable alongside #533's "FAST never
  removes contract tests", or should class 1 also run FAST (still cheaper than
  FULL and trivially within #533)? Recommendation: start with DOCS gated on
  the guard; fall back to FAST if the guard's first iteration is contested.
- **Q2.** Keep metadata validation, canonical build, spec validation, and
  parity jobs on the DOCS tier? Recommendation: yes (≈20–35 s, no workflow
  restructuring, no required-check change).
- **Q3.** Phase 2 TARGETED worth the complexity, given class 2 → FAST already
  removes the ~73% integration cost? Recommendation: defer until measured.
- **Q4.** Should root docs (`README.md`, `AGENTS.md`, …) and `policies/**`
  migrate from the allowlist into the index later? Recommendation: leave
  unchanged in phase 1.
- **Q5.** Location of this record: proposed `docs/validation-routing/`; move
  if the maintainer prefers another home.

## Proposed implementation issues

Proposed to the maintainer only; none is opened by this record. All
`maintainer-led` (they change validation policy and a required-check input).

1. **Shared change classifier + consumer index** — `change_classifier.py`
   (classes, tiers, §2.3 floor, §3 index), pure unit tests per §7, no
   workflow change. Blocks 2–4.
2. **Drift guard** — §4 policy test and scanner registry; extends
   `test_ci_test_routing.py`. Depends on 1.
3. **CI wiring** — `ci_test_route.py` delegates to the classifier; DOCS tier
   step and `class=` output in `validate.yml`; update
   `policies/validation-and-clean-exit.md` ("Routed CI tests"). Depends on 1–2.
4. **Local `classify` command** — same summary and tier commands; replace the
   README targeted-validation table with a pointer; align
   [#183](https://github.com/amirbena/code-review-skill/issues/183)
   preflight afterwards. Depends on 1.
5. *(optional)* **TARGETED tier** — only if measurement after 3 justifies it.
