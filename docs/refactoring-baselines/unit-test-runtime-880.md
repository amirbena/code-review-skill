# Unit test runtime breakdown

Evidence record for [#880](https://github.com/amirbena/code-review-skill/issues/880)
(related: [#533](https://github.com/amirbena/code-review-skill/issues/533)). Repository-development
record, not packaged into any Skill archive.

One macOS machine, Python 3.14.6, pytest 9.1.1 as a timing harness (CI itself uses
`unittest discover`), one sample per row. Compare shares, not seconds, with CI. The
`claude` CLI was on `PATH` for these runs, which is what made the live tests execute.

## Where the time went (`tests/unit`, 256.4 s, 2,091 passed)

Four tests account for about 144 s (56%); the other ~2,090 tests share the rest.

| Test | Wall s | Cause |
| --- | ---: | --- |
| `test_run_concurrency_experiment.py::FailureTest::test_termination_stops_children_and_seals_partial_evidence_as_terminated` | 60.7 | Waits out the termination grace periods (31 s when run alone, twice; failed once at the test's own 60 s limit in the full run) |
| `test_blocking_verdict_corpus.py::LiveBlockingVerdictTests::test_real_run_never_renders_a_clean_verdict_for_a_blocking_defect` | 42.9 (+5.7 setup) | Real reviewer/model calls, two cases; failed with the live model output |
| `test_production_adapter_e2e.py::ProductionAdapterEndToEndTests::test_real_case_executes_through_the_real_runtime` | 21.1 | Real reviewer/model call |
| `test_benchmark_corpus_patch_applies.py::CorpusPatchAppliesTest::test_every_patch_applies_to_its_own_base` | 15.3 | One `git apply` per patch-bearing corpus fixture |

Everything else is at or below about 5 s per test; most of it is subprocess and
throwaway-Git-repository setup in the benchmark, release and sandbox modules.

The ">7 minutes" in the issue was not reproduced (4 min 16 s here). The live tests are
the variable part: they run only where the CLI is installed and authenticated, and each
allows a 600 s timeout.

## Change

The two live classes (`LiveRuntimeTestCase` subclasses) are dropped from discovery by a
module-level `load_tests` unless `BENCHMARK_RUN_LIVE=1` or `BENCHMARK_REQUIRE_RUNTIME=1`,
and their `setUpClass` skips without probing the CLI. A default run never invokes a model.
Stub-based tests are unchanged. CI routing and required checks are untouched.

Expected saving: about 70 s of the 256 s above (the two live tests plus setup). This is
derived from the table, not a measured after-change `tests/unit` run.

## Not addressed

The termination test and the patch-applies scan remain the slowest deterministic tests
(about 76 s together). They are out of scope here and are candidates for a follow-up.
