# Human Reasoning Checkpoint — Contract Recommendation

Repository-development design record for
**[#565](https://github.com/amirbena/code-review-skill/issues/565)**, child
C1 of Epic [#564](https://github.com/amirbena/code-review-skill/issues/564).
Research only: no packaged policy, template, benchmark, or user-documentation
file changes with this record. It fixes the semantics that
[#566](https://github.com/amirbena/code-review-skill/issues/566) (shared
contract + both delivery templates),
[#567](https://github.com/amirbena/code-review-skill/issues/567) (benchmark),
and [#568](https://github.com/amirbena/code-review-skill/issues/568) (Wiki and
user docs) implement, so none of them re-decides a choice below.

Not packaged; explanatory. Once #566 lands, the normative rules live in the
packaged files named in §12, which reference this record by name (not by link,
because a packaged shared resource never depends on a repository-development
document).

## 1. Recommendation in one paragraph

Add **one** human-facing section, **`### Reasoning check`**, rendered
**after the Decision block and before the subordinate metadata**, holding
**1–4 numbered questions** (typically 2–3) addressed to the engineer. It
activates only when the review already gathered evidence that makes a
question *specific* — a bug-fix/regression/incident/behavior-correction
signal whose root cause depends on evidence the reviewer did not establish, or
an architectural-placement/lifecycle result that reached beyond the changed
method. Each question is anchored to a concrete artifact the review already
holds; a question that cannot name one is dropped, and with no question left
the section is absent. It carries no severity, ID, state, or blocking meaning,
never appears inline, and changes nothing else. Its rules live in a new
shared policy, `shared/policies/reasoning-checkpoint.md` (new, packaged, `on-activation`); its
input model is a small **problem-context** subsection added to
[`review-context.md`](../../shared/policies/review-context.md); its position
and shape are one paragraph in
[`review-summary.md`](../../shared/templates/review-summary.md).
`structured_review_result` is unchanged. No new invocation option.

## 2. Verdict on the Epic invariants

All nine hold against current repository evidence. Three need a stated
reading, and two need a cross-file adjustment that #566 owns:

| Invariant | Finding | Recorded consequence |
| --- | --- | --- |
| 1 Reviewer ≠ decision maker | Compatible. | Questions are phrased as questions; provenance tags keep engineer claims labeled as engineer claims (§8). |
| 2 Not findings | Compatible. `finding.md` requires severity/ID; the section has neither and sits outside `### Findings`. | Verdict-consistency and finding-count checks never see it: §9. |
| 3 No effect on Decision | Compatible. [`severity.md`](../../shared/policies/severity.md) "Decision derivation (mechanical)" reads only finding severities (plus the `REVIEW INCOMPLETE` override). | One extra rule: question text must not contain a Decision/Result label (§9), or the [`verdict-consistency.md`](../../shared/policies/verdict-consistency.md) comparator could misread it. |
| 4 Inert unless evidence | Compatible, with a tension: a bug-fix *without* supplied context has only a weak diff signal. | Resolved by §3: the diff alone activates the investigation facet only on a strong content signal; otherwise inert. |
| 5 Contextual, never invented | Compatible. | Anchor requirement + fail-closed (§4). |
| 6 No duplicate architecture model | Compatible. `architectural-placement.md` "Stop conditions" 4 ("insufficient … fail closed") is exactly the terminal outcome the checkpoint consumes. | The checkpoint reads placement results; it adds no ring, trigger, or stop condition (§4). |
| 7 Access boundary | Compatible, but it permits more than v1 should take. | **Decision:** v1 the reviewer initiates *no* live-system observability access (§7). Invariant 7 stays a ceiling, not a target. |
| 8 Readiness language | Compatible with "safe to merge/proceed" only via a **scoped clause**; see §8. | **Adjustment for #566:** `review-summary.md` "Opening assessment" and the Decision rationale get a conditional wording rule. No change to the Result/Decision *label*. |
| 9 One capability, two surfaces | Compatible. Both delivery templates already say they follow `review-summary.md` and override only the heading. | One shared section, no per-Skill semantics (§9). |

One adjacent contract needs a boundary line, not a change of semantics:
`github-pr-review`'s **Reviewer Brief** already has a private, caller-facing
`Open questions / assumptions` field ([`reviewer-brief.md`](../../skills/github-pr-review/policies/reviewer-brief.md),
"Required fields"). It is never published and stays a handoff to the caller.
Rule: a question rendered in `Reasoning check` is never repeated in the brief,
and the brief's field never substitutes for the public section. (#566
adjustment.)

## 3. Activation

Evaluated once, after findings are final, from evidence already in hand. Two
independent **facets**; either activates the section; both may.

**Investigation facet** — the change is a bug fix, regression fix, incident
follow-up, or behavior correction **and** its root-cause claim depends on
evidence the reviewer did not establish. Signals, strongest first:

1. supplied review context whose `source_type` is `bug-description` or
   `incident-followup` ([`review-context.md`](../../shared/policies/review-context.md),
   "Recommended internal normalization");
2. PR/task/Issue/Jira text stating an observed misbehavior the change
   corrects (a tracker *type* of Bug counts as a supporting signal, never
   sufficient alone);
3. a **strong content signal** in the change itself: a regression test added
   alongside a behavior change in the same path whose name or assertion states
   the corrected symptom.

Signal 3 alone activates the facet only when the reviewer can also name the
runtime-dependent link of the chain (§6) it cannot verify. A bare `fix:`
commit prefix, a bug-shaped branch name, or a small guard added to a helper is
*not* a signal — that is the trivial case and stays inert.

**Design facet** — the review's own architectural pass produced a result worth
a checkpoint. Activates when, per
[`architectural-placement.md`](../../shared/policies/architectural-placement.md):

- a semantic-risk trigger fired **and** the bounded expansion reached at least
  the "owning abstraction / lifecycle boundary" ring, or
- the analogue-based trigger applied and found a deviation with a concrete
  consequence, or
- either terminated at "insufficient evidence" **on a change that moves a
  responsibility across a lifecycle/ownership boundary** (the honest "I could
  not establish this" is itself the reason to ask).

A trigger that fired but stopped at the changed method's direct caller/callee
with the placement confirmed correct (stop condition 2) is **inert**: the
review found nothing to check.

**Always inert:** formatting, rename, dependency bump with no behavior change,
test-only or doc-only change, config value change with no lifecycle effect,
mechanical refactor with unchanged behavior, and any change where the only
candidate question would be generic (§4). Coverage `incomplete` and an
unresolved supplied Jira reference (`JIRA CONTEXT UNRESOLVED`) are also inert
(§9).

**Why no invocation option.** Activation is evidence-driven by Epic invariant
4; an option would either default on (boilerplate pressure) or default off
(the engineer must remember to ask, which is the failure the Epic exists to
remove). "Paired off/on" in the benchmark (§11) therefore means *input without
/ with the activation evidence*, not a flag.

## 4. Shape, section name, and derivation

**One unified contract, two facets** — not two subtypes. The facets differ
only in which evidence anchors a question; count bounds, rendering, provenance,
non-effects, and interactions are identical, so a second subtype would only
duplicate them.

**Name: `Reasoning check`.** Rejected: *Questions for the author* — in local
review the reader is the engineer, not a PR author, and the name would fork
per surface. *Checklist*/*Verification* — implies completeness or a gate.

**Bounds.** Max 4, typical 2–3, min 1. Order: investigation questions first,
then design questions. Each question is one sentence ending in `?`, names its
anchor, and is answerable by the engineer without re-reading the review.

**Derivation — anchor rule.** A question is emitted only if it names at least
one concrete artifact the review already gathered:

| Anchor | Source |
| --- | --- |
| a link of the §6 chain the reviewer could not verify, tied to the supplied item it concerns (e.g. "the 14:02 timeout trace you reported") | supplied problem context |
| a changed symbol/path and the owning boundary ring that established or failed to establish its placement | `architectural-placement.md` result |
| a caller/callee/analogue actually inspected, with the consequence found or not found | same |
| a contradiction between two evidence classes (§8) | supplied context vs repository evidence |

**Prevented by construction:** questions that would be true of any change
("did you test this?", "did you consider edge cases?"), questions that assert a
defect (that is a finding), questions that ask the engineer to prove a
negative, and questions whose only anchor is the reviewer's design preference
(`architectural-placement.md` "Guardrails": no finding because another
location is merely cleaner — and no question for the same reason).

**Fail closed.** No anchorable question → no section, and **no** "insufficient
context" placeholder (that would be manufactured uncertainty, invariant 4).
The one exception is the *unverifiable hypothesis* statement in §6, which is a
real anchor, not a placeholder.

**No second investigation.** The checkpoint reads results the review already
produced. It defines no ring, trigger, stop condition, or evidence label; the
"bounded investigation" boundary is still owned solely by
`architectural-placement.md` / [`evidence.md`](../../shared/policies/evidence.md).

## 5. Problem Context Contract

Goal: let the reviewer *challenge the engineer's diagnosis*, not own it. It is
an **input convention layered on the existing review-context model**, not a
schema, template, or gate.

### 5.1 Home and integration

**Extend `review-context.md`; do not add a parallel structure.** Three
additions, all optional, all under "Recommended internal normalization":

- `bug-description` and `incident-followup` (already `source_type` values) are
  the carriers — no new type.
- A small optional **problem_context** grouping beside `intended_behavior`,
  holding the elements in §5.2, each tagged with its epistemic class (§5.3).
- The rule (below) that supplied tracker/Issue/PR text is *evidence about the
  problem to be classified*, not the problem context itself.

Identical across Skills because it lives in the shared policy;
each Skill's thin `review-context.md` keeps naming only its review target.

**Relation to Jira/Issue/PR/task text.** A ticket is the most common *source*
of problem context, not a substitute for it. Its description is usually an
*observed fact as reported* or an *engineer hypothesis*, never reviewer-inspected
runtime evidence. Classification of ticket comments already follows
[`jira-context.md`](../../shared/policies/jira-context.md); this contract adds
only that the reviewer maps the resolved text onto §5.3 classes. An unresolved
Jira reference keeps its existing `JIRA CONTEXT UNRESOLVED` behavior; this
contract never routes around it.

**Authority.** Problem context is `informational` under the contextual-evidence
model ([`contextual-evidence-model.md`](../review-context/contextual-evidence-model.md) §3)
unless it is an explicit requirement or acceptance criterion. It focuses
attention and anchors questions; it never establishes a finding and never
outranks code (`review-context.md` "Evidence hierarchy"). No new evidence type.

### 5.2 Elements and status

| Element | Status |
| --- | --- |
| Observed behavior; expected behavior | **Recommended**; **required** for the investigation facet to produce *root-cause* questions (else §6 fallback) |
| Where/environment observed | Recommended |
| Suspected root cause (hypothesis) | **Required** to activate the "does the fix explain it" question set; absent → asked, not assumed |
| Evidence supporting / weakening the hypothesis | Recommended |
| Concrete failing example or input; reproduction conditions | Optional (raises question specificity) |
| Logs, traces, metrics, alerts, persisted state, screenshots, error text | Optional; each item is classed per §5.3 the moment it is supplied |
| Affected / known non-affected flows | Optional |
| Architectural/lifecycle assumptions behind the correction | Conditionally required for the design facet's "why here" question |
| Why this change addresses the problem | Recommended |
| Unavailable evidence / access constraints | Optional; when stated, suppresses the question that would ask for that evidence |

Nothing is mandatory to run a review. "Required" above means *required to
raise that specific question*, never required to review.

### 5.3 The five epistemic classes

Every problem-context item and every question premise carries exactly one
class; **the reviewer never promotes a class silently.**

| # | Class | Rendered tag | Rule |
| --- | --- | --- | --- |
| 1 | Observed fact | *(reported)* | A behavior the engineer or tracker states was seen. Represented as reported; the reviewer did not observe it. |
| 2 | Engineer hypothesis | *(hypothesis)* | A cause or mechanism proposed. Never becomes fact because the diff implements it. |
| 3 | Repository evidence | *(reviewed)* | Read by the reviewer in the diff/repository this session. |
| 4 | Runtime / higher-environment evidence | *(reported)* or *(reviewed)* per §7 | Logs, traces, metrics, persisted state. *(reviewed)* only if actually read in-session (§7). |
| 5 | Unknown / unavailable | *(not available)* | Named explicitly when it is what blocks a link. |

### 5.4 Reasoning chain

```text
observed behavior → evidence → root-cause hypothesis → affected execution path
  → proposed correction → architectural/lifecycle placement → validation strategy
```

When context suffices, the reviewer walks the chain **looking for the first
break** and anchors a question at it. It reports at most one question per
break, and never walks a link it has no evidence for.

### 5.5 Missing and contradictory context

- **Ask vs. proceed.** The reviewer never blocks or degrades a review for
  missing problem context. "Asking" *is* the checkpoint: the missing element
  becomes a question, in the report itself (local review may be
  non-interactive; GitHub review cannot converse mid-review).
- **Unverifiable hypothesis.** A stated hypothesis with no supporting evidence
  in the supplied context or repository → one question stating the hypothesis
  cannot be validated from the available evidence and asking for the missing
  evidence class. Not a finding; the code may still be reviewed as correct.
- **Contradiction** between supplied runtime evidence, repository evidence, and
  the hypothesis → surfaced as one question quoting both sides with their class
  tags. It follows `review-context.md` "Context mismatch vs. implementation
  defect": it becomes a *finding* only through the ordinary route (code clearly
  violates an explicit requirement), never because of the checkpoint.
- **Lightweight.** No template is ever requested of the caller; unstructured
  prose is normalized by the reviewer. A review with none of the above is
  unchanged.

## 6. Chain-break cases

Each is one anchored question, worked in §10. None is a finding.

| Break | Anchor | Question shape |
| --- | --- | --- |
| Correct implementation, does not explain the symptom | observed symptom (class 1) vs the changed path | "The symptom you reported occurs at <path>; the change touches <other path> — which execution reaches the fixed code?" |
| Plausible hypothesis unsupported by supplied evidence | hypothesis (class 2), no class 3/4 backing | "What in the <logs/trace> ties <cause> to the failure?" |
| Fix addresses a symptom, not the source | changed guard vs the upstream producer inspected | "The change tolerates <bad value> at <site>; what produces it and does that stay?" |
| Right cause, wrong responsibility/lifecycle boundary | placement result (design facet) | "<Concern> is enforced at <layer> elsewhere (<analogue>); why here?" |
| Sound change, no runtime/post-deploy verification path | validation strategy link | "What specific signal after deploy would show <symptom> stopped, beyond no new reports?" |

## 7. Evidence boundary for bug investigations

**Prompt set** (a closed menu; a question may draw on it only through an
anchor): root-cause evidence; reproduction/confirmation of the observed
behavior in the environment where it occurred; whether logs/traces/metrics/
persisted state were inspected, and if not why; whether the fix explains the
runtime evidence; what observation would falsify the hypothesis; post-deploy
verification beyond absence of new reports.

**Three-way provenance.** A question that mentions an evidence item says which
of three it is:

| Label | Meaning | May be claimed when |
| --- | --- | --- |
| *reviewer-inspected* | Read in this review | the text was supplied in the invocation and read in-session, or a repository-resident artifact was read, or a runtime-validation outcome was actually `executed`/`failed` ([`runtime-validation.md`](../../shared/policies/runtime-validation.md)) |
| *engineer-reported* | Stated by the engineer/tracker | a claim without the underlying artifact |
| *possible but unavailable* | Would exist, reviewer has no path | an observability mechanism is evidenced (below) but nothing was supplied or reachable |

**Detecting that a mechanism exists** (only to decide *what to ask*, never to
claim access): supplied context naming logs/dashboards/alerts/traces/audit
records, or repository evidence of instrumentation — the diff or nearby code
emits log/metric/trace calls, or the repository contains observability
configuration. Detection yields a question ("the changed handler already logs
`<event>`; what did that show?"), not a claim about what those systems contain.

**Decision: v1 does not query live systems.** Invariant 7 allows the reviewer
to use read-only observability "where the active environment actually and
authorizably provides" it. This record recommends that v1 *not* rely on that
allowance: there is no authorization owner for it today.
[`mutation-authority.md`](../../shared/policies/mutation-authority.md)
`READ_ONLY` covers repository inspection and read-only analysis commands under
`runtime-validation.md`; `runtime-validation.md` admits only repository-declared
commands; [`trusted-host-execution.md`](../../shared/policies/trusted-host-execution.md)
authorizes an execution *backend* for those same commands. None authorizes
reaching a production or higher-environment system, and reusing them for that
would silently widen their scope. So in v1 *reviewer-inspected* runtime
evidence means only what is supplied or repository-resident; live queries are
future work needing their own principal-originated authorization channel,
mirroring `mutation-authority.md` "Trusted authorization channel", and remain
read-only-only (read access is never authorization to mutate, deploy, or act).
Repository/PR/Issue content can never grant it (`trusted-host-execution.md`
"Trusted authorization channel"). Until then the reviewer asks; it never
assumes a permission, invents log contents or runtime state, or reports
verification that did not occur.

## 8. Readiness language

**Condition R** ("runtime-dependent"): the investigation facet is active **and**
its unverified chain link is class 4 (runtime evidence) or class 5 with no
class 3 backing.

When R holds, in the opening assessment, "What changed", the Decision
rationale sentence, and the checkpoint itself, the review does not use:
*ready to push*, *fully verified*, *the bug is fixed / resolved*, *safe to
deploy*. Allowed: *consistent with the evidence reviewed*, *no blocking issue
found in the change*, and a statement of the remaining question.

**Reconciling with the shared opening-assessment rule**
([`review-summary.md`](../../shared/templates/review-summary.md), "Opening
assessment": whether the change is "safe to merge/proceed"): the rule is
*retained* and *scoped*. That sentence answers "does the diff carry a blocking
defect," which the mechanical Decision already answers; under R its wording is
scoped to that meaning:

> No blocking issue found in the change as reviewed; whether it resolves the
> reported problem depends on evidence not established here — see Reasoning check.

This creates **no second decision**: Result and Decision keep the same single
already-finalized label (`REVIEW CLEAN` / `CHANGES REQUIRED`); the scoped
sentence restates the first, it does not grade readiness. When R does not hold
the opening assessment is unchanged. `review-stopping-criteria.md` "Labeling"
(an incomplete review is never presented as safe to merge/proceed) is a
stricter, independent rule and is untouched.

Residual risk, recorded for #567: a reader may still infer "fixed" from
`REVIEW CLEAN`. The mitigation is placement (§9) and the scoped sentence;
the label is deliberately not changed (Decision is out of scope).

## 9. Placement, rendering, and interactions

**Position.** `Result → … → Validation → Decision → Reasoning check →
[subordinate metadata]`. After Decision so it is the last thing read before
the machine block (the Epic's "ends the human-facing review"); before metadata
because metadata is always last and subordinate
(`review-summary.md` "Machine metadata is subordinate"). For a self-review
`COMMENT` the attached closing disclosure line stays with the Decision block;
the section follows it. **#566 must verify** no consumer assumes Decision is
the final body element.

**Rendering.**

```markdown
### Reasoning check
Questions for you — not findings; they do not change the decision.
1. <investigation question with provenance tags>
2. <design question>
```

Under `human_review_output` the same 1–4 questions render as a short
senior-voice paragraph (a single lead-in sentence and the questions in prose);
count, anchors, and provenance are identical, voice follows
[`finding-rendering.md`](../../shared/templates/finding-rendering.md) "Senior
voice contract". `human_inline_findings` is irrelevant — there is no inline
form, ever.

| Situation | Behavior |
| --- | --- |
| Clean review | Section renders alone after Decision when active; a clean review does not gain a "Findings" section. |
| P2-only | Same. P2 does not change Decision; the checkpoint does not restate P2. |
| With findings | Renders after Decision; never duplicates a finding (a question restating a finding's defect is dropped — that is a finding). |
| `REVIEW INCOMPLETE` | **Inert.** The incomplete label already says the review is not to be trusted; a second forward-looking prompt competes with it. |
| `JIRA CONTEXT UNRESOLVED` | **Inert.** The report is ungraded and omits Findings/Decision. |
| Delta / stateful re-review | Evaluated fresh on the reviewed delta and its blast radius; **no persisted question state**, no "previously asked", no answered tracking. A delta that does not touch the fix or boundary is inert. `local-code-review` is architecturally stateless (its `SKILL.md`, "Statelessness and Orchestration Boundary"), and [`stateful-delta-rereview.md`](../../skills/github-pr-review/policies/stateful-delta-rereview.md) "Scope boundaries" carries no question state. |
| GitHub passive / active / withheld approval / self-review `COMMENT` / fallback body findings | Always in the review **body**, same text and position in every mode; the presence of an inline surface changes nothing because the section is never inline. Published exactly once. |
| Local review | Same section in the returned report, before Review Metadata. |
| Verdict-consistency | Question text contains no `REVIEW CLEAN` / `CHANGES REQUIRED` / `REVIEW INCOMPLETE` token and no `P0`/`P1`/`P2`. |
| Reviewer Brief | Never repeats a checkpoint question (§2). |

## 10. Worked examples

### A. Bug fix, with context (activates, investigation facet)

Change: retry guard added in `PaymentConsumer.handle` plus a regression test
`testDuplicateChargeOnTimeout`. PR text: "Fix duplicate charges observed in
prod after gateway timeouts."

| Class | Content |
| --- | --- |
| Observed fact *(reported)* | Duplicate charges appeared in prod after gateway timeouts. |
| Engineer hypothesis | The consumer retried after a timeout that had already succeeded. |
| Repository evidence *(reviewed)* | The consumer retries on `TimeoutException`; the charge call has no idempotency key; the new guard checks `chargeId` in memory. |
| Runtime evidence | Not supplied. The handler logs `charge.attempt` (mechanism exists). |
| Unknown / unavailable | Whether prod ever retried across process restarts. |

Findings: none. Result `REVIEW CLEAN`. Opening (scoped, §8): "No blocking issue
found in the change as reviewed; whether it stops the reported duplicates
depends on evidence not established here — see Reasoning check."

```markdown
### Reasoning check
Questions for you — not findings; they do not change the decision.
1. The guard keys on an in-memory `chargeId`; you reported duplicates in prod
   (reported, not inspected) — did the `charge.attempt` logs show retries
   within one process, or across restarts?
2. What would show after deploy that duplicate charges stopped, beyond no new
   reports?
```

Chain breaks surfaced: *correct implementation, may not explain the symptom*
(Q1); *no post-deploy verification path* (Q2). Both are questions, neither a
finding; Decision is unchanged.

### B. Architectural change (activates, design facet)

Change moves an authorization check from the controller into a service method.
The placement pass reached the owning-boundary ring and found two analogues
enforce it in the controller.

```markdown
### Reasoning check
Questions for you — not findings; they do not change the decision.
1. Authorization for `Order` is enforced in the controller in `RefundController`
   and `ExportController`; the sibling flows will bypass the service check —
   was moving it to the service intended for all order entry points?
```

No finding is raised because the evidence did not establish a consequence
(`architectural-placement.md` "Evidence"); the unresolved boundary question is
the checkpoint's material.

### C. Trivial change (inert)

Rename a private helper and adjust a log message; `fix:` commit prefix. No
context signal, no semantic-risk trigger, no content signal. **No section.** The
review is byte-identical to today's.

### D. Insufficient evidence (inert)

Change adds a null guard in a utility. Placement expansion stopped at the direct
caller (stop condition 3: no material effect). No problem context supplied; the
diff alone gives no strong content signal. Any question would be generic
("could this hide a bug?") and fails the anchor rule. **No section, no
"insufficient context" note.**

### E. Bug fix, no context (fail-closed, partial)

The same change as A with an empty PR description. Signal 3 fires (regression
test) but the reviewer can still name the unverified link, so **one** question
activates: "What evidence tied the duplicate charges to timeout retries?" —
hypothesis-unverifiable case (§5.5), not a finding.

## 11. Non-effects, and benchmark representability (input to #567)

| Concern | Unchanged, owned by |
| --- | --- |
| Finding detection | [`review-scope.md`](../../shared/policies/review-scope.md), [`evidence.md`](../../shared/policies/evidence.md) |
| Severity | [`severity.md`](../../shared/policies/severity.md) |
| Finding identity / consolidation | [`finding.md`](../../shared/templates/finding.md), [`root-cause-consolidation.md`](../../shared/policies/root-cause-consolidation.md) |
| Requirement coverage | [`requirement-coverage.md`](../../shared/policies/requirement-coverage.md) |
| Validation section | [`runtime-validation.md`](../../shared/policies/runtime-validation.md) |
| Decision, incl. `REVIEW INCOMPLETE` override | [`severity.md`](../../shared/policies/severity.md), [`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md) |
| Finding `confidence` | [`finding-confidence-model.md`](../finding-confidence/finding-confidence-model.md): a question is not a finding and carries no `confidence` |

**Benchmark.** Not representable in `benchmark-case/v2`: its `expected` block
is a patch plus expected review findings
([`fixture-format.md`](../../runtime_platform/benchmark/fixture-format.md)),
a closed, findings/Decision-shaped schema. Use the **test-only reference
fixture** pattern of
[`verdict_consistency_fixtures.py`](../../runtime_platform/benchmark/reference/verdict_consistency_fixtures.py):
a new `reasoning_checkpoint_fixtures.py` producing declarative,
metadata-bearing cases over a rendered review. Cases to cover, paired
*without/with activation evidence*:

- activation: A, B (active) vs C, D (inert) vs E (partial);
- absence of `P0/P1/P2`, IDs, validation state, Decision/Result tokens, and
  inline placement in the section;
- count within 1–4, every question anchored, provenance tags present;
- forbidden readiness phrases absent under R, allowed phrase permitted;
- Decision and finding set identical to the same input rendered with the
  checkpoint suppressed;
- rendering parity: local report vs each GitHub mode
  (passive/active/withheld/self-review/fallback) and default vs
  `human_review_output`;
- inert under `REVIEW INCOMPLETE` and `JIRA CONTEXT UNRESOLVED`;
- no invented runtime evidence or access claim.

## 12. Home, packaging, and manifest

**Combination**, each rule with one owner:

| Rule | Home |
| --- | --- |
| Activation, anchor rule, evidence boundary, provenance, readiness language, interactions, non-effects | new `shared/policies/reasoning-checkpoint.md` |
| Problem-context input model, epistemic classes | subsection of `shared/policies/review-context.md` |
| Section position and shape; scoped opening-assessment clause | `shared/templates/review-summary.md` |
| Rendering-only wiring | both delivery templates (`local-review-report.md`, `external-review-summary.md`), pointing at the shared template |
| Brief boundary line | `skills/github-pr-review/policies/reviewer-brief.md` |

`structured_review_result` is **unchanged** (recommended default confirmed): it
projects findings/coverage/Decision and is local-only; the section is
human-facing and would add an unknown key to a closed schema
([`structured-output.md`](../../shared/policies/structured-output.md)
"Document shape"). Its `summary` field remains the "What changed" prose only.

**Manifest.** Warranted. Add `capabilities/reasoning-checkpoint/capability.yaml`
(`loads: on-activation`, `adapters: [local, github]`,
`requires: [review-kernel, finding-contract]`), modeled on
`capabilities/conditional-passes/capability.yaml`, so the policy is not loaded
into reviews that never activate it (the inert-by-default invariant applies to
context cost too). #566 owns the manifest schema/baseline update.

**Packaging.** The new shared policy links only to other shared files and
names — not links — this design record, exactly as `review-context.md` names
the contextual-evidence model. It never references `AGENTS.md`/`policies/`
(`AGENTS.md` "Packaged Skills are independent…"). Runtime-neutral: no
tool-specific syntax.

## 13. Scope for the children

- **#566** — implement §12; apply the two adjustments (§2: scoped opening
  clause, brief boundary); verify no consumer treats Decision as the last body
  element; add manifest entry; keep the new policy ≤ the file-size trigger or
  decompose; Documentation-impact check for `docs/features/README.md` is #568's.
- **#567** — build `reasoning_checkpoint_fixtures.py` and its tests from §11
  contract-first (may start before #566); closes only after verifying delivered
  behavior.
- **#568** — one `docs/features/reasoning-checkpoint.md` guide + catalog row;
  states "not a gate, no option, not a findings list"; Wiki after contract is
  stable. Do not restate rules — link the shared policy.

No change is required to #564's invariants or child dependencies.

## 14. Non-goals

Live observability querying (deferred, §7); an incident template; a mandatory
problem-context schema; a readiness verdict; answered-question tracking; any
change to Decision or `benchmark-case/v2`.
