# tests/

The repository's own Python test suite. None of it is packaged into a Skill
archive or loaded at Skill runtime — the packaged Skills are Markdown and
JSON only.

The v2 prose-pinning policy tests and the test-only shadow models of v2
review policy were retired with the v2 architecture (#849); a test here
either runs real code or guards a structural contract of the repository.

## Layout

| Directory | Contents |
|---|---|
| `unit/benchmark/` | Unit coverage for the benchmark harness in [`runtime_platform/benchmark/`](../runtime_platform/benchmark/README.md): corpus validation, runner, matcher and metrics, history/baseline, the publication CLI, the production adapter, and the blocking-verdict corpus check. |
| `unit/governance/` | Repository automation and hygiene: issue-claim reconciliation, issue-label sync, PR-description length and structure, the Markdown-link validator, and the CI test router (`test_ci_test_route.py`, `test_change_aware_routing.py`, `test_partial_routing.py`). |
| `unit/release/` | Coverage for `scripts/release/`: path classification, CHANGELOG coverage and generation, release intent, preflight and finalization. |
| `unit/review/core/` | Contract tests over the v3 Skills under `skills/`: that each `SKILL.md`, its rule files and its templates exist, link correctly and keep the structural contract the ADR sets. |
| `unit/package_domain/` | The packaging-domain rules in `scripts/packaging/package_domain/`: tree building, adaptation, validation, version stamping. |
| `unit/skill_metadata/` | The Skill frontmatter and link validator in `scripts/skill_metadata/`. |
| `unit/sandbox/`, `integration/sandbox/` | The sandbox backend in `scripts/sandbox/` and its adversarial-containment suite. |
| `unit/github_integration/` | The authenticated GitHub call boundary and write allow-list in `scripts/github_integration/`. |
| `unit/security/` | The threat-model validator in `scripts/security/`. |
| `integration/github/` | `review-publish-github` against an in-memory PR that enforces what GitHub enforces. |
| `integration/packaging/` | The package manifest's path safety and the parity of the shell and PowerShell packaging scripts. |
| `integration/release/` | Coverage that exercises the release-worthiness PR boundary against real Git. |
| `policy/benchmark/`, `policy/governance/`, `policy/release/` | Structural guards over workflows, routing and benchmark wiring (not prose): the CI test routing contract, the PR-description and release workflows, the benchmark publish workflow and its no-write guarantee, the benchmark root layout, and the instruction-routing structure. |
| `repository/` | Repository-hygiene checks (`.gitignore`, `scripts/` staying subsystem-owned). |
| `support/` | Shared test infrastructure: `paths.py` (the one canonical `REPO_ROOT`), `git_repo.py` (`isolate_git_config()` for modules that build throwaway Git repositories), `pr_publication_fake.py`, `benchmark_runtime.py` (the shared gate for tests that need the real benchmark review runtime; live tests skip unless `BENCHMARK_RUN_LIVE=1`; `BENCHMARK_REQUIRE_RUNTIME=1` also opts in and makes a missing runtime an error instead of a skip), `corpus_hygiene.py`, and the benchmark publisher fakes. |

Genuine developer scripts (packaging, metadata validation) live in
[`../scripts/`](../scripts/), not here.

## Running

From the repository root:

```bash
python3 -m unittest discover -s tests -t .
```

`python3 -m unittest discover` from the repository root also works. Run one
module with, e.g., `python3 -m unittest tests.unit.review.core.test_review_core_contract`.
Individual test files are not meant to be executed as scripts
(`python3 tests/unit/…`) — they rely on `tests` being importable as a
package, which `python3 -m unittest` provides.

To re-check that git-using tests do not depend on the host's git configuration,
run them with `HOME` pointed at an empty directory and `GIT_CONFIG_GLOBAL` set to
a config enabling `commit.gpgsign` with a failing `gpg.program`, a failing
`core.hooksPath` hook, and a non-`main` `init.defaultBranch`; none should fail.
