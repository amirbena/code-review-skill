# Shared Policy — Repository Expansion

Applies identically to `local-code-review` and `github-pr-review`. It
defines when and how far a review's investigation expands beyond the
changed lines into the rest of the repository: a small, fixed catalog of
**expansion triggers**, a **bounded, ring-based** procedure for how far
each trigger may be followed, and the requirement that every expansion
decision is **reported with the review**.

This makes the general "scale dependency exploration to blast radius"
guidance in [`evidence.md`](evidence.md), "Findings beyond the changed
lines," concrete and inspectable for the general case: any investigation
that needs to look past the diff to gather evidence for a finding. It
does **not** replace [`review-scope.md`](review-scope.md),
"Architectural placement and execution-lifecycle fidelity" (still the
canonical bounded-expansion procedure for placement/lifecycle questions
specifically) or [`affected-test-analysis.md`](affected-test-analysis.md)
(still the canonical procedure for tracing a change into tests that
depend on it) — those remain independent, narrower appliances of the same
underlying idea. This policy is the general-purpose default for the fixed
trigger catalog below, and the one that ties expansion bounds to
change-risk depth.

## Activation

This pass is **always active**, the same posture as
[`change-risk-signals.md`](change-risk-signals.md). Every review evaluates
whether an expansion trigger is present in the diff; a change with none
present stays scoped to the diff and its immediately adjacent evidence per
[`evidence.md`](evidence.md), and that is a normal, complete outcome.
There is no caller option to disable it.

"Always active" describes the trigger-evaluation predicate above, not
whether this file itself is opened. Recognizing which trigger *type* a
change plausibly implicates, and — for the interface/contract,
migration/schema, and config-consumer triggers — whether they fire, are
both decidable from the diff alone, against the fixed trigger catalog
`review-scope.md`'s "Repository expansion" already restates as resident
summary: each of those three fires on a fact the diff itself already
shows. Only the call-site trigger's firing can require this file's own
ring-1 investigation to confirm, per "Signal detection is evidence-based,
not name-based" below — see "Conditional loading: fail-closed" below for
how that one exception governs
`capabilities/scale/capability.yaml`'s `on-activation` loading.

## Expansion triggers (fixed catalog)

Each trigger names the concrete diff fact that activates it and what it
points investigation toward. The list is fixed; a reviewer does not
invent new trigger types.

| Trigger | Activates on | Investigation target |
| --- | --- | --- |
| **Call-site trigger** | A changed public/exported function, method signature, class, or module-level symbol that has consumers elsewhere in the repository. | Direct call sites / usages of the changed symbol. |
| **Interface/contract trigger** | A changed interface, abstract base, protocol, dependency-injected abstraction, or published API/event/message schema. | Implementers or subclasses of a changed interface; producers and consumers of a changed contract or schema. |
| **Migration/schema trigger** | A changed database migration, DDL, schema/model definition, or data backfill/transform script. | Queries, ORM models, and sibling migrations that reference the changed table or column; the migration's ordering relative to other migrations. |
| **Config-consumer trigger** | A changed configuration key, feature flag, environment variable, or other externally-consumed setting. | Code paths that read or otherwise consume the changed key. |

Signal detection is evidence-based, not name-based, per
[`review-scope.md`](review-scope.md), "Technology neutrality": a symbol
that merely *looks* public or exported, with no evidenced external
consumer, does not activate the call-site trigger, and a symbol activates
it whenever it has an evidenced consumer even if nothing in its name says
so.

