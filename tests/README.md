# tests/

The repository's own Python test suite and the **test-only** reference
models it exercises. None of this is packaged into either Skill archive or
loaded at Skill runtime — the packaged Skills are Markdown/YAML only. The
packaging boundary is enforced by the guard tests under
[`integration/packaging/`](integration/packaging/) (see its
[package docstring](integration/packaging/__init__.py)).

## Layout

Each of `unit/`, `policy/`, and `reference/` is split into capability
sub-packages so a contributor can find "the benchmark tests" or "the
release tests" without scanning dozens of flat filenames. A sub-package
exists only where the repository actually has that many modules for it —
none of the four top-level kinds (`unit`, `policy`, `reference`,
`integration`) is itself renamed.

| Directory | Contents |
|---|---|
| `reference/benchmark/` | Test-only reference implementations of the benchmark pipeline: fixture validation, the run-to-run report, the expected-vs-produced matcher, and the missed/incorrect, severity-accuracy, and duplicate-noise metrics built on it. |
| `reference/review/` | Test-only reference implementations mirroring packaged review policy decision tables (`decision_semantics.py`, `review_context.py`, `jira_context.py`, `parallel_review.py`, `repository_instructions.py`, `runtime_validation.py`, `pr_checkout.py`, …). Imported by tests; never run directly. |
| `support/` | Shared test infrastructure: `pr_simulation.py` (local bare-repo PR harness) and `paths.py` (the one canonical `REPO_ROOT`). |
| `unit/benchmark/` | Unit coverage for the `reference/benchmark/` models: `test_benchmark_corpus.py` validates the `docs/benchmark/corpus/` fixtures (#51) through the `benchmark_fixture.py` reference validator; `test_benchmark_runner.py` drives the reference runner (#52) over the corpus and asserts per-case isolation, cleanup, and byte-for-byte preservation of a deliberately dirty source repository; `test_benchmark_report.py` drives the reference report (#53) and asserts a seeded regression is classified distinctly from an improvement and that output is byte-identical for identical inputs; `test_benchmark_match.py` drives the reference matcher (#54) and asserts every `match-criteria.md` §8 worked example classifies as documented; `test_benchmark_metrics.py` drives the reference metric (#55) and asserts every `missed-and-incorrect-findings.md` §8 worked example counts as documented; `test_benchmark_severity.py` drives the reference metric (#56) and asserts every `severity-accuracy.md` §7 worked example classifies as documented; `test_benchmark_dupes.py` drives the reference metric (#57) and asserts every `duplicate-noise.md` §7 worked example clusters as documented. |
| `unit/governance/` | Repository automation and hygiene: issue-claim reconciliation, issue-label sync, PR-description length, and the repository-wide Markdown-link validator. |
| `unit/release/` | Coverage for `scripts/release_worthiness.py`, split along its path-classification, CHANGELOG coverage, Unreleased roll, main()/`$GITHUB_OUTPUT` contract, pure SemVer/ref helpers, and preflight/verify responsibilities (`_shared.py` holds the fake Git/GitHub runner and CHANGELOG fixtures they share), plus `test_changelog_generation.py` and `test_release_intent.py`. |
| `unit/review/` | Unit coverage for the `reference/review/` models, including `test_finding_identity_regression.py` — the data-driven finding-identity regression corpus (#61) — `test_rereview_regression_fixtures.py` — the data-driven stateful delta re-review regression corpus (#66) of paired before/after review histories — and `test_architectural_placement_fixtures.py` — paired local-only vs. bounded context-expansion outcomes for architecturally misplaced behavior (#153) — each with its induced-regression / mutation check. |
| `integration/github/` | Coverage that shells out to real Git for the GitHub PR checkout lifecycle. |
| `integration/packaging/` | End-to-end packaging-boundary guard: manifest/path-safety, script parity, hidden-runtime-dependency + disclaimer prose, and the built local/GitHub archive contents (`_shared.py` holds the shared paths, manifest helpers, and the reference-module list). |
| `integration/release/` | Coverage that builds the packaged archives to exercise the release-worthiness PR boundary. |
| `policy/benchmark/` | Prose / documentation-contract checks for the benchmark docs (`docs/benchmark/**`). |
| `policy/governance/` | Prose / documentation-contract checks over `AGENTS.md`, `policies/`, entrypoint guards, forbidden terms, and PR-description enforcement. |
| `policy/release/` | Prose / documentation-contract checks for CHANGELOG/SemVer guidance and the release-worthiness workflow. |
| `policy/review/` | Prose / documentation-contract checks over `shared/policies/`, `shared/templates/`, and each Skill's review-related files. |
| `repository/` | Repository-hygiene checks (e.g. `.gitignore`). Unchanged by the #217 reorganization. |

Genuine developer scripts (packaging, metadata validation) live in
[`../scripts/`](../scripts/), not here.

## Running

From the repository root:

```bash
python3 -m unittest discover -s tests -t .
```

`python3 -m unittest discover` from the repository root also works. Run one
module with, e.g., `python3 -m unittest tests.unit.review.test_decision_semantics`.
Individual test files are not meant to be executed as scripts
(`python3 tests/unit/…`) — they rely on `tests` being importable as a
package, which `python3 -m unittest` provides.
