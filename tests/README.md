# tests/

The repository's own Python test suite and the **test-only** reference
models it exercises. None of this is packaged into either Skill archive or
loaded at Skill runtime — the packaged Skills are Markdown/YAML only. The
packaging boundary is enforced by
[`integration/test_packaging_runtime_boundary.py`](integration/test_packaging_runtime_boundary.py).

## Layout

| Directory | Contents |
|---|---|
| `reference/` | Test-only reference implementations mirroring packaged policy decision tables (`decision_semantics.py`, `review_context.py`, `jira_context.py`, `parallel_review.py`, `repository_instructions.py`, `runtime_validation.py`, `pr_checkout.py`, …). Imported by tests; never run directly. |
| `support/` | Shared test infrastructure: `pr_simulation.py` (local bare-repo PR harness) and `paths.py` (the one canonical `REPO_ROOT`). |
| `unit/` | Unit coverage for the `reference/` models, including `test_finding_identity_regression.py` — the data-driven finding-identity regression corpus (#61) — `test_rereview_regression_fixtures.py` — the data-driven stateful delta re-review regression corpus (#66) of paired before/after review histories — and `test_architectural_placement_fixtures.py` — paired local-only vs. bounded context-expansion outcomes for architecturally misplaced behavior (#153) — each with its induced-regression / mutation check. `test_benchmark_corpus.py` validates the `docs/benchmark/corpus/` fixtures (#51) through the `benchmark_fixture.py` reference validator. `test_benchmark_runner.py` drives the `benchmark_runner.py` reference runner (#52) over the corpus and asserts per-case isolation, cleanup, and byte-for-byte preservation of a deliberately dirty source repository. `test_benchmark_report.py` drives the `benchmark_report.py` reference report (#53) — the run-to-run baseline comparison — and asserts a seeded regression is classified distinctly from an improvement and that output is byte-identical for identical inputs. `test_benchmark_match.py` drives the `benchmark_match.py` reference matcher (#54) — the expected-vs-produced match relation — and asserts every `match-criteria.md` §8 worked example classifies as documented. |
| `integration/` | Coverage that shells out to real Git or builds the packaged archives. |
| `policy/` | Prose / documentation-contract checks over `AGENTS.md`, `policies/`, `shared/policies/`, and each Skill's files. |
| `repository/` | Repository-hygiene checks (e.g. `.gitignore`). |

Genuine developer scripts (packaging, metadata validation) live in
[`../scripts/`](../scripts/), not here.

## Running

From the repository root:

```bash
python3 -m unittest discover -s tests -t .
```

`python3 -m unittest discover` from the repository root also works. Run one
module with, e.g., `python3 -m unittest tests.unit.test_decision_semantics`.
Individual test files are not meant to be executed as scripts
(`python3 tests/unit/…`) — they rely on `tests` being importable as a
package, which `python3 -m unittest` provides.