A single changed fact may simultaneously activate one of the
[`change-risk-signals.md`](change-risk-signals.md) catalog's signals
(that policy's classification) and one of the triggers above (this
policy's investigation target) — they are two independent facts about the
same change, not one catalog. A changed migration, for example, is
independently a `deep` change-risk signal there and an activated
migration/schema trigger here.

## Bounded, ring-based expansion

Investigate minimum-context-first, expanding one ring at a time and only
as far as needed — the same discipline already used for
architectural-placement questions in
[`review-scope.md`](review-scope.md), "Bounded context expansion":

```text
changed symbol / fact (ring 0 — the diff itself)
→ direct call sites, consumers, or referencing queries (ring 1)
→ owning interface, schema definition, or contract (ring 2)
→ sibling implementers or consumers only if still necessary (ring 3)
```

Stop at the first ring that establishes or disproves the question the
trigger raised. Do not default to repository-wide exploration.
"Insufficient evidence" is a valid terminal outcome, exactly as
[`review-scope.md`](review-scope.md), "Architectural placement and
execution-lifecycle fidelity," "Stop conditions" already establishes for
placement questions — but it is never reported as if the relationship had
been checked: see "Relationship outcomes and unresolved relationships"
below.

### Expansion bound scales with change-risk depth

The **maximum ring** an expansion may reach for the current change is
bounded by that same change's `standard` / `elevated` / `deep`
classification from [`change-risk-signals.md`](change-risk-signals.md):

| Change-risk depth | Maximum ring reachable |
| --- | --- |
| `standard` | Ring 1 (direct call sites/consumers only), and only when a trigger fired. |
| `elevated` | Ring 2. |
| `deep` | Ring 3. |

This is a **ceiling, not a target**: a trigger resolved at an earlier ring
stops there regardless of the change's depth — see "Stop at the first
ring" above. A `deep` classification never forces expansion out to ring
3; it only permits reaching it when a trigger's own resolution genuinely
needs that much context.

## Determinism

Given the same diff and the same repository state, the same triggers fire
and the same rings are traversed to the same stopping point — no
run-to-run variance and no reviewer discretion to expand further "just in
case." Reviewer judgement applies only *within* a ring (for example, which
of several sibling call sites to read first), never to whether a trigger
fires or how far its ceiling reaches.

## Relationship outcomes and unresolved relationships

Every relationship question a fired trigger raises ends in exactly one of
three outcomes. This section is the single definition; other policies and
templates name these values and do not restate them.

| Outcome | Meaning |
| --- | --- |
| `resolved_relevant` | The relationship was established inside the authorized ring and carries relevant evidence (a concrete `path:line`). |
| `resolved_none` | The search was actually performed, with a capability able to answer the question inside the authorized ring, and no relevant repository-local relationship exists. |
| `unresolved` | The question could not be established — ambiguous resolution (dynamic dispatch, reflection, string-keyed lookup), an unsupported language shape, missing or unavailable capability, or evidence that was not obtainable inside the authorized ring. |

- **Absence is established, never inferred.** `resolved_none` requires that
  the search ran and could have found the relationship. A search that
  returned nothing because it could not look (no capability, unreadable
  path, ambiguous dispatch) is `unresolved`, not `resolved_none`.
- **The ring ceiling is not a verdict.** When the ceiling for the change's
  depth is reached with the question still open, the outcome is
  `unresolved`. An `affected_test` question has no ring: it is `unresolved`
  when [`affected-test-analysis.md`](affected-test-analysis.md)'s own
  tracing could not link the change to tests. Stop-at-first-ring and the ceiling table are unchanged.
- **Initial relationship classes.** `caller_consumer` (callers of a changed
  symbol; consumers of a changed config key or contract),
  `implementation_interface` (implementers of a changed interface, or the
  interface a changed implementer must still satisfy), and `affected_test`
  (tests that depend on the changed behavior, per
  [`affected-test-analysis.md`](affected-test-analysis.md)). The classes
  are demonstrated review needs, not an ontology; an unlisted class —
  including architectural analogue and relevant dependency — is out of
  scope until a later contract adds it explicitly.
- **Coverage is unchanged.** An `unresolved` relationship is a
  visibility-only disclosure: it is not an incomplete trigger in
  [`review-stopping-criteria.md`](review-stopping-criteria.md), never turns
  coverage to `incomplete`, and never alters the Decision, a finding's
  severity, identity, or evidence bar. `coverage: complete` keeps its
  existing meaning — every required pass reached its own stop condition —
  and does not assert that every relationship was resolved.
