# Shared Policy — Change-Risk Signals and Review Depth

Applies identically to `local-code-review` and `github-pr-review`. It
defines a small, fixed set of **change-risk signals**, a **deterministic**
procedure that maps the signals present in a change to one **review-depth
level**, and the requirement that the resulting level and its activating
signals are **emitted with the review**.

This policy makes the informal "scale the review to the change's blast
radius" guidance in [`evidence.md`](evidence.md), "Findings beyond the
changed lines," and [`review-scope.md`](review-scope.md) explicit and
inspectable for one specific purpose: labelling how much review effort a
change warrants. It **adds no second scope model and no second evidence
standard** — blast radius is still scoped per [`evidence.md`](evidence.md),
finding labels are still `confirmed defect` / `credible engineering risk`
/ `optional improvement`, severity is still P0/P1/P2, and
[`severity.md`](severity.md) still derives the decision mechanically. The
depth level never becomes a finding, a severity, or a merge gate.

## Activation

This pass is **always active**. Every review classifies its change into a
depth level; a change with no risk signals is classified `standard` and
that is a normal, complete outcome. There is no caller option to disable
it and no contract that must be supplied to activate it.

## Review-depth levels

Three ordered levels, lowest effort first:

| Level | Meaning |
| --- | --- |
| `standard` | No change-risk signal is present. Ordinary review depth. |
| `elevated` | Exactly one independent `elevated`-tier signal is present. Widen inspection of that signal's area and its immediate blast radius. |
| `deep` | A `deep`-tier signal is present, or two or more independent `elevated`-tier signals are. Treat the change as high-risk and review it with the most thoroughness the change's evidence supports. |

What each level *changes* about how far a review expands into the
repository, how a very large change is partitioned into review units, and
when a review pass stops is **out of scope here** — those are owned by
the repository-expansion rules, the large-PR partitioning strategy, and
the review stopping criteria respectively. This policy owns only the
signal catalog, the classification, and the rationale.

## Change-risk signals

Each signal has a **detection note** (what observed fact in the change or
repository activates it) and a **tier**. The list is fixed; a reviewer
does not invent new signal types.

| Signal | Tier | Detection note |
| --- | --- | --- |
| **Auth / access-control change** | `deep` | The change touches authentication, authorization, permission or role/scope checks, session or token handling, credential verification, or a policy file that governs access. |
| **Migration / schema change** | `deep` | The change adds or edits a database migration, DDL, a schema/model definition that maps to storage, or a data backfill/transform script. |
| **Concurrency change** | `deep` | The change adds or alters threading, locking, async coordination, shared mutable state, parallel workers, or queue/worker consumption semantics. |
| **Public API contract change** | `deep` | The change adds, removes, or retypes a public function/method signature, an HTTP route or its request/response shape, an emitted event/message field, or a published wire/serialization schema. |
| **Sensitive-path change** | `elevated` | The change modifies a file under an area the target repository treats as sensitive (for example a payments, security, or infrastructure root) and that fact is not already captured by one of the `deep` signals above. |
| **Infra / config change** | `elevated` | The change modifies CI/CD, infrastructure-as-code, container or orchestration manifests, or deployment/runtime configuration. |
| **Diff size** | `elevated` at threshold 1, `deep` at threshold 2 | The change is large by the deterministic thresholds in "Diff-size thresholds" below. |

Signal detection is evidence-based, not name-based: a file path or symbol
that merely *looks* like one of these categories, with no evidenced
effect of that kind, does not activate a signal, and a change that has
the effect activates the signal even if nothing in its path says so
(see [`review-scope.md`](review-scope.md), "Technology neutrality").

## Classification ordering

The depth level is derived by this exact, reproducible ordering:

1. **Detect** every catalog signal label supported by each **observed
   fact** — a distinct changed thing in the diff (typically a file, or a
   coherent group of hunks that implement one change).
2. **Deduplicate** the labels that belong to the *same* underlying
   observed fact into **one signal occurrence**. One fact never becomes
   several independent signals merely because overlapping catalog
   descriptions classify it under more than one label.
3. **Resolve** each occurrence to the **highest applicable tier** among
   its labels. Deduplication in step 2 must never lower the tier an
   occurrence resolves to.
4. If any resolved occurrence is **`deep`-tier**, the review depth is
   **`deep`**.
5. Otherwise, if **two or more independent resolved occurrences** are
   `elevated`-tier, the review depth is **`deep`**. "Independent" means
   distinct underlying observed facts — not the same fact relabelled. The
   diff-size occurrence, when it reaches only threshold 1, is one
   `elevated`-tier occurrence and may be one of the two.
6. Otherwise, if exactly **one** resolved occurrence is `elevated`-tier,
   the review depth is **`elevated`**.
7. Otherwise (no occurrences), the review depth is **`standard`**.

### Worked examples

- One changed file that qualifies as **sensitive-path *and* infra/config**
  (both `elevated`): step 2 dedups it to one occurrence, step 3 resolves
  it to `elevated`, step 6 → **`elevated`**. Overlapping labels on one
  fact do not reach `deep`.
