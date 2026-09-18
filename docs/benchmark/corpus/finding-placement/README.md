# Finding-Placement (Fix/Action Location Derivation) Corpus

Repository-development artifact for GitHub Issue
[#387](https://github.com/amirbena/code-review-skill/issues/387). Parent
capability: [#385](https://github.com/amirbena/code-review-skill/issues/385),
implementation contract:
[#386](https://github.com/amirbena/code-review-skill/issues/386), which adds
"Deriving the fix/action location" to
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md):
canonical reasoning for **how a finding's fix/action location is derived**
from its already-accepted claim, when review evidence, causal reasoning, or
bounded context expansion touch more than one place. This is a **focused
sub-corpus** of [`benchmark-case/v2`](../../fixture-format.md) fixtures that
pin correct primary-location selection for that reasoning.

## What this corpus does *not* assert

This corpus does **not** test anchor-selection/inline-vs-body transport
mechanics for an *already-known* location —
[`../../../skills/github-pr-review/policies/finding-placement.md`](../../../skills/github-pr-review/policies/finding-placement.md)
(#164) already owns and tests that, given a resolved location. This corpus
tests the layer beneath it: whether the correct primary location is
*derived* in the first place — causal vs. symptom, caller vs. callee
ownership, locality preservation, precision, multi-location selection, and
test-vs-production placement — before that transport policy ever runs. No
#164 fixture is duplicated here.

Every fixture illustrates the reasoning, not a preferred code structure or
domain. The fictional pricing/orders/inventory/notifications/config domains
below exist only to carry each scenario; the corpus never asserts one of
those domains' implementation choices is itself canonically correct.

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of
[`../`](../README.md) and [`../../`](../../README.md) this is **not**
packaged into either Skill archive and no packaged Skill resource depends
on it — it is consumed only by this repository's own test suite, through
the single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../tests/reference/benchmark/benchmark_fixture.py).

## Selection principle

One case per required outcome shape in Issue #387's scope, so a regression
in any one is unambiguous:

- **causal center** — a claim about *cause* anchors at the site
  introducing the incorrect value, even when the failure is only observed
  downstream (`finding-placement-causal-site-not-symptom.yaml`);
- **downstream-local handling defect** — a claim about *unsafe handling*
  of an otherwise-valid, documented upstream state anchors downstream, not
  mechanically moved upstream
  (`finding-placement-downstream-unsafe-handling.yaml`);
- **caller precondition violation** — the caller failed to establish a
  state the callee is documented to be entitled to assume
  (`finding-placement-caller-precondition-violation.yaml`);
- **callee contract violation** — the callee fails to honor its own
  documented contract regardless of a conforming caller
  (`finding-placement-callee-contract-violation.yaml`);
- **pre-existing callee bug merely exposed** — a changed caller reaches a
  bug that predates it; the caller is the trigger, not the cause
  (`finding-placement-preexisting-callee-bug-exposed.yaml`);
- **context-expansion drift** — reading a sibling, a caller, or an
  existing test for evidence never by itself relocates the finding
  (`finding-placement-context-expansion-drift.yaml`);
- **precedent trap** — a correct sibling implementation used only as
  comparison evidence is never itself the anchor
  (`finding-placement-precedent-trap.yaml`);
- **false-precision / nearest-changed-line trap** — a defect that is a
  property of a function's overall coverage is anchored at the function,
  not forced onto a nearby, individually-correct changed line
  (`finding-placement-false-precision-nearest-line.yaml`);
- **multi-file primary selection** — a diff spanning several files still
  gets exactly one primary causal/contract-owning location, not an anchor
  per touched file, and is distinguished from root-cause consolidation
  (one manifestation site, not >=2)
  (`finding-placement-multi-file-primary-selection.yaml`);
- **fallback to an out-of-diff location** — the derived primary location
  can resolve to a site the diff never touches, which then legitimately
  takes `finding-placement.md`'s existing "resolved but not
  inline-commentable" fallback rather than a misleading in-diff stand-in
  (`finding-placement-fallback-reuses-unresolved-location-state.yaml`);
- **test reveals a production defect** — a correct test that fails only
  because production is broken anchors at production, not the test
  (`finding-placement-test-reveals-production-defect.yaml`);
- **defective test itself** — a test asserting an incorrect expectation
  against otherwise-correct production code anchors at the test
  (`finding-placement-defective-test-not-production.yaml`).

## Cases

| File | Outcome shape | A correct review must… | Decision |
|---|---|---|---|
| [`finding-placement-causal-site-not-symptom.yaml`](finding-placement-causal-site-not-symptom.yaml) | causal center | anchor at pricing/discount.py, not billing/invoice.py where the bad value is merely rendered | `changes-required` |
| [`finding-placement-downstream-unsafe-handling.yaml`](finding-placement-downstream-unsafe-handling.yaml) | downstream-local handling defect | anchor at billing/invoice.py's missing guard, not pricing/discount.py, which behaves per its documented contract | `changes-required` |
| [`finding-placement-caller-precondition-violation.yaml`](finding-placement-caller-precondition-violation.yaml) | caller precondition violation | anchor at orders/api.py, which skips validating a documented callee precondition | `changes-required` |
| [`finding-placement-callee-contract-violation.yaml`](finding-placement-callee-contract-violation.yaml) | callee contract violation | anchor at pricing/tax.py, which breaks its own documented contract regardless of a conforming caller | `changes-required` |
| [`finding-placement-preexisting-callee-bug-exposed.yaml`](finding-placement-preexisting-callee-bug-exposed.yaml) | pre-existing callee bug exposed | anchor at inventory/adjust.py's pre-existing off-by-one, entirely outside the diff, not the new orders/cancel.py caller that merely reaches it | `changes-required` |
| [`finding-placement-context-expansion-drift.yaml`](finding-placement-context-expansion-drift.yaml) | context-expansion drift | anchor at notifications/email.py despite reading a sibling and an existing test as evidence | `changes-required` |
| [`finding-placement-precedent-trap.yaml`](finding-placement-precedent-trap.yaml) | precedent trap | anchor at the defective integrations/webhook/client.py, not the correct integrations/slack/client.py precedent used for comparison | `changes-required` |
| [`finding-placement-false-precision-nearest-line.yaml`](finding-placement-false-precision-nearest-line.yaml) | false-precision / nearest-line trap | anchor at the whole `transition` function's incomplete event coverage, not the newly added, individually-correct elif line | `changes-required` |
| [`finding-placement-multi-file-primary-selection.yaml`](finding-placement-multi-file-primary-selection.yaml) | multi-file primary selection | anchor only at config/schema.py; the docstring-only and unrelated-flag touches in the same diff are not additional anchors | `changes-required` |
| [`finding-placement-fallback-reuses-unresolved-location-state.yaml`](finding-placement-fallback-reuses-unresolved-location-state.yaml) | fallback to an out-of-diff location | resolve the location to shared/validators.py, entirely outside the diff, rather than signup/api.py's convenient in-diff call line | `changes-required` |
| [`finding-placement-test-reveals-production-defect.yaml`](finding-placement-test-reveals-production-defect.yaml) | test reveals production defect | anchor at math/stats.py's median, not the new test that correctly reveals it | `changes-required` |
| [`finding-placement-defective-test-not-production.yaml`](finding-placement-defective-test-not-production.yaml) | defective test itself | anchor at the new test's own incorrect assertion, not the unchanged, correct math/stats.py | `changes-required` |

Per-case provenance and a one- or two-sentence rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`), alongside its
mandatory canonical taxonomy classification (`metadata.taxonomy`) — see
[`../../taxonomy.md`](../../taxonomy.md) and
[`../../fixture-format.md`](../../fixture-format.md) §10.1.

## Validation

[`../../../../tests/unit/benchmark/test_finding_placement_corpus.py`](../../../../tests/unit/benchmark/test_finding_placement_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
used for the worked example and every other corpus — never a second one —
and asserts: the sub-corpus stays small and documented; every required
outcome shape above is present; every case pins an explicit `decision`
consistent with its required findings; every case carries exactly one
required finding pinned to its intended primary-location file; and every
finding's anchor resolves inside its own case's patch or base (including
the fallback case's anchor, which resolves in `base` precisely because it
is outside the diff). Matching a reviewer's output to these expectations
and scoring it are out of scope here (Issues #41 / #52 / #54). Peer review
of the expected findings themselves happens on the pull request.