- **Never presents as complete context.** A review with at least one
  `unresolved` relationship renders the optional **Context gaps** section
  of [`../templates/review-summary.md`](../templates/review-summary.md):
  one bullet per unresolved relationship naming its class, subject, reason,
  and, for expansion-trigger classes, ring reached. The review must not describe an unresolved relationship
  with wording that claims it was checked ("no callers", "all consumers
  verified"). The section is omitted entirely when nothing is unresolved,
  and it is never a finding.
- **No second evidence-state model.** The outcome vocabulary applies to
  relationships only. It adds no `confidence` value: a finding's
  `confidence` (`insufficient-context` included) is derived exactly as
  [`../templates/finding.md`](../templates/finding.md), "Confidence and
  evidence state," defines, and an unresolved relationship that bears on a
  finding is cross-referenced by that finding's id rather than restated.
  An unresolved relationship cannot support a finding.

## Expansion decisions are reported

Every review emits, alongside the change-risk classification, which
triggers fired — or none — and, for each fired trigger, the ring reached
and the concrete locations inspected. It is rendered in the review's
subordinate metadata (see
[`../templates/review-summary.md`](../templates/review-summary.md),
"Machine metadata is subordinate") — never in the primary human-facing
body, never as a finding, and never in a way that implies a verdict. The
one human-visible exception is the **Context gaps** disclosure above, which
carries only `unresolved` relationships. A
review with no fired trigger still emits the classification, as "none";
it is not silently dropped.

## Conditional loading: fail-closed

`capabilities/scale/capability.yaml` declares this file `on-activation`,
alongside [`large-pr-partitioning.md`](large-pr-partitioning.md). That
governs when this file's deeper ring-expansion procedure, bound table,
and machine-readable model below are consulted — never whether the
trigger-evaluation predicate in "Activation" above runs, which stays
always active exactly as stated there. This file loads only once a
trigger has already been decided to have fired, or its firing cannot yet
be confidently ruled out; it is never opened as a precondition to first
recognizing which trigger *type* — a changed call-site, interface/
contract, migration/schema, or config-consumer fact — a change plausibly
implicates, since that recognition is decidable from the diff alone,
against the fixed trigger catalog `review-scope.md`'s "Repository
expansion" already restates as resident summary.

Confirming a recognized trigger actually *fires* is, for three of the
four triggers, equally resident: the interface/contract, migration/schema,
and config-consumer triggers each fire on a fact the diff itself already
shows (a changed interface/schema, migration/DDL file, or config key),
with no further investigation needed to know they fired. Only the
call-site trigger is different, per "Signal detection is evidence-based,
not name-based" above's requirement (an evidenced consumer, not merely a
name or path that looks public) — confirming *it* fired can require this
file's own ring-1 investigation to resolve, and is not always decidable
from the diff and its immediately adjacent context alone. That is not a
gap in this contract: an inconclusive or not-yet-investigated call-site
firing determination is itself the ambiguous case below, and fails closed
to performing that investigation (loading this file), never to silently
treating the call-site trigger as unfired for lack of a visible consumer
in the diff.

Loading is fail-closed: if evaluating whether a trigger fired is unclear,
incomplete, or fails for any reason — including because a call-site
trigger's evidenced-consumer determination has not yet been investigated
— this capability loads anyway. Ambiguity resolves to load, never to skip
— the
same convention [`specialist-depth.md`](specialist-depth.md)'s
"Conditional loading: fail-closed" already establishes. A capability
boundary that a failed or ambiguous predicate evaluation could silently
bypass is the one catastrophic-if-wrong outcome this contract exists to
prevent; this file's activation predicate must never be able to produce
that outcome.

Not loading this capability never narrows or substitutes for the
always-active trigger-evaluation predicate itself — that predicate always
runs regardless of whether this file is ever opened. Conditional loading
changes only when the ring-expansion procedure and reporting model below
are consulted, never whether a trigger is evaluated.

