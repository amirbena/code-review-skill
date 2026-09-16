# Candidate-Finding Validation Model

Repository-development design record for **[#382](https://github.com/amirbena/code-review-skill/issues/382)**
(child of the [#381](https://github.com/amirbena/code-review-skill/issues/381) epic).
Not packaged; explanatory. It is the canonical home for the
`observation → candidate claim → validated finding → severity` reasoning
contract: what a candidate must prove before it is promoted to a
severity-bearing finding, gating the labeling
[`evidence.md`](../../shared/policies/evidence.md) already owns rather than
redefining it.

The test-only reference model is
[`../../tests/reference/review/candidate_finding_validation.py`](../../tests/reference/review/candidate_finding_validation.py);
its regression corpus and the worked examples below are exercised by
[`../../tests/unit/review/test_candidate_finding_validation.py`](../../tests/unit/review/test_candidate_finding_validation.py)
and the documentation contract by
[`../../tests/policy/review/test_candidate_finding_validation_docs.py`](../../tests/policy/review/test_candidate_finding_validation_docs.py).

## 1. Problem and goal

Nothing canonically owns the reasoning steps between noticing a suspicious
difference and promoting it to a severity-bearing finding.
[`evidence.md`](../../shared/policies/evidence.md) owns the confirmed-defect
/ credible-risk / optional-improvement label and
[`severity.md`](../../shared/policies/severity.md) owns the mechanical
P0/P1/P2 → decision derivation, but neither gates *what a candidate must
prove* before it reaches that labeling — so an unestablished
semantic-equivalence assumption, an unproven "regression," or a bare
structural inconsistency can reach P0/P1 without the evidentiary premise
actually supporting it.

The goal is to own that gap — the `observation → candidate claim →
validated finding → severity` pipeline — **without** weakening discovery
sensitivity, the evidence bar, or the severity definitions, and **without**
requiring Jira or any other tracker for a technically-grounded blocking
finding. Deep technical sensitivity (TOCTOU, races, stale-state use, broken
invariants, security-boundary violations, deterministic NPEs, data-loss
paths, lifecycle bugs) is fully preserved, including with no ticket at all.
The objective is to raise the standard of proof required before a candidate
is escalated, not to make the reviewer more timid.

## 2. The pipeline

```text
observation → candidate claim → validated finding → severity
```

- **Observation** — unusual code, a branch difference, a missing check, a
  differently-handled field, or a state-transition anomaly the reviewer has
  noticed. An observation is not yet a finding and carries no severity.
- **Candidate claim** — an observation the reviewer proposes to promote:
  "this is a defect because …". A candidate claim requires the validation
  steps in §3–§7 before it may become a finding.
- **Validated finding** — a candidate claim that has cleared semantic-role
  validation (§3), evidence/contract grounding (§4), causal validation (§5),
  regression-proof discipline where applicable (§6), and the disconfirmation
  pass (§7), and has been classified (§8). It is labeled confirmed defect /
  credible engineering risk / optional improvement exactly as
  [`evidence.md`](../../shared/policies/evidence.md) already requires — this
  model gates *reaching* that label, it does not add a second one.
- **Severity** — derived from the validated finding exactly as
  [`severity.md`](../../shared/policies/severity.md) already defines,
  subject to §9's finding-validity/blocking-validity separation.

Each arrow is a gate, not a formality: a claim that does not clear the gate
stays at the stage it actually earned — most often reported as a lower
classification (§8) rather than discarded outright, per the fail-open
default in §7.

## 3. Observation-first gate

Noticing an unusual shape is not itself evidence of a defect. Before an
observation is proposed as a candidate claim, the reviewer states, even
informally: *what specifically differs from what should hold, and why that
difference is suspicious rather than merely different*. An observation that
cannot clear this restatement stays an observation and is never rendered
as, or silently treated as, a finding.

This gate does not require new machinery — it is the existing
[`evidence.md`](../../shared/policies/evidence.md) discipline ("do not
manufacture findings to appear thorough") stated as the first explicit step
of this pipeline rather than left implicit.

## 4. Semantic-role validation

Before comparing two usages of the same field, function, path, or symbol,
establish that they serve the **same semantic responsibility**. The same
primitive handled differently in two places is not itself evidence of a
defect — it is evidence of a difference, and the difference is a candidate
only once the reviewer has concrete evidence the two usages are meant to
behave alike.

Concretely: identify the responsibility each usage actually serves (from
its caller, its surrounding contract, or its documented purpose — not from
name similarity alone), and confirm both usages are instances of the *same*
responsibility before treating a difference between them as a defect
candidate. Two usages that share a name or a type but serve different
responsibilities (a validation-time check versus a display-time formatter,
say) are not comparable, and a divergence between them is not a candidate
claim on that basis alone.

## 5. Evidence/contract grounding hierarchy

Every candidate claim must name the contract, invariant, or expected
behavior it violates, using this grounding hierarchy — highest to lowest:

1. **Explicit requirement / acceptance criteria** — a stated requirement,
   Jira ticket, or acceptance-criteria entry
   ([`review-context/contextual-evidence-model.md`](../review-context/contextual-evidence-model.md)'s
   `requirement` / `acceptance_criteria` types).
2. **Tests encoding intent** — an existing test whose assertions encode the
   expected behavior the candidate claims is violated.
3. **Established production behavior** — the behavior the system
   demonstrably exhibits today, elsewhere, for the same responsibility.
4. **Technical invariant** — a concurrency, atomicity, lifecycle, or
   correctness guarantee that holds independent of any stated requirement
   (a TOCTOU race, a broken transaction boundary, a security-boundary
   bypass, a deterministic null dereference, a data-corruption or data-loss
   path).
5. **Nearby precedent** — how the same contract is honored at comparable
   sites elsewhere in the repository.
6. **Local docs / comments** — an in-repository statement of intent that
   is not itself a `requirement` or `accepted_decision`.
7. **Reviewer inference alone** — the reviewer's own read of what "should"
   happen, with no corroboration from 1–6.

**Reviewer inference (7) remains valid for discovery — it is how a
reviewer notices something worth checking in the first place — but it
never alone establishes a blocking premise.** A candidate grounded in
inference alone stays a candidate until it is corroborated by at least one
of 1–6, or it is reported at a non-blocking classification per §8.

**No source in the hierarchy requires a tracker ticket.** Level 4
(technical invariant) is deliberately positioned above nearby precedent and
local docs precisely so that a TOCTOU race, a stale-state read, a broken
atomicity guarantee, a deterministic NPE, a data-corruption/loss path, a
security-boundary bypass, a lifecycle/irreversible-state violation, or a
concrete API/runtime-contract violation stands on its own technical merit
as a blocking premise, with no Jira reference required. This is the
explicit preservation the issue and its parent epic require: Jira is
sufficient, never necessary.

This hierarchy does not redefine
[`review-context/contextual-evidence-model.md`](../review-context/contextual-evidence-model.md)'s
authoritative/informational typing or resolution outcomes — it names where
a candidate's grounding evidence sits, and a `requirement` /
`acceptance_criteria` / `accepted_decision` entry that resolves
`USE_AUTHORITATIVE` there satisfies level 1 or 5 here directly.

## 6. Causal validation chain

A candidate claim is not "these two paths are inconsistent." It is:

```text
reviewed change → changed state / control-flow / assumption
               → concrete failure condition
               → observable incorrect result
```

Every link must be shown with evidence, not asserted:

1. **Reviewed change** — the actual diff content that is claimed to matter.
2. **Changed state/control-flow/assumption** — what specifically the change
   alters (a value now read before it is written, a check now skipped, an
   invariant now assumable-false).
3. **Concrete failure condition** — the specific input, timing, or
   sequence under which the changed element actually misbehaves.
4. **Observable incorrect result** — the concrete, externally observable
   consequence (wrong value returned, side effect performed twice, an
   exception escaping, data persisted incorrectly).

A candidate missing any link is not yet a validated finding. "These paths
are inconsistent" alone supplies link 1 and, at most, a hint at link 2 — it
does not supply links 3–4, and is not sufficient on its own.

## 7. Regression-proof discipline

A **regression** claim ("this used to work and the change broke it") is a
specific, stronger version of §6 and requires its own four-part evidence
set before it may be presented as proven:

1. evidence of the **prior behavior** (a test, a changelog entry, git
   history, or the pre-change code path);
2. evidence of **the change** that altered it (the diff itself);
3. evidence of the **failure scenario** under the new behavior;
4. the **causal link** connecting 2 to 3 (not merely that both exist).

Absent all four, the candidate is not presented as a proven regression —
report it, if it clears the other gates, under its actually-supported
classification (§8), phrased as what the evidence shows ("this input path
now returns X where the surrounding contract implies Y") rather than as an
asserted regression the evidence does not fully establish.

## 8. Disconfirmation pass

Before accepting a blocking candidate (one heading toward P0/P1), actively
try to invalidate it against the bounded review context already available:
task/PR context, existing tests, the relevant callers/callees identified
during the causal-chain check (§6), established behavior, nearby precedent
(§5, level 5), architecture contracts, and local docs. This is a genuine
attempt to falsify the candidate, not a restatement of the evidence that
already supports it.

The disconfirmation pass reaches exactly one outcome:

| Outcome | When | Effect |
| --- | --- | --- |
| `SURVIVES` | No contradicting evidence found, or contradicting evidence is itself non-authoritative/weaker than the candidate's own grounding. | The candidate proceeds to classification (§9). |
| `DROPPED` | Authoritative contradicting evidence shows the candidate is simply wrong (the code does the opposite of what was claimed, a guard already handles it, the "changed" behavior is unchanged). | The candidate is not reported. |
| `DOWNGRADED` | Contradicting evidence weakens the candidate's grounding (§5) or breaks a link in its causal chain (§6) without fully disproving it. | The candidate is reported at a lower classification/severity per §9, not dropped. |
| `RECLASSIFIED` | Contradicting evidence shows the candidate is real but is a different kind of issue than first proposed (a claimed correctness defect is actually a test-coverage gap, say). | The candidate is reported under the classification §9 actually supports. |

This mirrors, and reuses without redefining, the resolution discipline in
[`review-context/contextual-evidence-model.md`](../review-context/contextual-evidence-model.md)
§7 — contradicting authoritative evidence there produces the same kind of
downgrade/reclassification outcome here, applied specifically to a
candidate finding rather than to a piece of supplied context.

## 9. Classification before severity

Once a candidate clears §3–§8, classify it as exactly one of:

- **proven correctness defect** — the causal chain (§6) is complete and
  grounded (§5) at level 1–5, and the disconfirmation pass (§8) survived.
  Normally proceeds to severity per
  [`severity.md`](../../shared/policies/severity.md) and is normally
  blocking when it independently meets the P0/P1 bar there.
- **requirement ambiguity** — the grounding source (§5) is vague or
  missing where one was expected (mirrors
  [`review-context/contextual-evidence-model.md`](../review-context/contextual-evidence-model.md)'s
  `REPORT_AMBIGUITY`). Reported, not normally blocking on its own.
- **test-coverage gap** — the causal chain (§6) is plausible but the
  concrete failure condition (link 3) is not demonstrated, or the
  disconfirmation pass could not be completed because no test exercises
  the boundary in question. Reported as a coverage finding, not as a
  proven defect.
- **maintainability concern** — the candidate is real but does not rise to
  a correctness, security, or reliability defect (a valid but non-blocking
  observation per [`evidence.md`](../../shared/policies/evidence.md)'s
  "optional improvement" label).

**Only a proven correctness defect is normally blocking.** This mirrors,
and does not redefine, [`evidence.md`](../../shared/policies/evidence.md)'s
confirmed-defect / credible-engineering-risk / optional-improvement
labeling — classification here decides *which* of those labels the finding
earns before [`severity.md`](../../shared/policies/severity.md) runs; it
does not add a fourth label or a parallel severity scheme.

### Finding validity is separate from blocking-justification validity

`claim_valid` (the observation is real and the finding should be kept) and
`blocking_justification_valid` (the finding, as currently evidenced,
clears the P0/P1 bar) are **independent booleans**, not one combined
pass/fail:

- `claim_valid = true, blocking_justification_valid = true` — a proven
  correctness defect with a complete causal chain and material impact:
  proceeds to severity normally.
- `claim_valid = true, blocking_justification_valid = false` — **the
  finding is kept**, reported at its actually-supported classification
  (requirement ambiguity / test-coverage gap / maintainability concern),
  and receives whatever severity
  [`severity.md`](../../shared/policies/severity.md) derives for that
  classification — typically P2. The finding is never suppressed merely
  because it does not clear the blocking bar; only its severity is
  affected, and severity is still derived exactly as
  [`severity.md`](../../shared/policies/severity.md) already defines, never
  by this model directly.
- `claim_valid = false` — the candidate did not survive §3–§8 (dropped by
  the disconfirmation pass, or never cleared the observation-first gate);
  nothing is reported.

P0/P1 requires a violated contract/invariant (§5) **plus** a concrete
failure condition **plus** a causal connection (§6) **plus** material
impact — never "the reviewer expected different behavior" on its own. That
expectation, without the rest, is exactly the `claim_valid = true,
blocking_justification_valid = false` case above: worth keeping as a
finding, not worth blocking on.

## 10. Bounded blast-radius reuse

Once a candidate has meaningful support (has cleared §4–§6), scoping how
far its blast radius is investigated reuses the existing ring-based
caller/callee model exactly as already defined —
[`repository-expansion.md`](../../shared/policies/repository-expansion.md)'s
fixed trigger catalog and ring ceiling, and
[`architectural-placement.md`](../../shared/policies/architectural-placement.md)'s
bounded context expansion for placement/lifecycle questions specifically.
This model defines **no second expansion or blast-radius procedure**: a
candidate's causal-chain investigation (§6) and its disconfirmation pass
(§8) stop at the same rings, under the same stop conditions (including
"insufficient evidence" as a valid terminal outcome), that those two
policies already establish.

## 11. Worked examples

### Worked example 1 — technically-grounded blocking finding, no Jira

```text
Observation: a balance-check-then-debit sequence reads a value, then writes
  a decremented value in a separate step, with no lock or optimistic
  concurrency check between them.
Semantic-role validation: both operations act on the same account balance;
  no mismatch.
Grounding: level 4, technical invariant — a TOCTOU race is a concurrency
  guarantee violation independent of any stated requirement.
Causal chain: reviewed change (the split read/write) → changed assumption
  (single-writer assumed, not enforced) → concrete failure condition (two
  concurrent debits interleave) → observable incorrect result (balance can
  go negative or a debit can be lost).
Disconfirmation: no lock, transaction, or upstream serialization found on
  the calling path → SURVIVES.
Classification: proven correctness defect. claim_valid = true,
  blocking_justification_valid = true. No Jira reference was supplied or
  needed.
```

### Worked example 2 — semantic-role mismatch, not a candidate

```text
Observation: field `status` is validated with a strict enum check in the
  API controller, but read without validation in an internal batch-report
  job.
Semantic-role validation: the controller's check exists to reject invalid
  external input at a trust boundary; the batch job reads a value already
  persisted (and therefore already validated at write time) purely for
  reporting. The two usages serve different responsibilities.
Outcome: not a candidate claim — the difference in handling is explained by
  the difference in responsibility, not evidence of a defect.
```

### Worked example 3 — unproven regression, downgraded not discarded

```text
Observation: reviewer believes a changed default value "used to be" false
  and is now true, and suspects this silently changes existing behavior.
Regression-proof check: no test, changelog entry, or prior code evidence
  establishes what the prior default actually was; git history shows the
  default was introduced by this same change (no prior value existed).
Outcome: not presented as a proven regression (§7 not met). The finding is
  reported instead on what the causal chain does establish — the new
  default's own effect on current callers, if any — at whatever
  classification that evidence supports.
```

### Worked example 4 — reviewer inference alone, non-blocking

```text
Observation: reviewer feels a newly added helper "should" throw on empty
  input, though nothing in the repository states that requirement.
Grounding: only level 7 (reviewer inference alone) — no test, established
  behavior, technical invariant, precedent, or doc supports the expectation.
Classification: maintainability concern (or requirement ambiguity, if the
  reviewer can point to a genuinely vague existing requirement). claim_valid
  = true (worth raising), blocking_justification_valid = false. Reported,
  not blocking.
```

### Worked example 5 — disconfirmation drops a candidate

```text
Observation: a new code path appears to skip an authorization check present
  on a sibling path.
Disconfirmation pass: tracing the caller shows the new path is only
  reachable from a call site that already performed the same authorization
  check one layer up (ring 1 of the reused blast-radius model, §10) —
  authoritative evidence the check is not actually bypassed.
Outcome: DROPPED. claim_valid = false. Not reported.
```

## 12. Non-goals

- **No chain-of-thought exposure.** This model governs internal
  pre-publication reasoning; it does not require the validation steps
  above to appear in rendered findings, and does not change finding
  rendering or publication-mode behavior in either Skill.
- **No new runtime enum on the finding contract.** Classification (§9)
  reuses [`evidence.md`](../../shared/policies/evidence.md)'s existing
  confirmed-defect / credible-risk / optional-improvement labeling and the
  `confidence` field defined in
  [`finding-confidence/finding-confidence-model.md`](../finding-confidence/finding-confidence-model.md);
  it adds no packaged field.
- **No redefinition of evidence.md, severity.md,
  repository-expansion.md, or architectural-placement.md.** This model
  gates what reaches those contracts; it does not restate or alter their
  rules.
- **Jira is never made mandatory.** §5's hierarchy explicitly preserves a
  technically-grounded blocking finding with no tracker reference.
- **No suppression of a code-provable P1.** §9's `claim_valid`/
  `blocking_justification_valid` separation keeps a finding whose
  blocking justification does not (yet) hold; it never discards a finding
  the code evidence actually proves.

## 13. Smallest useful first implementation

1. **This model** — the pipeline (§2), the five validation gates (§3–§8),
   classification (§9), the blast-radius reuse statement (§10) — consumed
   as reviewer discipline.
2. **Reference-level cross-links only** — from
   [`review-scope.md`](../../shared/policies/review-scope.md),
   [`evidence.md`](../../shared/policies/evidence.md), and
   [`severity.md`](../../shared/policies/severity.md) to this document; no
   table, hierarchy, or worked example duplicated into packaged policy.
3. **Test-only reference model** — the deterministic corpus in
   [`../../tests/reference/review/candidate_finding_validation.py`](../../tests/reference/review/candidate_finding_validation.py),
   mirroring the worked examples above.

**Deferred** (named here so scope stays fixed):

- benchmark/corpus coverage protecting this contract's precision — tracked
  by the sibling Benchmark child issue of the #381 epic;
- Wiki documentation of the mental model — tracked by the sibling Wiki
  child issue of the #381 epic;
- any machine-readable rendering of the validation steps themselves (see
  "No chain-of-thought exposure" above — deliberately out of scope, not
  merely deferred).

## 14. Runtime boundary

This model adds **no** new capability: no retrieval, no mutation, no
network access beyond what a review already performs, and no new
publication or rendering behavior. It is reviewer discipline applied
before a finding is labeled and before severity is derived — the labeling
and derivation themselves are unchanged.

## 15. Relationship to existing canonical policies

- [`evidence.md`](../../shared/policies/evidence.md) owns the
  confirmed-defect / credible-risk / optional-improvement labeling and the
  code-evidence bar every finding must clear. This model gates *reaching*
  that bar; it does not relax or restate it.
- [`severity.md`](../../shared/policies/severity.md) owns P0/P1/P2 and the
  mechanical decision derivation. §9 decides which label a candidate has
  earned before that derivation runs; it never overrides or duplicates the
  derivation itself.
- [`repository-expansion.md`](../../shared/policies/repository-expansion.md)
  and
  [`architectural-placement.md`](../../shared/policies/architectural-placement.md)
  own the bounded, ring-based blast-radius model this document reuses in
  §10 and §11's worked examples — neither ring ceiling is redefined here.
- [`root-cause-consolidation.md`](../../shared/policies/root-cause-consolidation.md)
  owns whether several validated findings that share a mechanism are
  consolidated into one authoritative finding — orthogonal to, and applied
  after, the per-candidate validation this model owns.
- [`review-context/contextual-evidence-model.md`](../review-context/contextual-evidence-model.md)
  owns the typed authoritative/informational evidence model and its
  resolution outcomes; §5 and §8 above consume it without redefining it.
- [`finding-confidence/finding-confidence-model.md`](../finding-confidence/finding-confidence-model.md)
  owns the single `confidence` field a finding carries; this model's
  outcome composes with it (a `claim_valid = true,
  blocking_justification_valid = false` finding still receives whatever
  `confidence` its own evidence supports) without redefining it.
- [`review-scope.md`](../../shared/policies/review-scope.md) owns base
  review scope; this model sits upstream of the finding-raising language in
  its sections and is cross-linked from it, not restated there.
