# Root `benchmark/` Relocation: Sentinel and Comprehensive Verification

Verification record for GitHub Issue
[#582](https://github.com/amirbena/code-review-skill/issues/582) (parent
[#577](https://github.com/amirbena/code-review-skill/issues/577)): that the
relocation of the benchmark corpus and prompt docs to the root
[`benchmark/`](../../../benchmark/README.md) tree (#580, #581) changed nothing the
Sentinel and Comprehensive scheduled lanes run, how their corpus is identified, or
how they publish.

A repository-development record, not packaged into either Skill archive. It is
deterministic evidence only: **no routine, baseline, or publication was
executed**, and no external configuration was read or changed.

- **Pre-move base:** `6e12c36` (the last commit before `437ca58` moved the tree).
- **Verified head:** `8233d21` (#581 rewire, on `main`).
- **Method:** the same probe (below) run against a detached checkout of each commit.

## Result

| Scope item | Result | Evidence |
| --- | --- | --- |
| Entrypoint resolves the new corpus and prompt-doc paths | Verified | `run_benchmark.DEFAULT_CORPUS_DIR` = `benchmark/corpus`; `benchmark_lane_run.ROUTINE_DOC` = `benchmark/cloud-routine-integration.md`; the entrypoint's `--corpus-dir` default is `rb.DEFAULT_CORPUS_DIR`. Both files exist. |
| Sentinel sees exactly the four root fixtures | Verified | `lane_corpus("sentinel", …)` returns 4 cases: `correctness-off-by-one-pagination`, `no-op-comment-and-rename`, `quality-duplicated-branch-logic`, `security-command-injection`, all from `benchmark/corpus`. |
| Comprehensive discovers each fixture exactly once | Verified | `discover_comprehensive_fixtures` returns 114 fixtures with 114 distinct ids on both base and head (a duplicate id would raise). |
| `corpus_id`, `membership_digest`, per-fixture digests unchanged | Verified | Sentinel `corpus_id` `39fa0e1a…2b97` and comprehensive `corpus_id` `e56ebc5a…e57c` are identical on base and head; `benchmark_result.membership_digest` over each lane's sorted case ids is identical (sentinel `96f4622d…7499`, comprehensive `33038764…ae83a`); 0 of 4 and 0 of 114 per-fixture digests differ. |
| `spec_sha256` stable | Verified | `dc3bebf4…5f76` on both; the prompt-block SHA-256 (`8f443b55…68c1`) is also identical, so the prompt-block bytes are unchanged. |
| Schedule manifest, cadence, publication boundary, sealed record unchanged | Verified | `git diff 6e12c36 8233d21` over `runtime_platform/benchmark/schedule/`, `publisher/`, `schemas/`, `publish_benchmark.py`, `benchmark_seal.py`, `benchmark_run_record.py`, `benchmark_schedule_manifest.py`, `benchmark_result.py`, and `.github/` is empty. |
| External Cloud Routine hardcodes a `docs/` benchmark path | **Unverifiable** | The Cloud Routine configuration lives in Claude's product surface, which this session cannot read. Nothing was guessed. See the contract comparison below. |
| External execution contract still matches the entrypoint | Verified against the issue's recorded baseline; live configuration not inspected | See below. |

`membership_digest` is the SHA-256 of the canonical JSON of the lane's case ids
(`benchmark_result.membership_digest`); it was recomputed from the base and head
case-id sets and is equal.

### Relocation diff scope

`git diff 6e12c36 8233d21` over the `runtime_platform/benchmark/scripts/` modules shows
only path-literal and docstring edits (nine files, 14 lines): corpus/index/doc path
constants moved to root `benchmark/`, and doc references updated. No argparse
definition, mode handling, exit-code path, seal, or publisher logic changed.
`runtime_platform/benchmark/benchmark-result-schema.md` changed only two relative
links. Fixture bytes are unchanged: the only edits under the moved tree are corpus
and benchmark READMEs/doc links, and the 34 fixture header comments that still
carry the pre-move path are frozen deliberately because their bytes feed
`corpus_id` and `fixture_digest` (see `FROZEN_FIXTURE_HEADERS` in
`tests/policy/benchmark/test_benchmark_root_migration.py`).

### External execution contract comparison

The baseline is the "Observed external Cloud Routine execution contract" recorded in
Issue #582 (copied from the Cloud Routine instructions). It is compared with the
repository's thin prompt spec
([`cloud-routine-integration.md` §9](../../../benchmark/cloud-routine-integration.md))
and the entrypoint's argument parser:

| Contract item | Recorded external instruction | Repository after relocation | Match |
| --- | --- | --- | --- |
| Checkout | fresh `amirbena/code-review-skill` at `main` | §9 step 1: fresh checkout at `<ref, default main>` | Yes |
| Entrypoint | `runtime_platform/benchmark/scripts/run_benchmark_routine.py` | file exists, same path on base and head | Yes |
| Sentinel args | `--mode sentinel --trigger scheduled --model-id claude-sonnet-5` | parses cleanly; `--model-id` is a free-form string | Yes |
| Comprehensive args | `--mode comprehensive --trigger scheduled --model-id claude-sonnet-5` | parses cleanly | Yes |
| Failure semantics | non-zero exit: stop, no success report, no silent retry, no GitHub post/push | §9 step 3 text identical (prompt-block SHA unchanged); exit-code paths not in the diff | Yes |
| `docs/` benchmark path in the instruction | none | the recorded instructions contain none, and neither does the §9 template | Yes |

Conclusion: **no Cloud Routine prompt or configuration change is required.** The
entrypoint's path, argument surface, defaults, and failure contract are unchanged;
the corpus default now resolves inside the repository checkout the routine already
creates, so the routine needs no path of its own. Because the live configuration
could not be inspected, the maintainer should confirm once, in the Routine's
product surface, that both instructions match the recorded text and contain no
pre-move benchmark path.

### Discrepancies

None found, so no follow-up issue was filed.

### Smoke-run rule (not executed)

If a post-merge smoke run is separately authorized, it must use exactly the two
commands recorded in the issue (`--mode sentinel` / `--mode comprehensive`, each
with `--trigger scheduled --model-id claude-sonnet-5`), and a non-zero or unsealed
run is a failure: stop, do not report success, do not retry silently, do not post
or push to GitHub.

## Reproduce

Run from a detached checkout of each commit, then compare the outputs. Imports and
file reads only; nothing is executed against a runtime.

```python
import hashlib, json
from pathlib import Path
from runtime_platform.benchmark.scripts import run_benchmark as rb
from runtime_platform.benchmark.scripts import benchmark_lane_run as lr
from runtime_platform.benchmark.scripts import benchmark_corpus_membership as m
from runtime_platform.benchmark.scripts import benchmark_schedule_manifest as sm
from runtime_platform.benchmark.scripts import benchmark_result as res

corpus = str(rb.DEFAULT_CORPUS_DIR)
for lane in ("sentinel", "comprehensive"):
    c = lr.lane_corpus(lane, corpus)
    print(lane, len(c.digests), c.corpus_id, res.membership_digest(sorted(c.digests)),
          json.dumps(c.digests, sort_keys=True))
ids = [f.case_id for f in m.discover_comprehensive_fixtures(Path(corpus))]
print(len(ids) == len(set(ids)))
print(lr.spec_sha256(sm.load_manifest()))
print(hashlib.sha256(lr._prompt_template().encode()).hexdigest())
```
