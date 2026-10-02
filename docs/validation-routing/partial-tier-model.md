# PARTIAL Tier — Affected-Scope Selection Model

Design record and implementation notes for
[#634](https://github.com/amirbena/code-review-skill/issues/634). Navigation:
[`README.md`](README.md). The normative description lives in
[`../../policies/validation-and-clean-exit.md`](../../policies/validation-and-clean-exit.md)
("Routed CI tests" → "PARTIAL: affected-scope selection"); this record owns
the rationale. It renames and specifies the "TARGETED" tier that
[`change-aware-test-selection-model.md`](change-aware-test-selection-model.md)
(#624) deferred.

## 1. Problem

The router selected DOCS, FAST, or FULL. Every path under `tests/` was
unclassified by it, so any test-only change — however small — ran the whole
suite, including `tests.integration.*` (about 73% of suite time, #533). FAST
is cross-cutting (everything except integration), not affected-scope; no tier
selected "only what this change can affect".

A change to one test module or one shared helper has a statically knowable
set of affected modules, but the router had no model of it. The set is
derivable, but not trivially:

- Modules import helpers statically (`from tests.support… import …`,
  relative `_shared`/`_harness` imports). `tests/support/paths.py` alone has
  ~180 transitive consumers, so fan-out can approach the whole suite.
- Tests also depend on `tests/` files they do not import: policy tests name
  `tests/unit/benchmark/test_*.py` by path,
  `tests/integration/packaging/_shared.py` reads `tests/support` and
  `tests/reference` as directories, and layout guards enumerate `tests/`.
- Some modules load code dynamically (`importlib`, `sys.path`), and non-Python
  test inputs exist (`tests/unit/review/findings/structured_output_samples/`).

## 2. Principle

> Select the smallest validation surface that can prove the affected
> contract; unknown or ambiguous impact fails upward, never downward.

FULL stays the deliberate high-impact and fallback route.

## 3. Tiers

| Tier | Meaning |
| --- | --- |
| DOCS | Pure documentation with no consumer; static docs validation only (unchanged) |
| PARTIAL | An explicit module set: the affected test surface plus mandatory companions; no full discovery (new) |
| FAST | Full discovery minus `tests.integration.*` (unchanged) |
| FULL | `python -m unittest discover -s tests -t .`, the default and fallback (unchanged) |

Order: `DOCS < PARTIAL < FAST < FULL`; a change set takes the maximum tier of
its paths.

## 4. Mechanism

One module, [`ci_test_route.py`](../../scripts/validation/ci_test_route.py),
owns classification, the graph, the tier order, and the summary. CI `route`
and local `classify` call the same `classify()` and print the same class,
tier, reason, forcing path, and module list. `validate.yml` only invokes the
router (extracted from the base commit) and runs the tier it names.

### 4.1 Derived test-impact graph

Nothing is declared per directory or per helper. A static scan (`ast`, no
imports executed) of every tracked file under `tests/` produces, per Python
file, its dependencies:

| Edge kind | Recognized forms |
| --- | --- |
| Import | `import a.b`, `from a import b` (b as a submodule when it is one), relative imports, imports inside functions, and every package `__init__.py` an import executes |
| Module-name string | `"tests.unit.x"` anywhere (for example `import_module`) |
| Literal path read | `"tests/…"` strings (a bare `tests/` is a command argument or prose, not a read; glob components truncate to the directory), docstrings excluded |
| Path-expression read | `X / "tests" / …`, `Path("tests", …)`, `.joinpath`, `os.path.join`, and `__file__`-relative chains (`.parent`, `.parents[n]`, `os.path.dirname`) |
| Directory read | any of the above that resolves to a directory depends on every file under it |

Only the operands of a path-building node are folded into that node; an
argument of an unrelated call is evaluated on its own, so a `tests/` read is
never hidden inside a call. The closure is the transitive set of consumers
(importers and readers), computed on the **union of the base (merge-base) and
head graphs**, so removed edges, new edges, and a deleted or renamed
helper's former consumers are all covered.

### 4.2 Path to required surface

| Changed path | Required surface |
| --- | --- |
| `tests/**/test_*.py` | itself, every module that imports it, every module that reads it |
| any other `tests/**/*.py` (`support/`, `reference/`, `_shared.py`, `__init__.py`) | the whole closure, with no cap |
| non-Python file under `tests/` | modules that reference it by literal or directory path; none found is FULL, not "no tests" |
| registered companions | `TREE_GUARD_MODULES`, added to every PARTIAL set |
| pure docs | joins as before: `DOCS_SCANNER_MODULES` and the link validator become companions |
| allowlisted FAST path or consumed docs, plus tests | FAST plus the affected `tests.integration.*` modules (`run-fast --modules`) |
| production/shared semantic paths | FULL, unchanged |
| router, classifier, graph builder, registries, `validate.yml`, and their tests | FULL |
| anything not positively classified | FULL |

Union and monotonicity: the surface of a change set is the union of its
paths' surfaces, a FULL path makes the whole set FULL, and adding a path never
removes a module or lowers the tier.

### 4.3 Fail-upward conditions

FULL when: a path is outside the known `tests/` kinds (a top-level `tests/`
directory with no base files included, or a path the graph does not contain);
any scanned file fails to parse or read (stricter than "changed or
in-closure": an unparseable consumer is invisible, so it cannot be ignored);
the closure contains a module whose `importlib`/`sys.path`/subprocess handling
the scan cannot resolve to a known non-tests root or to a literal module name,
or that builds a `tests/` path from dynamic parts (the scan reports the file
and line); the graph is missing, empty, or errors; a path's affected set is
empty; a registered companion is absent from the head tree; the affected set
is the whole suite (the whole suite is then simply FULL); or any module ID is
not a well-formed `tests.…` name at run time. `run-partial` validates every
ID before importing anything and fails if zero tests ran.

### 4.4 The router is FULL by rule

The router is trusted from the base commit, so it cannot vouch for a head
version of itself. A change to the router, graph builder, registries,
`validate.yml`, or their tests is FULL, the only run that exercises the new
router independently of its own routing decision. The router's own tests are
always companions of a PARTIAL set and never replace FULL for such a change.

## 5. Measured fan-out (this tree)

271 test modules; 380 files under `tests/`; the scan takes ~0.6 s. Sample
`classify` results (`classify --base base --head HEAD` in a throwaway clone):

| Change | Result |
| --- | --- |
| docs-only | DOCS |
| one test module | PARTIAL, 10 modules (itself, readers, 6 companions) |
| `tests/support/deepening_contract.py` | PARTIAL, 30 modules (the four direct importers, the integration `_shared.py` readers, whole-tree readers, companions) |
| `tests/support/paths.py` | PARTIAL, 184 modules (the actual closure; nothing dropped) |
| two bounded families | PARTIAL, union (32 modules) |
| `shared/policies/review-scope.md` | FULL |
| docs + test change | PARTIAL, 13 modules, docs scanners, link validation |
| `README.md` + a helper with integration consumers | FAST plus 10 integration modules |
| new top-level `tests/newkind/` | FULL |
| unparseable test file | FULL (graph incomplete) |
| router or `validate.yml` | FULL |
| rename or delete of a helper | PARTIAL including its former consumers |
| non-Python sample input | PARTIAL, 11 modules |

## 6. Accepted limits

- The scan is static and over-approximates. A directory named by a string
  counts as a read only as an argument of a filesystem or subprocess call
  (`"pytest", "tests/unit"` or a doc link is not a read); a path expression
  that resolves to a directory always counts. A genuine whole-tree reader
  (for example the layout guards) is therefore selected by most test changes,
  which costs a few modules, never correctness.
- Git reads of `tests/` blobs time out after 120 s (`GIT_READ_TIMEOUT`); a
  stalled lazy fetch routes FULL rather than hanging the job.
- A path assembled by arithmetic the scan does not model is reported, with
  file and line, by the drift test (`test_real_tree_has_no_unresolved_access_forms_or_scan_problems`)
  and makes its closure FULL at run time.
- Module granularity only; no per-class or per-case selection, and no mapping
  of production source to tests.
- Reading the base graph reads `tests/` blobs from the route clone, and the
  graph is built only when a test path changed. The workflow's clone is
  blobless, so the route step first runs a best-effort sparse checkout of
  `tests` at the base commit, which fetches those blobs in one batch (a probe
  against a local blobless clone: 356 blobs in one fetch, versus ~14 s of
  one-at-a-time lazy reads). If the prefetch fails the router still reads
  each blob lazily; any read failure leaves the graph unavailable and routes
  FULL.

## 7. Drift guards

[`tests/unit/governance/test_partial_routing.py`](../../tests/unit/governance/test_partial_routing.py)
asserts: each path-to-surface case; monotonicity on generated pairs of change
sets (synthetic and real tree); exhaustiveness (every tracked path classifies
deterministically, an unruled path is FULL); an under-reporting differential
(every `tests.*` import a discovery run actually performs is in the static
graph); that the real tree has no unresolved access form; that a new
unrecognized form fails with its file and line; that the closure of
`paths.py` equals an independent fixed-point computation; and the
no-live-execution and no-tier-override invariants.
[`tests/policy/governance/test_ci_test_routing.py`](../../tests/policy/governance/test_ci_test_routing.py)
asserts the workflow holds no path logic, trusts the base router, and keeps
the `test` job and required check unchanged.

## 8. Non-goals

No test-suite redesign; no change to DOCS semantics, the FAST definition, the
required-check names, or the parity jobs; no per-case selection; no nightly
tier, parallelization, or sandbox change; no review, policy, or benchmark
semantics; no reduction of security-adjacent coverage; no
[#183](https://github.com/amirbena/code-review-skill/issues/183) preflight
rework (preflight may consume `classify` later). Related:
[#533](https://github.com/amirbena/code-review-skill/issues/533),
[#624](https://github.com/amirbena/code-review-skill/issues/624). Parent:
[#395](https://github.com/amirbena/code-review-skill/issues/395).
