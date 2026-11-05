# Policy-Loading Benchmark

Issues [#806](https://github.com/amirbena/code-review-skill/issues/806) and
[#808](https://github.com/amirbena/code-review-skill/issues/808). A
review that did not open the required policies must not render a complete
verdict. These fixtures hold recorded tool traces plus the labels the
report rendered; `check_policy_reads` in
[`benchmark_blocking_verdict.py`](../../../runtime_platform/benchmark/reference/benchmark_blocking_verdict.py)
compares them. Tests:
[`test_policy_read_verification.py`](../../../tests/unit/benchmark/test_policy_read_verification.py).
They are not `benchmark-case/v2` fixtures: there is no patch or finding.

| Fixture | Shows |
| --- | --- |
| `v1.80.2-skipped-policies.json` | A v1.80.2 review that read only the first 60 lines of `severity.md` and rendered `CHANGES REQUIRED`. Detected. |
| `complete-review-confirmed-reads.json` | Synthetic complete review: every unconditional file read in full. Passes. |
| `declared-command-runtime-validation-fired.json` | #816: repository declares a test command, the `runtime-validation.md` predicate fires, the file is read in full before command selection. Passes. |
| `no-command-runtime-validation-not-fired.json` | #816: no declared command, nothing fires, the file is never opened and the explicit no-command `Validation` entry still renders. Passes. |

The first fixture keeps only the skill-touching calls (skill directory
replaced by `$SKILL_DIR`) and the report's labels. The source session was
deleted afterwards, so its commands were restored from the earlier replay
of that session rather than re-extracted.

## Read states

- `confirmed`: a `Read` without `limit`/`offset`, or a `cat` naming the
  file with no truncating pipe or redirect.
- `unverifiable`: the file is named but the trace cannot show it was read
  in full (`head`, `sed -n`, `| head -c`, a redirect, a limited `Read`), or
  it is only reachable through a glob or a bare name after `cd`.
- `missing`: no read-style call names the file. `wc`, `ls` and `grep` are
  not reads.

Unless every required file is `confirmed`, Result and Decision must both
render `REVIEW INCOMPLETE` and a `Coverage:` value must not read
complete. Required files are derived from the unconditional part of
`SKILL.md` section 2, so a conditional file that did not fire is never
required and a new unconditional file is picked up automatically. A fixture
may declare `fired_conditional` (Issue
[#816](https://github.com/amirbena/code-review-skill/issues/816)); those
files are required like unconditional ones. The fixture author asserts the list; it is not derived from the trace, so the check covers the read given the claim, not whether the claim is right. A fired predicate with no full read before a definitive verdict is a violation. Fire rate of the
`runtime-validation.md` predicate over the two #816 fixtures: 1 of 2. The four
sentinel cases carry a patch and no repository instruction sources, so the
predicate does not fire on them by the instruction-source clause (0 of 4, by
inspection, not a live-run measurement).

A definitive verdict (`REVIEW CLEAN` or `CHANGES REQUIRED`) with no
`Coverage:` value is also a violation, because the runbooks treat a missing
line as incomplete. A test also requires every shared policy a runbook
applies to be named in its Skill's section 2, so the inventory the
checkpoint and this checker read cannot silently omit one (#808 found
`verdict-consistency.md` missing).

## Resumed reads

Issue [#812](https://github.com/amirbena/code-review-skill/issues/812).
[`review-stopping-criteria.md`](../../../shared/policies/review-stopping-criteria.md),
"Bounded, resumable policy loading", owns the procedure: bounded groups, a
per-file line count compared with the lines received, resumption from the last
verified line, and `REVIEW INCOMPLETE` only when recovery fails.
[`benchmark_policy_loading.py`](../../../runtime_platform/benchmark/reference/benchmark_policy_loading.py)
models it and
[`test_policy_loading_resumption.py`](../../../tests/unit/benchmark/test_policy_loading_resumption.py)
covers truncation, partial reads, recovery, unrecoverable failure and files
without a trailing newline.

`check_policy_reads` is called only by the fixture tests; nothing in the live
benchmark path uses it. It still classes a ranged read as `unverifiable`
because a recorded trace holds tool inputs, not delivered lengths, so a
resumed review replayed through it is flagged rather than passed (pinned by
a test). Confirming one needs delivered-length evidence in the trace, which
no consumer needs yet.

### Evidence status

- **Simulated:** every recovery path above runs against a fake reader that
  truncates, cuts off or over-delivers. This proves the procedure, not any
  runtime's behavior.
- **Observed once, 2026-10-26, Claude Code desktop:** a 39 KB `Bash` result
  was not delivered inline; the harness replaced it with a "persisted-output"
  notice, the first 2 KB and a file path. A `Read` of a 2,500-line file
  returned every line, and numbered an empty row after the last newline
  (hence the line definition in the policy).
- **Not observed:** a silent truncation. No runtime has yet been seen to cut a
  `Read` short without saying so, and no complete review has been run through
  a runtime that does. Recovery on a truncating runtime therefore rests on
  the simulation and on the per-file comparison, not on a recorded run.

## Limitations

- A trace shows reads, not that a policy was applied.
- Detection works on command text. A read built indirectly (a variable, a
  script, reading a redirected dump) is `unverifiable`, so a valid review
  that loaded policies that way is flagged rather than passed.
- It runs in tests and over recorded traces. It cannot stop a live user
  run; the runbooks' checkpoint and step 10b remain prompt-level there.
- **Live runtime enforcement is not achieved.** Nothing in this repository
  can block a live review from rendering a definitive verdict after skipping
  policies: that would need a runtime hook or interception, which is out of
  scope. In a normal run the invariant stays prompt-level (the
  mandatory-loading checkpoint and step 10b). The checker and the inventory
  test detect failures in tests, over recorded traces and in benchmarks only.
- Live-run use is optional, behind the existing `BENCHMARK_REQUIRE_RUNTIME`
  gate, and is not required for every PR.