This conditional-loading contract is scoped to `scale` alone (this file
and [`large-pr-partitioning.md`](large-pr-partitioning.md)); it does not
define, and must not be read as defining, a general loading/routing
mechanism for any other capability in this repository.

## Machine-readable model

```yaml
repository_expansion:
  triggers:
    - trigger: call_site | interface_contract | migration_schema | config_consumer
      source: <the observed diff fact that activated it>
      ring_reached: 1 | 2 | 3
      locations: [<path:symbol or path:line inspected>, ...]
  relationships:
    - class: caller_consumer | implementation_interface | affected_test
      subject: <changed symbol, key, or interface>
      outcome: resolved_relevant | resolved_none | unresolved
      ring_reached: 1 | 2 | 3   # expansion-trigger classes only
      reason: <present only when outcome is unresolved>
```

`triggers` is empty when no expansion trigger fired on the current change.
`relationships` is a sibling list, one entry per relationship question
asked, and is empty when none was asked. It is not nested under `triggers`
because `affected_test` comes from the signal-triggered
[`affected-test-analysis.md`](affected-test-analysis.md) pass, which is not
an expansion trigger and has no ring.

## Relationship to the repository-intelligence model

This policy stays canonical for *when* expansion happens, *which trigger*
authorizes it, and *how far* (the ring ceiling table above) — none of that
changes. The repository-intelligence model design record (a
repository-development document, not a packaged resource, so it is named
here, not linked) types what a fired trigger resolves *inside* an
authorized ring — entity and relationship semantics, provenance, snapshot
identity and staleness, and relationship-influence attribution — without
re-deriving or loosening this policy's ring ceiling.

## Non-goals and ownership boundary

- **Not a merge gate.** An expansion decision never blocks a merge on its
  own and is never itself a finding.
- **No cross-repository expansion.** Investigation stays within the
  current repository, or, for `local-code-review`'s explicit,
  user-authorized multi-repository Review Target (see
  `skills/local-code-review/policies/multi-repository-review-target.md`),
  within the already-admitted member repositories of that target — never
  into a repository the caller did not explicitly supply. This governs
  expansion into a **non-member** repository specifically: a separate
  dependency, submodule, or service repository that is not itself an
  admitted Review Target member is out of scope for this policy; it does
  not restrict evidence-connection between repositories the caller has
  already, explicitly admitted as co-equal members of the same combined
  target.
- **Not a repository-wide audit.** Ring-bounded expansion investigates
  only what a fired trigger needs; it is never license to explore
  unrelated repository areas.
- **Defers finding standards to evidence.md and severity.md.** This
  policy adds only *where to look*; what counts as a finding, its
  evidence label, and its severity are unchanged.
- **Does not replace signal-specific expansion procedures.**
  [`review-scope.md`](review-scope.md), "Architectural placement and
  execution-lifecycle fidelity" and
  [`affected-test-analysis.md`](affected-test-analysis.md) remain the
  canonical procedures for their own specific questions; this policy is
  the general-purpose default for the fixed trigger catalog above.

## Reused, not redefined, by candidate-finding validation

The candidate-finding validation model (a repository-development document,
not a packaged resource, so it is named here, not linked) scopes a
candidate's blast-radius investigation by reusing this policy's fixed
trigger catalog and ring ceiling directly — it defines no second expansion
procedure.

## Not a second scope or evidence model

Everything a finding needs — blast-radius scope, evidence, labels,
severity, and the mechanical decision — is unchanged by this policy. It
only makes the "how far do I look beyond the diff" decision inspectable
and reproducible; it never lowers the evidence bar a finding must clear
and never substitutes for the evidence a finding must carry.

Following a trigger's ring into a caller, callee, sibling, test, utility,
or downstream consumer for evidence never by itself relocates a finding:
where the resulting finding's fix/action location is anchored is governed
by [`../templates/finding.md`](../templates/finding.md), "Deriving the
fix/action location," not by which ring the investigation reached.
