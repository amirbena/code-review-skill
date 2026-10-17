# Session-Scoped Render Consent Contract

Repository-development design record for
**[#770](https://github.com/amirbena/code-review-skill/issues/770)** (C1 of
epic [#769](https://github.com/amirbena/code-review-skill/issues/769)). Not
packaged; explanatory. It is the canonical home for the render-consent
contract that [#771](https://github.com/amirbena/code-review-skill/issues/771)
implements and [#772](https://github.com/amirbena/code-review-skill/issues/772)
documents. It changes no packaged resource, adapter, test, or Wiki page, and it
extends [`rendered-inspection-contract.md`](rendered-inspection-contract.md)
(Epic [#614](https://github.com/amirbena/code-review-skill/issues/614))
without re-deciding any of it.

Status vocabulary: **ratified** (stands as proposed in the Epic), **amended**
(stands with a stated change), **open** (cannot be decided here; owner named).

## 1. Problem and decision summary

Rendered inspection is conditional but automatic: once the UI-impact trigger
fires and a browser and a target exist, it renders with no approval. This
record adds one **render-consent gate** between the trigger and capability
detection, without a second workflow:

```text
UI-impact trigger fires   (unchanged)
        |
render-consent gate       (new, this record)
        |  granted
capability detection -> install question -> target sourcing -> render   (unchanged)
```

- Consent is requested only after the trigger fires, so nothing changes for
  backend-only or trivial frontend reviews: they stay byte-identical.
- The Skill remains stateless. "Session" is a property of the **host**, and
  authorization is represented only by an attributable, trusted signal the
  reviewer can actually see; it is never stored by the Skill (§4).
- Where a host cannot hold that signal, consent degrades to **invocation scope**
  (ask again next invocation). It never degrades to implicit authorization (§6).
- No new outcome state: decline, revocation, and unavailable consent map onto
  `skipped`, with distinct recorded reasons (§5).
- Render consent never authorizes install, download, repository change, or
  trusted-host execution (§7).
- After consent, the plan is derived statically from the diff, is proportional,
  and fits the unchanged budget (VC §1, VC §2). Real input is added as a bounded
  capability (VC §3.1), the baseline render is rejected for v1 (VC §3.2), and
  evidence and per-check status are recorded by kind (VC §4).

## 2. Ratification table

| # | Topic | Status | Decision and repository evidence |
| --- | --- | --- | --- |
| 1 | Placement | ratified | After the UI-impact trigger, before detection. If consent is absent or refused, no detection, install question, or target work happens, so no install noise is produced for a render that will not run. Evidence: [`rendered-inspection-environment.md`](../../shared/policies/rendered-inspection-environment.md), "Detection", is already "evaluated once, only after the UI-impact trigger fired". |
| 2 | Relevance | amended | Same trigger as today (§3 adds the seven-class test of VC §1; no new signal source). Silent otherwise. Evidence: [`rendered-inspection.md`](../../shared/policies/rendered-inspection.md), "Inert and silent otherwise". |
| 3 | First-use approval | ratified | The gate must be satisfied before the first inspection in an interactive session. §4. |
| 4 | Session scope | amended | The Skill never stores consent. The session is the host's; authorization is a trusted signal visible to the reviewer (§4). Amends the "no state across invocations" sentences for *render* consent only (§8). |
| 5 | Decline, revocation, unavailable | ratified | Three distinct states, one outcome (`skipped`), three reasons (§5). |
| 6 | Non-interactive | ratified | Never offers, never waits, skips without a prior structured grant (§6). |
| 7 | Install separation | ratified | A separate authority, unchanged (§7). |
| 8 | Evidence and severity | ratified | No change to evidence, `confidence`, severity, or the Decision (§9). |
| 9 | New outcome state | rejected | The four existing outcomes are sufficient (§5). |
| 10 | Host support | open | Cannot be asserted from this repository; verification is assigned to #771 with a safe default (§6). |
| 11 | Verification planning | ratified | Static, diff-derived, proportional; classes and properties in VC §1. Evidence: the plan already "names, for each target, the changed element or state it exists to observe" (`rendered-inspection.md`, "Inspection plan and default budget"). |
| 12 | Viewport selection | ratified | Chosen from the diff inside the unchanged cap of 2 viewports and 6 captures; unchecked risk is recorded (VC §2). |
| 13 | Interaction capability | amended | Capability definition gains real keyboard and pointer input, bounded, with a request guard and passive-only input on non-disposable targets (VC §3.1). |
| 14 | Before/after | rejected | v1 is after-only (VC §3.2). |
| 15 | Evidence and outcomes | amended | Three kinds and per-check status inside `inspected`; one new `checks` slot (VC §4). No new outcome. |

## 3. Relevance and prompt fatigue

The gate runs only when the existing trigger in
[`rendered-inspection.md`](../../shared/policies/rendered-inspection.md),
"Activation", already holds (dimension implicated, rendered output materially
changed, a render could add evidence). It adds no detection of its own and no
second trigger evaluation. It reuses that evaluation's result.

The offer is made only if, in addition, the diff touches at least one of the seven
change classes of VC §1 (grid, overflow, typography, interaction and state,
responsive layout, positioning and stacking, visibility and appearance). If none
applies, the review stays silent and records nothing, exactly as today.

Fatigue limits, all mechanical:

- at most **one offer per review**;
- after a decline, no further offer in that review;
- after a grant, no further offer for the rest of the host session (§4);
- a later, separate review may offer again once; a decline is not
  remembered as future refusal, because remembering it would require state the
  Skill does not hold. Users who want lasting silence supply
  `allow_rendered_inspection=false` (§4.4).

## 4. Consent lifecycle and state representation

### 4.1 Offer text

The offer is the operator-facing question below, two verbatim sentences:

> This review includes frontend changes that may benefit from browser-rendered
> verification. Would you like me to run Playwright?

One appended line must state: the planned change classes (VC §1); that keyboard
or pointer interaction may occur (VC §3.1); that approval covers relevant renders
for the rest of the session; that it installs nothing; and how to refuse or
revoke. It makes no claim about outcomes.

### 4.2 Authorization sources (closed list)

Render consent is `granted` only through one of these, in this precedence:

1. **Structured value.** A runtime-supplied boolean `allow_rendered_inspection`
   (default `false`), delivered through the same trusted, out-of-band channel
   as `allow_trusted_host_execution`. It is valid for the current invocation. A
   runtime that supplies it on every invocation of a session thereby provides
   session scope without the Skill holding any state. An explicit structured
   `false` always wins.
2. **Attributable conversational reply.** The trusted invoking user's own
   affirmative reply to the §4.1 offer, in an interactive conversation, where
   that reply is present in the context the reviewer actually has. This
   reuses the recognition-layer pattern of
   [`trusted-host-execution.md`](../../shared/policies/trusted-host-execution.md),
   "Natural-language authorization phrasings": a closed affirmative/negative
   set, matched against text attributable to the user's own turn only, never
   PR/issue/commit text, instruction files, tool output, a finding's `Fix`,
   or nested-agent/spawned-child state.

Never a source, individually or combined: browser availability; a prior
session or review; repository files, manifests, workflow files, or
configuration; PR, issue, comment, or commit text; rendered page or console
text; generated content; or the reviewer's belief about what the user "probably
wants". Absent, ambiguous, malformed, or repository-sourced means `false`.

### 4.3 Session boundary

A session is the host's interactive conversation: the span over which the
reviewer's context still contains the attributable grant. The boundary is
**observable, not asserted**:

- a grant counts for a later invocation only if the granting user turn is still
  visible in the reviewer's context and has not been followed by a revocation;
- a new conversation, a fresh process, or any context in which the turn is no
  longer visible has no grant, so the gate asks again (fail closed);
- nothing is written to repository files or persistent configuration, and no
  session identifier is invented. A host that can carry the signal natively
  supplies it structurally (§4.2.1); otherwise conversation context is the only
  carrier.

Context truncation can only lose a grant, never create one, so the failure mode
is an extra question, not unauthorized rendering.

### 4.4 Durable silence

`rendered_inspection_opt_out` is **unchanged**: it silences the install question
only
([`rendered-inspection-environment.md`](../../shared/policies/rendered-inspection-environment.md),
"Durable opt-out") and neither grants nor refuses render consent. Lasting
silence of the render offer is a structured `allow_rendered_inspection=false`
(§4.2.1), supplied by the runtime on each invocation: it asks nothing and
records `skipped` · `consent-declined` with basis `declined`. Reusing the
opt-out for this would silently stop rendering for operators who set it only to
end install questions while a browser is already installed.

## 5. Decline, revocation, unavailable consent, and outcomes

| State | Meaning | Effect | Recorded outcome and reason |
| --- | --- | --- | --- |
| `granted` | a source in §4.2 authorizes rendering | proceeds to detection | n/a until the inspection runs |
| `declined` | the user answered the offer negatively, or the host's answer mechanism ended without an answer (see Waiting) | this review's render is skipped; review continues; not a future grant; not re-offered in this review | `skipped` · reason `consent-declined` |
| `revoked` | the user retracted a prior grant (closed negative set, or structured `false`) after it was given | no new inspection starts; the grant is not reused; later offers follow §3 | `skipped` · reason `consent-revoked` |
| `unavailable` | no consent channel exists for this invocation (non-interactive, no prior structured grant) | no offer, no wait; static review continues | `skipped` · reason `consent-unavailable` |

**Waiting.** The render offer is the one place a review waits, and only for the
host's own answer mechanism, once per review. The reviewer sets no timeout of its
own and never polls. When that mechanism returns without an answer, or the host
turn ends, the offer ends as `consent-declined` and the review completes.

**Outcome compatibility.** [`rendered-inspection.md`](../../shared/policies/rendered-inspection.md),
"Outcome vocabulary", defines `skipped` as "the step was not started because a
precondition, bound, or safety gate was not satisfied; the reason is stated".
Consent is exactly such a precondition, and the three states are separated by the
stated reason, so no fifth outcome is needed. `unavailable` stays reserved for a
missing browser or target.

**Revocation of a running inspection.** An inspection that already started is
stopped at the next safe point (between captures), every process the step
started is torn down, captures are discarded, and the outcome is
`attempted-inconclusive` with reason `consent-revoked-during-run`. No
observation or visual finding is emitted from a revoked run. In a
single-threaded host the user cannot interject mid-run, so this clause binds
hosts that can deliver a revocation while a step is executing and is vacuous
elsewhere.

**Recording.** When the trigger fired, one `Validation` entry still records the
outcome, per the existing rule. Its field list gains one slot, `consent
<session|invocation|declined|revoked|unavailable>`, naming the basis. No other
field changes.

**Disclosure.** The recorded `skipped` entry is the single limitation statement,
made once, and it is the context-gap disclosure. It is not repeated in findings,
the Decision, or a second paragraph. None of the states changes coverage,
makes a review `REVIEW INCOMPLETE`, or is shown as a pass.

## 6. Non-interactive execution, hosts, and fallbacks

**Interactive** means the invoking runtime can deliver the §4.1 question to a
human and receive an answer within the invocation, and signals this to the
reviewer (open question 1). Anything else is **non-interactive**, including when
the reviewer merely cannot tell. Unknown is non-interactive.

| Environment | Offer | Consent source | Behavior |
| --- | --- | --- | --- |
| Interactive host with retained conversation context | yes, once | §4.2.2, or §4.2.1 | session scope per §4.3 |
| Interactive host that compacts or drops earlier turns | yes | §4.2.2 | grant may be lost; asks again; fail closed |
| Interactive host, user answers nothing | yes | none | `declined`; review completes |
| Non-interactive, structured grant present | no | §4.2.1 | renders, invocation-scoped |
| Non-interactive, no structured grant | no | none | `consent-unavailable`; static review only |
| Automated GitHub review (CI/bot) | no | §4.2.1 only | as above; a workflow file or PR text can never grant |

A non-interactive run never blocks, never waits, and never introduces
persistent consent.

**Host capability investigation.** This repository ships portable Skills
(README: Claude Code, Codex, Cursor, GitHub Copilot, OpenCode) and forbids
runtime-specific syntax in canonical behavior
([`skill-development-policy.md`](../../policies/skill-development-policy.md)).
It records no per-host API for sessions, user prompts, or revocation delivery,
and [`distribution.md`](../distribution.md) verifies install and update paths,
not interaction capabilities. This record therefore **does not assert** support
for any named host; it specifies the capabilities a host must show, and the safe
default for a host that does not:

| Needed capability | Host without it |
| --- | --- |
| deliver a question and receive the user's own answer in-invocation | non-interactive: no offer; structured grant only |
| keep the grant turn visible across invocations of one conversation | invocation scope: ask again each invocation |
| deliver a revocation while a step runs | revocation takes effect at the next invocation; the vacuous clause in §5 applies |
| supply a structured `allow_rendered_inspection` | conversational reply is the only source |

#771 must verify these per runtime it ships guidance for and record the
verified result in the feature docs. A host that is unverified is treated as
having none of the capabilities above.

## 7. Separation from other permissions

Render consent is its own authority. It does **not** imply, and is not implied
by, `allow_browser_tooling_install`, `allow_trusted_host_execution`, or
[`mutation-authority.md`](../../shared/policies/mutation-authority.md)'s
authorizations. Specifically, approving a render never authorizes installing
Playwright, downloading a browser, installing dependencies, starting a project
start command outside the verified boundary, changing repository configuration,
or modifying any project file. The install flow, its four-gate question, the
pinned version, the user-level location, and the structured-only install signal
stay exactly as defined in `rendered-inspection-environment.md`. Natural-language
recognition (§4.2.2) is **not** extended to the install or trusted-host signals.

Order when several apply: consent gate → detection → install question (only if
consent is `granted` and no usable browser) → target sourcing → render. Every
bound, source, isolation rule, and untrusted-data rule of the existing contract
applies unchanged once consent is granted.

## 8. Existing canonical statements this contract amends

| Existing statement | Replacement (owner: #771) |
| --- | --- |
| [`rendered-inspection.md`](../../shared/policies/rendered-inspection.md) preamble and docs guide: rendering is "conditional and automatic"; "no invocation option" | Add the consent gate after the trigger; rendering needs a `granted` state. |
| [`rendered-inspection-environment.md`](../../shared/policies/rendered-inspection-environment.md), "Authorization": "A natural-language phrasing is **not** recognized for this signal" | Unchanged for install. Add a separate render-consent section that recognizes the closed phrase set of §4.2.2 for the render signal only. |
| Same file, intro and "Authorization": the Skill is stateless; "Nothing is carried over… an answer given in a later invocation is a new decision" | Keep for install. For render consent, a still-visible attributable grant in the same conversation is honored. |
| Same file, "Boundaries": "no path here persists approval state across invocations" | Scope to install approval; add that render consent is never stored by the Skill. |
| Same file, "Durable opt-out": "It silences the *question* only" | Unchanged. Render-offer silence is a separate structured `allow_rendered_inspection=false` (§4.4). |
| Same file, "Surface": install question goes to the Reviewer Brief or final-report note, never published | Unchanged for install. The consent offer is asked inline where the host is interactive; where it is not, there is no offer. It is never published to GitHub. |
| Same file, "Surface" ("never blocks the review, and the Skill never waits for an answer"), and the Epic #614 record §6.2 ("The Skill never waits for an answer") | Unchanged for the install question. The render offer waits as defined in §5, "Waiting". |
| `rendered-inspection.md`, "Evidence record" field list | Add the `consent <…>` slot of §5. |
| `rendered-inspection.md`, "Runtime neutrality": isolated context that can navigate, set a viewport, capture, and read structure, accessibility, and console | Add dispatching keyboard and pointer input to the page under test (VC §3.1). |
| Same file, "Inspection plan and default budget": the plan names the changed element or state per target | Plan items also name the property, the evidence kind, and the viewport, derived from the diff (VC §1, VC §2). Bounds unchanged. |
| Same file, "Evidence record" | Add the `checks` slot and per-check status (VC §4), alongside `consent`. |
| `capabilities/rendered-inspection/capability.yaml` | `never:` gains rendering without a `granted` consent state and treating a repository source as consent. |
| [`docs/features/rendered-inspection.md`](../features/rendered-inspection.md), "Default, conditional, or requested" | State the consent gate and its fallbacks. |

Nothing else in the Epic #614 contract is amended.

## 9. Preserved guarantees

Unchanged by this contract: the UI-impact trigger and inertness; the budget
(targets, viewports, captures, 120 s); the closed, ordered target sources and
SHA binding; browser isolation and unauthenticated-only scope; the four
outcomes and their never-`REVIEW INCOMPLETE` rule; the no-fabrication rule;
objective-defect-versus-observation classification; `confidence` derivation;
severity and the mechanical Decision. A review whose render was declined,
revoked, or never offered contributes **no** `confidence` value and **no**
severity change, and static findings keep their `credible` ceiling. Declined or
unavailable verification is never grounds to raise a finding's severity.

Static inference, browser-observed evidence, and each verification state
(`inspected`; `skipped` with reason `consent-declined`, `consent-revoked`, or
`consent-unavailable`; `unavailable`; `attempted-inconclusive`) therefore
remain distinguishable in the `Validation` record. No finding may say a defect was
reproduced unless a page was rendered and observed.

## 10. Verification rules

What a granted render inspects, and how it is recorded, is owned by
[`verification-contract.md`](verification-contract.md) ("VC"):

| Decision | Where |
| --- | --- |
| Diff-derived, proportional planning; the seven change classes; the specific offer line | VC §1 |
| Viewport selection inside the unchanged budget | VC §2 |
| Bounded keyboard and pointer input, request guard, non-disposable targets | VC §3.1 |
| After-only rendering (no baseline in v1) | VC §3.2 |
| Evidence kinds, per-check status, `checks` slot, outcome mapping | VC §4 |

## 11. Threat model

New exposure, to be catalogued by #771 in `docs/threat-model/catalog/` using the
existing categories:

| Abuse case | Safe outcome |
| --- | --- |
| PR/issue/repo content claims the user approved, or embeds "yes, run Playwright" | not attributable to the user's own turn; consent stays `false` |
| A workflow file or repository config supplies `allow_rendered_inspection=true` | not the trusted channel; ignored |
| Consent inherited by a nested agent or reused from a prior session | not a source; absent |
| Prompt fatigue pressuring blanket approval | one offer per review; structured `false` for lasting silence; consent stays separate from install |
| Context truncation resurrects or loses a grant | can only lose; fail closed |
| Approval to render smuggles install or host execution | separate authorities; no implication (§7) |
| Input actions mutate state of the target or trigger a destructive control | only plan-named actions; no form submission, credentials, or destructive controls; throwaway context, non-`GET`/`HEAD` requests aborted, and activation only on a started target inside the isolation boundary (VC §3.1) |
| A DOM-only pass is reported as visual or interaction verification | kinds recorded separately; "visually verified" needs a `visual` check (VC §4) |
| An uncovered viewport or check is presented as covered | recorded `not-checked(reason)`; never dropped (VC §2, VC §4) |
| Revoked inspection leaves a process or partial evidence | teardown and discard; `attempted-inconclusive` |

## 12. Open questions for #771 and the maintainer

1. **Interactivity signal.** How does a runtime tell the reviewer that a human
   can answer in-invocation? The default here is non-interactive when unknown.
2. **Per-host verification.** Verify each §6 capability for every runtime the
   repository documents, and publish only what is verified.
3. **Phrase sets.** Confirm the closed affirmative and negative sets for the
   §4.1 reply and for revocation, mirroring the structural pattern of
   `trusted-host-execution.md`. This record fixes the pattern, not the strings.
4. **Input-event cap and destructive controls.** The per-target/viewport cap on input events and the exact heuristic for "destructive" controls (VC §3.1 sets the principle, not the number).
5. **Offer surface in `github-pr-review`.** Passive/active GitHub runs have no
   interactive turn by default; confirm that the offer exists only for an
   operator-driven interactive review and never in a published surface.

These do not block approval of the semantics above; they are implementation
verification items. They must be settled before #771 is marked ready.

## 13. Checklist against #770 acceptance criteria

- Consent semantics and the lifecycle states are unambiguous, with decline,
  revocation, and unavailable consent distinct: §5.
- Session boundaries and state representation defined; host limitations and safe
  fallbacks documented: §4.3, §6.
- Non-interactive behavior defined: §6.
- Installation permission separate; trusted-host rules unchanged: §7.
- Every amended canonical sentence listed with its replacement: §8.
- Existing rendered-inspection guarantees preserved: §9.
- Verification planning, proportionality, viewport selection, interaction capability, before/after decision, and evidence and outcome semantics specified within the unchanged budget: VC §1–§4.
- Docs-only; maintainer approval required before #771 starts: this record changes
  no packaged resource.