- One changed file that qualifies as **sensitive-path, infra/config *and*
  auth**: step 2 dedups it to one occurrence, step 3 resolves it to the
  highest applicable tier `deep` (auth), step 4 → **`deep`**. Dedup does
  not downgrade the tier.
- **One infra/config change** in one file and **one unrelated
  sensitive-path change** in another, neither qualifying for any `deep`
  category: two independent `elevated` occurrences, step 5 → **`deep`**.
- **Diff size at threshold 1** plus **one distinct infra/config change**:
  two independent `elevated` occurrences, step 5 → **`deep`**.
- A docs-only change of forty lines with no other signal: no occurrences,
  step 7 → **`standard`**.

## Diff-size thresholds

Authoritative, policy-level numbers — not left to per-review judgement.
"Changed lines" is added plus deleted lines across the in-scope change;
"changed files" is the count of in-scope changed files. Both **exclude**
files classified non-reviewable per
[`file-reviewability.md`](file-reviewability.md) (generated, vendored,
minified, binary, snapshot/lockfile content), because a large generated
diff is not a large *change to review*.

| Boundary | The diff-size signal activates at that tier when |
| --- | --- |
| threshold 1 (`elevated`) | changed lines **≥ 150**, or changed files **≥ 10** |
| threshold 2 (`deep`) | changed lines **≥ 600**, or changed files **≥ 30** |

Boundary semantics are **`≥` (at or above the number)**: exactly 150
changed lines activates the signal at `elevated`; exactly 600 activates
it at `deep`; 149 activates nothing. When both a line count and a file
count apply, the signal takes the higher of the two tiers.

The diff-size signal is a **deterministic heuristic input to depth
classification only**. Size is never evidence that a change is defective
and never contributes to any finding's severity, confidence, or evidence
label.

## Depth-only conservative tie-break

When the available evidence supports **more than one plausible applicable
depth level** for a change, classification selects the **higher
review-effort level**.

This tie-break is strictly scoped to the `standard` / `elevated` / `deep`
label:

- It does **not** strengthen any finding's evidence label, severity,
  confidence, or applicability.
- It does **not** override the repository's existing rule that
  unresolved architectural or evidentiary ambiguity can terminate a
  reasoning pass **without a finding** — see
  [`review-scope.md`](review-scope.md), "Architectural placement and
  execution-lifecycle fidelity" (stop condition 4 and "'Insufficient
  evidence' is a valid terminal outcome"), and [`evidence.md`](evidence.md).

Ambiguity may cause more review; it never produces a stronger defect
claim.

## Machine-readable model

```yaml
change_risk:
  depth: standard | elevated | deep
  occurrences:
    - signals: [<catalog signal name>, ...]   # the label(s) this one changed fact matched
      tier: elevated | deep                    # the highest applicable tier for the occurrence
      evidence: <the observed fact — path, symbol, or diff-size measurement>
```

`occurrences` lists one entry per **resolved occurrence** (after
deduplication): the catalog signal label(s) that one changed fact
matched, the single tier the occurrence resolved to, and the concrete
evidence. An occurrence that matched several labels is still one entry.
`depth` is derived from `occurrences` by "Classification ordering" above
and by nothing else. For a `standard` classification `occurrences` is
empty.

## Rationale emission

The review **emits the classification with its result**: the derived
`depth` level and, for each activating signal, the signal name and the
observed fact that activated it. It is rendered in the review's
subordinate metadata (see
[`../templates/review-summary.md`](../templates/review-summary.md),
"Machine metadata is subordinate") — alongside review mode, reviewed
HEAD, and finding counts — never in the primary human-facing body, never
as a finding, and never in a way that implies a verdict. A `standard`
classification is still emitted (as `standard` with an empty `signals`
list); it is not silently dropped. Each Skill's own template owns the
concrete markup for its delivery surface: `local-code-review` always
renders it in "Review Metadata"; `github-pr-review` renders it in the
subordinate `Review metadata` block.

## Non-goals and ownership boundary

- **Not a merge gate.** The depth level is never an input to the
  mechanical decision in [`severity.md`](severity.md) and never blocks a
  merge on its own.
- **Never skips review.** A `standard` classification is still a full
  review at ordinary depth; low risk is not "no review."
- **No PR splitting.** This policy classifies a change; it never splits a
  pull request or asks the author to.
- **Defers downstream behavior.** How `elevated` / `deep` change
  repository expansion, large-change partitioning, and review stopping
  criteria is owned by those separate policies, not here. This policy
  provides only the vocabulary and the classification they consume.

## Not a second scope or evidence model

Everything a finding needs — blast-radius scope, evidence, labels,
severity, and the mechanical decision — is unchanged by this policy. The
depth level tunes how much effort a review spends looking; it never
lowers the bar for reporting a finding, never raises a finding's
severity, and never substitutes for the evidence a finding must carry.
