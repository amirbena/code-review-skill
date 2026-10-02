# Rendered-UI Inspection Contract

Repository-development design record for
**[#615](https://github.com/amirbena/code-review-skill/issues/615)** (C1 of
epic [#614](https://github.com/amirbena/code-review-skill/issues/614)). Not
packaged; explanatory. It is the canonical home for the rendered-inspection
contract that C2–C5 implement and C6 documents. It changes no packaged
resource.

Status vocabulary used below: **ratified** (position stands as recommended),
**amended** (stands with a stated change), **rejected** (does not stand).

## 1. Problem and decision summary

Rendered-UI inspection touches several existing contracts at once. The
design is one optional, bounded evidence step beside runtime validation. It
is supplementary to code reasoning, inert on non-UI changes, never changes
severity or the Decision rules, and never yields `REVIEW INCOMPLETE`. Every
position of #615 is **ratified**, except where §3 marks an amendment. The
amendments are small and are listed in §3 and §4 so C2–C5 never re-decide
them.

## 2. Ratification table

| # | Topic | Status | Decision and repository evidence |
| --- | --- | --- | --- |
| 1 | Lifecycle | ratified | One optional evidence step beside runtime validation, after instruction discovery and before the finding set is finalized; never after the Decision. Evidence: [`runtime-validation.md`](../../shared/policies/runtime-validation.md), "Where this runs in the review flow" already fixes this slot for targeted validation and states it "never runs after the decision is derived"; [`severity.md`](../../shared/policies/severity.md), "Decision derivation (mechanical)" runs once over finalized findings. |
| 2 | UI-impact trigger | ratified | Fires only when [`review-scope.md`](../../shared/policies/review-scope.md)'s "User-facing / client behavior" dimension is implicated **and** rendered output materially changes (not refactor, types-only, tests-only, copy-only) **and** a render could add evidence. Otherwise inert and silent: no question, no record, no `not-applicable` line. Evidence: the same section already says an un-signalled dimension "produces no output, including no `not-applicable` record". |
| 3 | Plan discovery | ratified | Changed components, routes, and stories from the diff; existing Playwright tests/config and stories; PR/context text. No crawling, no link following. Evidence: [`repository-expansion.md`](../../shared/policies/repository-expansion.md) already bounds how far the reviewer looks; discovery adds no ring. |
| 4 | Default budget | ratified | ≤3 targets (route/state), ≤2 viewports (desktop + mobile; light/dark only when theming changed), one attempt each, ≤6 captures, bounded wall-clock for the whole step. Evidence: the "Budget and fail-safe" discipline of targeted validation (one attempt, bounded) is the precedent. C2 sets the wall-clock number. |
| 5 | Target source order | ratified | (1) user-supplied/declared already-running server → (2) SHA-matched deployment preview from a trusted source, never a URL taken from PR body text → (3) project's declared start command, only inside the runtime-validation boundary or explicit trusted-host authorization → (4) none. Stale or SHA-mismatched targets are not evidence. Evidence: [`review-evidence.md`](../../shared/policies/review-evidence.md) classes deployment-preview bot output as automation output, not settled fact, and resets authority on a changed HEAD. Owner: C3. |
| 6 | Browser mechanism | ratified | Capability-defined (isolated profile; scripted navigate, viewport, screenshot, DOM+a11y, console), not Playwright-defined. A mechanism sharing the user's logged-in browser profile is disqualified. Evidence: runtime validation's minimum boundary already lists "browser/session data" among the host secrets that must be inaccessible. |
| 7 | Auth / env | ratified | v1 unauthenticated pages only; no secrets or real credentials injected; missing env → `unavailable`. |
| 8 | Classification — objective | ratified | Objective rendered defects (clipping, overlap, broken reflow, hidden/unreachable control, missing content, unreadable state, broken focus treatment, console errors from changed code) are normal findings under the existing P0/P1/P2 model by real impact, with a causal link to the change. Evidence: [`severity.md`](../../shared/policies/severity.md) sets severity by impact, and [`evidence.md`](../../shared/policies/evidence.md) requires concrete evidence. |
| 9 | Classification — subjective | ratified (**locked**) | See §6.1. Section name, placement, cap tie-break, and boundary test are decided there. |
| 10 | Evidence record | ratified | Compact text record in `Validation`; screenshots ephemeral, outside the working tree, never uploaded or published. Evidence: runtime-validation's "Generated artifacts never enter the working tree". See §5. |
| 11 | Confidence | **amended** | Reuse existing values; **no new closed-set value**. One amendment to the `confirmed` entry criteria. See §7. |
| 12 | Failure | ratified | Any failure/timeout → recorded outcome; review completes; coverage is **not** downgraded. Evidence: [`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md) coverage requires only passes "the owning policy already activates"; rendered inspection is supplementary and is declared outside that set (§4). |
| 13 | Acquisition question | ratified (**locked**) | See §6.2. One amendment: the surface differs per Skill. |
| 14 | Durable opt-out | ratified (**locked**) | See §6.2. Form and provenance decided there. |
| 15 | Delta / SHA | ratified | Inspection evidence is bound to one reviewed SHA/tree; never carried forward; a delta re-review inspects only targets the delta affects. Evidence: [`review-evidence.md`](../../shared/policies/review-evidence.md), "Interpret prior evidence against the current target" — a changed HEAD resets which prior evidence is authoritative. |
| 16 | Design reference — modes | ratified (**locked**) | See §6.3. |
| 17 | Design reference — provenance | ratified (**locked**) | See §6.3. Out-of-band signal form decided in §6.4. |
| 18 | Design reference — retrieval | ratified (**locked**) | See §6.3 and the deliberate `jira-context.md` divergence in §3. |
| 19 | Design reference — evidence authority | ratified (**locked**) | See §6.3 and its composition with `review-context.md` in §3. |
| 20 | Design reference — comparison and classification | ratified (**locked**) | See §6.3. |
| 21 | Design reference — evidence record | ratified | See §5. |
| 22 | Out of scope v1 | ratified | See the README Non-goals. |
| 23 | Capability manifest placement | decided | `capabilities/rendered-inspection/capability.yaml`, `loads: on-activation`, `adapters: [local, github]`, `requires: [capability-posture]`, activation signals = the §2 row 2 trigger; `never:` lists install-without-authorization, repository mutation, post-Decision execution, and `REVIEW INCOMPLETE` from any inspection outcome. Owner: C2. |
| 24 | `benchmark` field value | decided | `tests/reference/review/rendered_inspection.py` — the test-only reference model path, following the existing precedent of capabilities whose `benchmark:` names a reference model rather than a corpus directory (`capabilities/structured-output/capability.yaml`, `capabilities/repository-checkout/capability.yaml`). C2 creates that file in the same PR as the capability manifest. No corpus path. See §9. |

## 3. Conflict resolutions

| Existing contract | Conflict | Resolution |
| --- | --- | --- |
| [`runtime-validation.md`](../../shared/policies/runtime-validation.md) | "Purpose and boundary" forbids "service startup" and the boundary denies network by default. | **Amended by C2/C3.** The prohibition stays for every declared command and every generated reproduction. Rendered inspection gains one narrow carve-out: a *declared project start command* may run only for source (3) in §2 row 5, and only inside the same verified isolation boundary, or under explicit `allow_trusted_host_execution` authorization. Loopback to that one started target is the only network permitted; no other egress. When neither exists, source (3) is `unavailable`. No fallback to unsandboxed host execution is added. |
| [`trusted-host-execution.md`](../../shared/policies/trusted-host-execution.md) | Backend selection is scoped to "admission scope only"; a browser is a new execution payload. | **Resolved without widening.** Rendered inspection reuses `allow_trusted_host_execution` unchanged: invocation-scoped, never inferred from repository content, non-persistent, grants no mutation. It selects a backend for the start command and browser process only; it creates no new command-discovery path. Installing a browser is a separate act and is never covered by this flag (§6.2). |
| [`severity.md`](../../shared/policies/severity.md) | "P2 must not be used for cosmetic noise." | **Consistent.** Subjective polish is never P2; it is a severity-less observation outside the finding set (§6.1). Objective defects use P0/P1/P2 by impact. The Decision derivation is untouched and never reads observations. |
| `confidence` ([model](../finding-confidence/finding-confidence-model.md)) | Needs an epistemic label for render-derived findings. | **Reuse** (§7). |
| [`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md) | Could an unfinished inspection make coverage `incomplete`? | **No.** Coverage requires only passes the owning policies activate. C2 adds one sentence stating rendered inspection is not a required pass at any depth. A failed or unavailable inspection is a `Validation` outcome only. |
| [`review-context.md`](../../shared/policies/review-context.md) | Its "Evidence hierarchy" ranks actual code/tests first; a design reference is intent. | **Composed, not contradicted** (§6.3, authority). "Evidence hierarchy" governs what the code *currently does*: rendered behavior and code remain the strongest evidence of that. The design reference answers a different question, what the UI *should* look like, which is context-class evidence per "Context mismatch vs. implementation defect". Where code and a trusted applicable design disagree, the reviewer states both sides and classifies per that section: clear violation of an explicit requirement → finding; stale or ambiguous → note with evidence on each side. No sentence ranks code, tests, or rendered behavior categorically above the design. |
| [`jira-context.md`](../../shared/policies/jira-context.md) | An unresolvable supplied Jira reference stops the Jira-scoped path with `JIRA CONTEXT UNRESOLVED`. A design reference must not. | **Deliberate divergence.** Jira context defines the *scope* of the review, so reviewing without it would silently answer a different question. A design reference is optional supplementary *evidence*; the review's scope is unchanged without it. An inaccessible design therefore yields analytical mode plus one limitation line, never a stop and never `REVIEW INCOMPLETE`. |
| Stateless Skill boundary | A durable opt-out and a "ask once" question both look like memory. | **Resolved** by making the opt-out an explicit local signal (§6.2) and the question non-persistent and non-blocking. |

## 4. Shared policies C2–C5 amend

| Policy section | Amendment | Owner |
| --- | --- | --- |
| [`review-scope.md`](../../shared/policies/review-scope.md), "Canonical dimensions" → *User-facing / client behavior* "Depth owner: no dedicated owner contract exists yet…" | Replace with: depth owner is the rendered-inspection capability, as supplementary evidence that never gates or replaces the base obligation. Base reasoning stays unconditional. | C2 |
| [`runtime-validation.md`](../../shared/policies/runtime-validation.md), "Purpose and boundary" ("no … service startup") and "Where this runs in the review flow" | Add the scoped carve-out of §3 and name rendered inspection as a second optional evidence step in the same slot. | C3 (carve-out), C2 (flow sentence) |
| [`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md), "Coverage" | State rendered inspection is never a required pass. | C2 |
| [`finding-confidence-model.md`](../finding-confidence/finding-confidence-model.md) §2 `confirmed` | Add one entry criterion (§7). | C2 |
| [`shared/templates/review-summary.md`](../../shared/templates/review-summary.md) | Add the rendered-inspection `Validation` record and the severity-less *Rendered observations* section. | C2 |
| [`trusted-host-execution.md`](../../shared/policies/trusted-host-execution.md) | One cross-reference that the flag also selects the backend for the rendered-inspection start command/browser. | C3 |
| `reviewer-brief` policy/template and the local final report | Acquisition-question surface (§6.2). | C4 |

## 5. Evidence record

`Validation` gains one compact text entry per inspection:

`Rendered inspection: <mode> · target source <order #/kind> · SHA <sha> · viewports <list> · states <list> · outcome <inspected|skipped|unavailable|attempted-inconclusive> · observed <facts>`

- Outcome mirrors the runtime-validation vocabulary (`inspected` in place of
  `executed`, `attempted-inconclusive` in place of `failed`, as ratified for
  implementation in #616), so `skipped`, `unavailable`, and
  `attempted-inconclusive` are never shown as passing and never dropped.
- Screenshots stay ephemeral, outside the working tree, never uploaded or
  published; the record carries observed facts, not images.
- In design-reference mode the entry also names the reference/frame actually
  used, how it was supplied, the matched target/viewport/state, match basis
  (operator-stated vs inferred), coverage, and freshness evidence. It is absent
  in analytical mode, except the single reason line for the mode.
- Provenance, applicability, and freshness uncertainty lines live here and
  never consume the observations cap.
- Nothing is carried across invocations or SHAs.

## 6. Locked contracts (verbatim)

### 6.1 Subjective polish

Purely subjective visual polish is **not** a P2 finding, consistent with
`severity.md`'s cosmetic-noise rule. It goes in a separate, severity-less
**Rendered observations** section (alias in user docs: polish suggestions),
capped at 3, never affecting the Decision, each grounded in a page/state
actually rendered. Concrete usability, accessibility, correctness, or
engineering cost makes it no longer subjective polish; it may then become a
normal finding with evidence.

- **Name and placement:** `Rendered observations`, rendered after the findings
  and before `Validation`; omitted entirely, not rendered empty, when there are
  none. It is not part of the finding set, never feeds the Decision tally, and
  is never published as a GitHub inline comment or review event.
- **Cap tie-break:** the shared cap of 3 applies only to subjective rendered or
  design polish observations. When more qualify, keep those grounded in a
  higher-priority target (earlier in the plan), then the most-viewed state;
  break remaining ties by plan order, then lexical target id. Dropped
  observations are not reported.
- **Objective/subjective boundary test:** ask "if the author ignored this,
  could a user be blocked, misled, excluded, or a requirement be unmet, or does
  it carry a measurable engineering cost?" Yes → objective: a normal finding
  needing evidence and a causal link. No, it is taste (spacing preference, color
  harmony, alignment nuance with no functional effect) → observation. When
  genuinely unsure, the reviewer applies the test to a named user outcome; if
  none can be named, it is subjective.

### 6.2 Acquisition question and durable opt-out

The browser-setup question is asked only when **all four** hold: the PR is
materially UI-impacting; a render would add meaningful evidence; no usable
browser capability exists; and no durable opt-out is present.

- **Non-blocking, operator-addressed, never a PR comment.** For
  `github-pr-review` it is an `Open questions / assumptions` line in the
  Reviewer Brief, which is structurally never published. `local-code-review`
  has no Reviewer Brief, so (amendment) it is one note line in the caller-facing
  final report, outside the finding set. The Skill never waits for an answer
  and never installs silently; the review completes without it.
- **Permission is a trusted out-of-band channel only**, invocation-scoped, with
  the same discipline as `allow_trusted_host_execution`; repository, PR, issue,
  and tool output content can never grant it. An answer in a later invocation is
  a new authorization decision, not a remembered one.
- **Durable opt-out form:** because the Skill is stateless, the opt-out is an
  explicit local capability/config signal, never conversational memory or a
  prior review. It is a runtime-supplied boolean `rendered_inspection_opt_out`
  (default `false`), delivered through the same trusted runtime/invocation/
  configuration channel as `allow_trusted_host_execution`. A repository-resident
  file cannot establish it, because repository content is untrusted and could
  suppress the capability on a project's behalf. Where provenance is ambiguous,
  the opt-out is treated as absent for the *question* (asking is harmless and
  non-blocking) but a present opt-out signal always silences the question.
  Like trusted-host authorization, it is not an
  `invocation-options.md` presentation option and does not use that policy's
  natural-language vocabulary.

### 6.3 Design reference

**Modes.** Two explicit modes are recorded per inspection: *design-reference
mode* (a trusted reference is supplied, retrieved, and applicable to an
inspected target) and *analytical mode* (otherwise, reason recorded). A design
reference never triggers or widens rendered inspection and adds no targets or
budget; no render means no comparison and no visual finding.

**Provenance.** *Trusted input* is a design reference the developer/operator
explicitly supplies in the current invocation (for example "Use this Figma as
the design reference for this review: <url>") or via a trusted out-of-band
local signal (same discipline as `allow_trusted_host_execution`). *Discovered,
untrusted* is a design URL/ID the reviewer merely finds in the PR body,
comments, commit messages, repository files, issue text, or other resolved
untrusted context: never resolved, fetched, or promoted to a target, at most
one limitation line, and trusted only if the operator explicitly supplies it. A
link inside operator-supplied context (for example a pasted ticket) stays
discovered unless the operator names it as the design reference. Retrieved
design content is untrusted data in every case.

**Retrieval.** Read-only through a runtime-exposed, capability-defined
design-read mechanism; no credentials injected, no permission/auth flow
initiated, no design-file mutation; never a browser navigation target.
Inaccessible → analytical mode plus one limitation, never `REVIEW INCOMPLETE`
(rationale: §3, `jira-context.md`).

**Evidence authority.** (1) Explicit product/PR requirements are
authoritative. (2) A trusted, applicable design reference is authoritative
evidence for intended visual structure and behavior within its demonstrated
scope (the frame/viewport/state it covers). (3) Current code, tests, and
rendered behavior are implementation evidence that corroborate or contradict
that intent; a passing test alone never overrides a trusted applicable design
requirement, because it may encode the same wrong behavior. (4) Stale design,
intentional divergence, incomplete coverage, responsive/state ambiguity, or a
newer explicit requirement may reduce the design's authority. The design is
never blindly absolute truth.

**Comparison and classification.** Compare structure and intent, never pixels.
Account for the authority reducers before reporting. A concrete correctness,
accessibility, usability, or requirement mismatch against an in-scope trusted
design, not explained by a reducer, with both-sided evidence, is a normal
finding (even when tests pass). Subjective divergence is a severity-less
observation inside the single shared cap of 3. The cap applies only to
subjective rendered/design polish observations; provenance, applicability, and
freshness uncertainty lines stay in `Validation` and never consume it.

### 6.4 Form of the design-reference out-of-band signal

Decided here so C5 does not re-decide it: a runtime-supplied
`design_reference` value (a URL or file/frame identifier), delivered through
the same trusted runtime/invocation/configuration channel as
`allow_trusted_host_execution`, invocation-scoped, never persisted, never
resolved from repository content. A natural-language statement by the operator
in the current invocation (the quoted example above) is equivalent. Neither is
an `invocation-options.md` presentation option.

## 7. Confidence decision

**Reuse existing values; add none.** A render-derived finding takes its value
from the existing derivation order (§4 of the confidence model):

- A finding whose defect a bounded rendered observation, taken on a
  SHA-matched target, directly demonstrates is `confirmed`. **Amendment (C2):**
  add that criterion to the `confirmed` row of §2 of the model. This parallels
  the existing static "directly demonstrates" criterion; it is not a new value
  and does not alter the derivation order.
- A render-derived finding resting on reasoning alone is `credible` (the floor).
- An inconclusive, failed, or unavailable inspection contributes **no value**:
  it is recorded in `Validation` only. `runtime-validation-unavailable` stays
  reserved for targeted per-finding validation (#128), whose meaning it
  already carries, to avoid overloading it.
- A design-reference mismatch with both-sided evidence follows the same rules;
  authority reducers that leave a context question unresolved may contribute
  `insufficient-context` per the existing `REPORT_AMBIGUITY` criterion.

`confidence` still never lowers the evidence bar, the severity, or the
decision.

## 8. Single-owner assignment of design-reference decisions

Each decision has exactly one owner so parallel children do not re-decide it.

| Decision | Owner |
| --- | --- |
| Mode vocabulary (`design-reference` / `analytical`) and the mode-reason line | C2 |
| The shared cap of 3 and the *Rendered observations* section | C2 |
| Evidence-record extension point in `Validation` (the field slots of §5) | C2 |
| Trusted vs discovered provenance, the `design_reference` signal and its handling | C5 |
| Read-only retrieval and inaccessible → analytical + limitation | C5 |
| Evidence authority and its composition with `review-context.md` | C5 |
| Applicability (frame/viewport/state match) and freshness evidence | C5 |
| Mismatch classification (finding vs observation, authority reducers) | C5 |

Non-design decisions: target sourcing/execution boundary → C3; capability
detection, acquisition question surface, opt-out, installation permission → C4;
core contract, trigger, budget, outcome vocabulary, confidence amendment,
manifest → C2; documentation → C6.

## 9. Benchmark decision

**No benchmark lane.** Rendered inspection depends on a browser, a reachable
target, and a design service: environment-dependent and brittle, so a
benchmark corpus would measure the environment rather than the review. The
`benchmark:` manifest field names the test-only reference model instead (§2
row 24).

Deterministic components that do warrant tests, to be added inside the
implementing children (policy-wiring and reference-model tests, not corpus):

- the UI-impact trigger predicate and its inert/silent cases (C2);
- budget enforcement and outcome mapping (failure never yields
  `REVIEW INCOMPLETE`) (C2);
- the four-condition acquisition-question gate and the opt-out silencing it (C4);
- the target-source order, SHA-match rejection, and the never-from-PR-body-text
  rule (C3);
- trusted vs discovered design provenance, including the operator-supplied
  ticket-link case (C5);
- the objective/subjective routing and the cap tie-break (C2/C5);
- "no packaged path installs or executes without trusted-channel
  authorization" (C3/C4).

## 10. Checklist against #615 acceptance criteria

- Every position stated as ratified/amended/rejected with evidence: §2.
- Conflicts resolved: §3 (runtime-validation, trusted-host, severity,
  confidence, stopping criteria, review-context, jira-context, stateless
  boundary).
- Amended shared sections named, including "no service startup" and the
  user-facing "no depth owner": §4.
- No-benchmark justified; testable components named: §9.
- Locked contracts verbatim and consistent with `severity.md` and statelessness:
  §6. No statement ranks code, tests, or rendered behavior categorically above
  the design.
- Design-reference decisions each assigned to one owner: §8.
- Docs-only: no packaged resource changed.
