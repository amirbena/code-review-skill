# Shared Policy — Root-Cause Consolidation and Model Completeness

Applies identically to `local-code-review` and `github-pr-review`. It owns
the bounded root-cause / model-completeness pass: when several observed
failures may be one underlying mechanism, when to consolidate them into a
single authoritative finding, the shared-cause evidence bar, the
affected-locations requirement on a consolidated finding, and how a
re-review reconciles prior per-site findings against a newly established
shared cause.

This is the consolidation sub-domain of
[`review-scope.md`](review-scope.md), which owns base review scope and
routes here. It builds on [`review-scope.md`](review-scope.md), "Existing
behavior ownership" (apply that search to the structural cause), and defers
finding-rendering to [`../templates/finding.md`](../templates/finding.md),
"Affected locations on a consolidated finding," and severity to
[`severity.md`](severity.md). It introduces no second scope model and no
second evidence standard.

## Root-cause and model-completeness pass

When several observed failures may be manifestations of one underlying
mechanism, do not stop at enumerating symptom permutations. Perform a bounded
root-cause / model-completeness pass when the current evidence shows signals
such as related defects with the same failure shape, repeated fixes that move
the failure, individually correct helpers whose composition remains unsafe,
the same invariant bypassed through multiple paths, divergence from a
canonical owner, or several special cases accumulating around one abstraction.
Two related findings are a strong signal, not a mandatory numeric threshold;
one clearly demonstrated shared failure path may also be enough.

Ask whether the failures share a mechanism, whether an invariant or semantic
model dimension/state is missing, whether multiple paths bypass the same
validation or authority rule, whether an existing owner already implements
the behavior, and whether one structural correction would eliminate the
related failures. For model-, state-machine-, and policy-driven changes,
compare what the model can represent with the distinctions its governing
contract actually requires. Examples include an author without the authority
kind being established, a transition without its origin, a retry without an
idempotency identity, or a status without its ownership/source. Do not invent
dimensions speculatively: a missing dimension is a finding only when concrete
current failures demonstrate that the model cannot represent a distinction
required for correctness or policy fidelity.

### Structural finding vs. separate findings

Prefer one structural finding, with representative concrete manifestations,
when the evidence demonstrates the same underlying defect and one coherent
correction addresses it. Keep findings separate when causes or fixes are
materially different, impacts are independently significant, or collapsing
them would hide actionable information. This is semantic deduplication, not
under-reporting, and severity remains governed only by
[`severity.md`](severity.md).

A root-cause finding meets the same evidence standard as any other finding:
show at least two concrete manifestations or one clearly demonstrated shared
failure path; identify the shared mechanism; explain why it is causal rather
than merely correlated; state the impact; and connect the correction/owner
direction to that evidence. Passing examples alone or historical similarity
does not prove a structural cause.

### Shared root cause versus independent findings

A **shared root cause** is a single defect-bearing element — one validator,
helper, query, configuration value, contract, or invariant — whose one
incorrectness propagates to multiple call paths or sites, such that one
correction at that element resolves every manifestation. The other
manifestations are that defect's blast radius, not separate defects.

Findings are **independent**, and stay separate, when each site carries its
own defective code and its own fix, even when the sites rhyme: the same
*pattern* re-implemented in unrelated modules, look-alike arithmetic or
off-by-one errors that share no symbol or import, or a merely thematic
resemblance ("no timezone discipline", "validation missing somewhere"). A
common theme is not a common cause.

Worked contrast:

- *Consolidate.* A shared `is_valid_email` is loosened so four callers
  (`register`, `change_email`, `subscribe`, `invite`) all inherit the
  weakened check — one symbol, one fix, four affected call paths — so the
  review emits one authoritative finding on `is_valid_email` that names the
  four call paths, not one near-duplicate finding per caller.
- *Keep separate.* Two off-by-one bugs, one in `pagination.page` and one in
  `history.recent`, sit in unrelated modules that share no code — two
  causes, two fixes — so the review emits two findings and does not merge
  them under one "off-by-one root cause".

### The authoritative consolidated finding

