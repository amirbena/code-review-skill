# Scale progressive-loading proof

Repository-development record for issue
[#447](https://github.com/amirbena/code-review-skill/issues/447), child of
[#403](https://github.com/amirbena/code-review-skill/issues/403), per
[#412](specialist-depth-continuation-checkpoint.md)'s decision to continue
the #408→#410→#411 pattern for exactly one more capability, `scale`. Like
the rest of [`./`](README.md), this is a repository-development doc:
**not** packaged into either Skill archive, and no packaged Skill
resource depends on it.

#447 made `scale`'s loading conditional on its declared activation
predicate and proved the fail-closed contract at the text/manifest level
([`tests/policy/review/test_scale_447.py`](../../tests/policy/review/test_scale_447.py)).
#408 recorded the pre-extraction baseline generically, by capability, for
every capability including `scale`
([`capability-loading-baseline.md`](capability-loading-baseline.md) §per-capability
table). This document is `scale`'s own proof, mirroring
[`specialist-depth-progressive-loading-proof.md`](specialist-depth-progressive-loading-proof.md)'s
(#411) shape: one static measurement and one live run of the real
reviewer runtime, both reproducible from the documented commands below,
reusing every existing corpus/evaluator rather than introducing a new
one (issue #451).

## 1. Scope and non-goals

Per #447/#451:

- Proves `scale`'s activation predicate is enforced and fail-closed at
  the text/manifest level (§tests, not restated here — see
  `tests/policy/review/test_scale_447.py`).
- Measures the static instruction-surface reduction an "unnecessary"
  review no longer has to apply once `scale`'s loading is conditional.
- Proves, with live-run evidence (#451): an ordinary review where
  `scale` is unnecessary sees unchanged findings; a review where an
  ambiguous trigger forces fail-closed loading produces the required,
  non-blocking finding; and behavior otherwise matches #408's baseline.
- Reuses `repository-intelligence`'s existing corpus (#129) for the
  "not needed" and "must activate" activation-correctness roles, and adds
  exactly one net-new fixture
  ([`docs/benchmark/corpus/scale-progressive-loading-proof/`](../benchmark/corpus/scale-progressive-loading-proof/README.md))
  for the one required shape neither existing corpus covers: an ambiguous
  trigger-evaluation that must still load (fail-closed) rather than skip.
- Does **not** rewrite any existing *pinned* benchmark expectation (§4
  below documents, but does not alter, a pre-existing location-convention
  mismatch on one reused fixture). Does **not** rewrite this issue's own
  not-yet-pinned fixture's pinned design invariants (severity stays
  `[P1, P2]`, never widened to include the observed `P0` — see §5); only
  its `defect_kind` wording tolerance was widened, following #411 §5's
  own precedent for recalibrating a not-yet-pinned fixture to observed
  reviewer behavior — a different class of fix from the two reused
  fixtures' patch-corruption correction in §3. Does
  **not** attempt a general router extraction, and does **not** change
  `specialist-depth`'s `requires: [... scale]` dependency or any other
  capability's loading behavior (`tests/policy/review/test_scale_447.py`,
  `ScopeBoundaryTests`, verifies this directly).
- Static measurement executed at commit `3b1cfba` +worktree (2026-09-17).
  Behavioral measurement executed at commit `384f88f` +worktree
  (2026-09-18), `claude` CLI `2.1.272`.

## 2. Static surface reduction

Reproducible with:

```bash
python3 scripts/capability_architecture/scale_progressive_loading_proof.py static
```

Reuses `capability_loading_baseline.py`'s own static-surface measurement
unchanged (`measure_static_surface()` — see
[`capability-loading-baseline.md`](capability-loading-baseline.md) §2 for
methodology) and isolates `scale`'s own attributed word count: the
surface an "unnecessary" review no longer has to apply once loading is
actually conditional.

| Adapter | Total words (`scale` loaded) | `scale` words | Total words (not needed) | Reduction |
| --- | ---: | ---: | ---: | ---: |
| `local-code-review` | 83,766 | 3,878 | 79,888 | 4.63% |
| `github-pr-review` | 112,954 | 3,878 | 109,076 | 3.43% |

These totals reflect a live re-measurement at the current commit (which
now includes both this issue's own "Conditional loading: fail-closed"
prose additions to `repository-expansion.md`/`large-pr-partitioning.md`
and every other change landed since #408's original snapshot), not the
stale #408 baseline figure. `scale` is a much smaller attributed slice
than `specialist-depth` was (3,878 words here vs. `specialist-depth`'s
9,379 at its own #411 measurement) — consistent with #447's own framing
of `scale` as a genuinely different, smaller activation shape, not a
repeat of the first extraction.

As with #411 §2: `scripts/packaging/package-manifest.json` still ships
`scale`'s files unconditionally — packaging membership is unaffected by
this issue. The "reduction" is the instruction surface a review's own
reasoning applies once loading is actually conditional on the activation
predicate, not a change to what the packaged archive contains.

## 3. Regression stability vs. #408's baseline (required cases 1/2, matched)

Reproducible with:

```bash
python3 scripts/capability_architecture/scale_progressive_loading_proof.py behavioral
```

Re-runs #408's own 4-case corpus (`docs/benchmark/corpus/*.yaml`) through
the same `ProductionReviewerAdapter` + `benchmark_metrics.compute_run_metrics`
#408 used, live, at the commit above:

| Case | False negatives | False positives | vs. #408 baseline |
| --- | ---: | ---: | --- |
| `correctness-off-by-one-pagination` | 0 | 0 | matches |
| `no-op-comment-and-rename` | 0 | 0 | matches |
| `quality-duplicated-branch-logic` | 0 | 0 | matches |
| `security-command-injection` | 0 | 0 | matches |
| **Aggregate** | **0** | **0** | **identical to #408's recorded 0 FN / 0 FP** |

Behavior on the reachable regression set is unchanged.

### Investigation: the earlier hang, and a genuine patch-corruption defect found along the way (#451 Scope #1)

The earlier attempt (recorded in #447/PR #448) left the nested reviewer
CLI invocation running with no output for several minutes and was
stopped. Re-attempting it in this issue's session did **not** reproduce
a hang: the full 7-case run (4-case regression set + the two reused
`repository-intelligence` cases + this issue's net-new ambiguous
fixture) completed in both an initial and a re-run pass in a few
minutes, well inside the adapter's existing per-case timeout
(`DEFAULT_TIMEOUT_SECONDS = 300.0`,
[`benchmark_review_adapter.py`](../../scripts/benchmark/benchmark_review_adapter.py)).
A short probe invocation of the `claude` CLI with this session's own
`CLAUDECODE=1`/`CLAUDE_CODE_*` environment inherited unchanged (exactly
as `ProductionReviewerAdapter` does — see `self.env = dict(os.environ)`)
also completed immediately, ruling out nested-session environment
inheritance as a cause. This is consistent with #447's own framing:
"local to that attempt", not a distinct, reusable runtime/tooling
defect — no separate issue is opened per Scope #1/#4, since no reusable
defect was found.

What the first completed run *did* surface, independent of the earlier
hang, is a genuine pre-existing defect in the two reused
`repository-intelligence` fixtures: both
[`repo-intel-python-control-compatible-caller-no-finding.yaml`](../benchmark/corpus/repository-intelligence/repo-intel-python-control-compatible-caller-no-finding.yaml)
and
[`repo-intel-python-call-site-caller-null-deref.yaml`](../benchmark/corpus/repository-intelligence/repo-intel-python-call-site-caller-null-deref.yaml)
carried a corrupt patch hunk header (`@@ -1,3 +1,3 @@` against a 2-line
base; `@@ -1,10 +1,6 @@` against a 9-line/5-line base respectively) —
the same class of bug #411 §4 found and fixed in 1 fixture and flagged
17 more of, generically, as a deferred follow-up (no test before this
issue actually ran `git apply` against these two specific fixtures).
Both live runs errored with `patch-did-not-apply` as a direct result.
Fixed here as the same minimal, mechanical hunk-header correction #411
§4 applied (`@@ -1,2 +1,2 @@` and `@@ -1,9 +1,5 @@` respectively — no
change to either fixture's expected findings, decision, or rationale);
re-running confirms both now apply and execute (§4). This is local to
these two fixtures, not scale-specific and not a #451-introduced defect;
the broader sweep for the remaining, already-flagged corpus-wide
instances of this bug class stays #411 §4's deferred follow-up, not
absorbed into this issue.

## 4. Activation correctness (required cases 1/2)

Reuses `repository-intelligence`'s control case ("not needed") and
call-site positive case ("must activate") by id, live, after the
patch-header fix above:

| Case | Role | Did the right thing happen? |
| --- | --- | --- |
| `repo-intel-python-control-compatible-caller-no-finding` | not needed | Yes — 0 false negatives, 0 false positives. No finding produced for the compatible caller, matching the pinned expectation exactly. |
| `repo-intel-python-call-site-caller-null-deref` | must activate | Yes, in substance — the live reviewer correctly identified the exact defect the fixture pins (`get_user` dropping its `UserNotFound` contract, crashing `charge_user` on `user.account_id`), including the same `null-dereference` `defect_kind`. It is nonetheless scored 1 false negative / 1 false positive by the strict matcher. |

The one scored mismatch is a **location-convention** difference, not a
substantive miss: the fixture's expected location is cross-file, pinned
at the caller (`app/billing/charge.py`, symbol `charge_user`, anchor
`user.account_id`) — where the crash occurs. The live reviewer instead
located its finding at the root cause (`app/users/lookup.py:4-5`, the
changed function itself) with a claim that explicitly names and quotes
`app/billing/charge.py`'s crash site in its text. `location_match`
(`tests/reference/benchmark/benchmark_match.py`) has no tolerance for
"correct claim, different location convention" — it scores this as
`UNRELATED` even though `defect_match` on the same pair is
`CORRESPONDS`. This is a property of this *reused*, already-pinned
fixture's location strictness, not a regression `scale`'s conditional
loading introduced, and per #451's Non-Goals this issue does not rewrite
that existing pinned expectation to force a pass — the same restraint
#411 §4 documented for its own two reused fixtures' `defect_kind`-wording
mismatches. Reconciling root-cause-vs-call-site location convention for
this fixture is left as a follow-up against #129's corpus.

## 5. Ambiguous predicate evaluation forces fail-closed load (required case 3)

This issue's one net-new fixture:
[`scale-progressive-loading-proof-ambiguous-public-export-forces-fail-closed-expansion.yaml`](../benchmark/corpus/scale-progressive-loading-proof/scale-progressive-loading-proof-ambiguous-public-export-forces-fail-closed-expansion.yaml).
`apply_discount`'s rounding direction flips; whether it has an external
caller is not resolvable from the diff alone (it is merely re-exported
through `__all__`), exercising #447's fail-closed clause directly. Live
result, across both runs:

| Run | Produced finding | Matched required entry? |
| --- | --- | --- |
| Initial | `incorrect-rounding-direction`, P0 | No — the fixture's `defect_kind` was pinned to `incorrect-rounding-behavior`/`broken-invariant` only; the live reviewer's real judgment used a third, reasonable but different slug. |
| After recalibration | `broken-invariant`, P0 | **Yes** — 0 false negatives, 0 false positives (`defect_kind` now includes `incorrect-rounding-direction` as a third accepted `alternatives` entry). |

`defect_kind` wording was widened the same way #411 §5 widened its own
net-new fixture's accepted range — this issue's own, not-yet-pinned
fixture, so recalibrating it to observed reviewer behavior is expected
corpus-authoring iteration, not the "rewrite a pinned expectation" #451's
Non-Goals forbid. **Severity was deliberately left unwidened**: both live
runs produced `P0`, one step more confident than the fixture's pinned
`[P1, P2]` hedge (`AmbiguousCaseShapeTests.test_carries_exactly_one_required_hedged_finding`,
[`tests/unit/benchmark/test_scale_progressive_loading_proof_corpus.py`](../../tests/unit/benchmark/test_scale_progressive_loading_proof_corpus.py),
still asserts `{"P1", "P2"}` and `can_block is False` unchanged). Per
this fixture's own design intent (§ comments in the fixture file and its
`AmbiguousCaseShapeTests` docstring): a `P0` result "would read as
confident, evidenced escalation the ambiguous trigger evidence does not
support," which is exactly the distinction this fixture exists to police
— so the observed `P0` is recorded here as a live-run observation, not
silently absorbed by loosening the pinned invariant. What both runs
confirm regardless of the severity variance: ambiguity produces a
finding at all (never silence), and that finding's evidence is the
ring-1 expansion result (`app/checkout/cart.py`'s minimum-charge
assertion), never the ambiguity itself — the fail-closed behavior #447
declared and this issue proves live.

## 6. Reproducing / re-measuring

```bash
python3 scripts/capability_architecture/scale_progressive_loading_proof.py all \
  --out docs/capability-architecture/scale-progressive-loading-proof.json
```

`all` runs both halves. `behavioral` requires the `claude` CLI on `PATH`
(or `BENCHMARK_REVIEW_CLI` set), per `run_benchmark.py`'s own
runtime-availability check, and its exit code is fail-closed on exactly
the two cases this issue owns outright: the regression set (§3) and this
issue's own net-new ambiguous-fail-closed fixture (§5) — both currently
0 FN / 0 FP, so the script exits `0`. A mismatch on either fails the
run. A mismatch on the two *reused* `repository-intelligence` fixtures
(§4's known, documented, pre-existing location-convention matcher
mismatch on one of the two) is reported (to stderr and in the JSON
output) but never fails the run, mirroring #411 §6's precedent for
`specialist-depth-composition`'s reused cases.

## Status and canonical home

This document and
[`scripts/capability_architecture/scale_progressive_loading_proof.py`](../../scripts/capability_architecture/scale_progressive_loading_proof.py)
are the authoritative proof for #447, completed by #451. Neither is
packaged into either Skill archive, and no runtime behavior, packaging,
or loading changed to produce it beyond the two incidental hunk-header
fixes in §3 and the one `defect_kind`-widening recalibration in §5 —
none of which alter what is packaged or how loading behaves, matching
#408's and #411's own precedent.
This, together with
[`tests/policy/review/test_scale_447.py`](../../tests/policy/review/test_scale_447.py),
is the evidence #403 is scoped to cite for `scale` as the second
capability proving the pattern generalizes with live-run evidence, not
just a static estimate.
