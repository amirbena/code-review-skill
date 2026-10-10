# Code Hygiene Benchmark Corpus

Repository-development artifact for GitHub Issue
[#677](https://github.com/amirbena/code-review-skill/issues/677), parent
[#675](https://github.com/amirbena/code-review-skill/issues/675). A focused
sub-corpus of [`benchmark-case/v2`](../../../runtime_platform/benchmark/fixture-format.md)
fixtures proving the delivered behavior of
[`../../../shared/policies/code-hygiene.md`](../../../shared/policies/code-hygiene.md)
(#676): hygiene is reported when it is real, left alone when it is legitimate,
and never exceeds its severity bounds. It validates the policy and never
redefines it.

Every case is a self-contained inline `patch` plus `base`, so the corpus runs
without network access. Like the rest of [`../`](../README.md) this is **not**
packaged into either Skill archive; it is consumed only by this repository's
test suite and benchmark harness, through the single reference validator
[`benchmark_fixture.py`](../../../runtime_platform/benchmark/reference/benchmark_fixture.py)
(never a second one). The existing `no-op-comment-and-rename` case is
unchanged.

## Selection principle

One case per shape the issue lists, each isolating that shape so a regression
is unambiguous. The harness matches **findings**, and the policy's default
tier is a severity-less *observation* outside the finding set, so the cases
encode the tiers as follows:

- **Default tier (flagged shapes)** — `decision: clean`, `exhaustive`, empty
  findings. A reviewer's observation is correct and invisible to the matcher;
  a finding of *any* severity is an unexpected finding, which proves hygiene
  alone never becomes a finding or changes the decision.
- **Controls** — the same empty exhaustive expectation. Any finding is a false
  positive, so the control cases are the false-positive measurement: the
  existing metrics report unexpected findings on them next to detection on the
  P2 cases.
- **P2 tier** — one required finding, severity `P2` only (never P0/P1), only
  where the delta itself carries causal maintainability evidence.

Observation detection is not machine-measured here: making it measurable would
need matcher or format changes, which are out of scope. Raising the default
tier to an optional or required finding would contradict the policy.

## Cases

| File | Shape | A correct review must… | Decision |
|---|---|---|---|
| [`code-hygiene-bare-issue-reference-observation.yaml`](code-hygiene-bare-issue-reference-observation.yaml) | bare `#482` comment | at most observe; no finding | `clean` |
| [`code-hygiene-obsolete-tracker-comment-observation.yaml`](code-hygiene-obsolete-tracker-comment-observation.yaml) | workaround comment left after its code is removed | at most observe; no finding | `clean` |
| [`code-hygiene-todo-ticket-without-content-observation.yaml`](code-hygiene-todo-ticket-without-content-observation.yaml) | `TODO(PROJ-456)` with no content | at most observe; no finding | `clean` |
| [`code-hygiene-poor-variable-name-observation.yaml`](code-hygiene-poor-variable-name-observation.yaml) | `tmp` holding per-line totals | at most observe `line_totals`; no finding | `clean` |
| [`code-hygiene-control-active-workaround-reference.yaml`](code-hygiene-control-active-workaround-reference.yaml) | reference documenting an active workaround | report nothing | `clean` |
| [`code-hygiene-control-known-limitation-reference.yaml`](code-hygiene-control-known-limitation-reference.yaml) | reference documenting a known limitation | report nothing | `clean` |
| [`code-hygiene-control-external-contract-and-compat-reference.yaml`](code-hygiene-control-external-contract-and-compat-reference.yaml) | external contract and compatibility references | report nothing | `clean` |
| [`code-hygiene-control-conventional-loop-and-comprehension-names.yaml`](code-hygiene-control-conventional-loop-and-comprehension-names.yaml) | `i`, `j`, `x`, `y` | report nothing | `clean` |
| [`code-hygiene-control-legitimate-short-and-domain-names.yaml`](code-hygiene-control-legitimate-short-and-domain-names.yaml) | `lat`, `lon`, `dlat`, `n` | report nothing | `clean` |
| [`code-hygiene-p2-misleading-name-with-causal-evidence.yaml`](code-hygiene-p2-misleading-name-with-causal-evidence.yaml) | `delay` seconds vs milliseconds at neighbouring call sites | report one **P2** | `clean` |
| [`code-hygiene-p2-reference-to-wrong-place-for-live-constraint.yaml`](code-hygiene-p2-reference-to-wrong-place-for-live-constraint.yaml) | comment cites closed duplicate for a live limit | report one **P2** | `clean` |

## Validation and results

[`../../../tests/unit/benchmark/test_code_hygiene_corpus.py`](../../../tests/unit/benchmark/test_code_hygiene_corpus.py)
pins the structure: every case parses, hygiene never reaches P0/P1, the
default-tier and control cases carry no findings, the two P2 cases carry exactly
one required P2 with a `clean` decision, and every issue-listed shape is present. Corpus membership,
patch application, and the committed taxonomy index are covered by the existing
sweeps.

Live adapter results (detection on the P2 cases, false-positive rate on the
nine no-finding cases, per adapter) come from the existing harness run against
the delivered #676 implementation and are recorded per the repository's
benchmark convention. They require a live runtime and are not produced by the
structural tests.