Consolidation applies only when the shared cause reaches **at least two**
manifestation sites. When it does, emit one finding with a single identity,
one severity (the highest justified across the manifestations, per
[`severity.md`](severity.md)), one evidence block establishing the shared
cause, and one remediation direction aimed at that cause or its canonical
owner — plus an **affected-locations list** that names **every** known
manifestation site (call path, caller, or occurrence), so the list is
exhaustive for the sites the review found and none is hidden. On a
consolidated finding the affected-locations list is required — a consolidated
finding without it is not publishable — and it is rendered on every delivery
surface, human-readable and structured alike, per
[`../templates/finding.md`](../templates/finding.md), "Affected locations on
a consolidated finding." The finding's canonical location is the shared
cause; the affected-locations list carries the sites it reaches. An ordinary
single-site finding never carries the field. `Evidence` may still walk
through a representative subset of the sites; the affected-locations list is
what preserves the complete known blast radius. Identity, severity, the
evidence bar, and the mechanical decision derivation are unchanged — this is
the blast-radius enumeration this pass already requires, given one stable
place to record it.

### Fail open toward separate findings

Consolidation requires the shared cause to be positively established to the
evidence standard above. When it is only plausible — the sites sit in
different layers, share no element, each needs its own fix, and only a theme
connects them — emit separate findings rather than over-merging. A false
split is visible duplicate noise a reader can reconcile; an over-merge
silently drops a distinct defect. When confidence is not there, split.

### Canonical owner and external dependencies

Apply "Existing behavior ownership" above to the structural cause. When a
repository-local helper, validator, service, or policy already owns the
invariant, recommend fixing or consuming that owner instead of adding more
local copies around each symptom.

When the canonical implementation belongs to a third-party or externally
versioned package, first distinguish local misuse/configuration from an
upstream package defect:

- **Local misuse or unsupported configuration** — correct the local call,
  configuration, or ordering; dependency involvement alone is not a reason
  to recommend an upgrade.
- **Upstream defect with an evidenced maintained fix** — prefer upgrading the
  same package to the fixed version or fixed release range over a local
  reimplementation/workaround. Cite available authoritative release notes,
  changelog, advisory, upstream issue, or package evidence identifying the
  package, current version, and fixed version/range.
- **Upstream defect without a verified fixed version** — identify upstream
  ownership and explicitly recommend verifying the upstream fix/version; do
  not invent a version or claim that an upgrade is available. Recommend a
  local mitigation only when it is needed and an upgrade is unavailable,
  incompatible, unsafe, or otherwise concretely blocked.
- **Breaking or major-version upgrade** — account for migration and
  compatibility implications supported by evidence; never present it as a
  trivial remediation merely because it contains the upstream fix.

Package upgrades are not a blanket dependency rule. An upgrade recommendation
is valid only when evidence connects the maintained release to the relevant
fix; when the review environment cannot verify that evidence, state the
limitation rather than guessing.

### Re-review and Existing Review Evidence

After a structural finding, verify on re-review that the corrected invariant
covers the related paths, not only the originally reported examples. A new
symptom from the same unfixed mechanism reconciles to the same finding rather
than receiving a renamed permutation; a materially different residual defect
remains separate.

Consolidation also reconciles in the other direction on re-review. When a
prior review recorded several separate per-site findings and the current
review independently establishes — to the root-cause evidence standard above
— that they are manifestations of one shared cause, emit the single
authoritative consolidated finding (a new finding identity), and carry every
prior site and its evidence in the affected-locations list so nothing is
lost. Do not also re-emit the per-site findings alongside it.

How the prior per-site finding identities are then handled is owned by the
repository's finding-identity and lifecycle model, not restated here, and
this section never widens or weakens it:

- ordinary many-to-one matching (several prior identities that merely appear
  to map to one candidate) stays ambiguous — each prior identity and its
  state are preserved, and consolidation is never inferred from that
  topology or from wording similarity;
- only a positively established shared cause folds the prior identities into
  the consolidated finding (the lifecycle model's `CONSOLIDATED`
  disposition). Even then nothing is treated as resolved — a folded identity
  stays open until the consolidated finding itself is fixed — and every
  folded site remains visible in the affected-locations list;
- when the shared cause is not positively established, keep the findings
  separate (the fail-open above).

Repeated historical findings in one semantic area may trigger this pass as
Existing Review Evidence, but they never widen the current Review Target and
never prove the root cause by themselves. Current code, tests, configuration,
or other repository evidence must establish the shared mechanism. This pass
remains bounded to the current change's realistic blast radius: it requires no
finding graph, clustering/similarity system, dependency scanner, or automatic
package resolver.
