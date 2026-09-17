# Specialist-Depth Continuation Checkpoint

Repository-development decision record for issue
[#412](https://github.com/amirbena/code-review-skill/issues/412), child of
[#403](https://github.com/amirbena/code-review-skill/issues/403), blocked
by [#411](https://github.com/amirbena/code-review-skill/issues/411). Per
#412's own Problem statement, the roadmap in
[`capability-architecture-model.md`](capability-architecture-model.md)
deliberately did not plan migration of the other capabilities in §M.4's
list; this record is the explicit, written checkpoint #412 requires before
any such follow-up issue is created, so that continuing the pattern is a
decided choice rather than a default.

Like the rest of [`./`](README.md), this is a repository-development doc:
**not** packaged into either Skill archive, and no packaged Skill resource
depends on it. It answers #412's questions using evidence already recorded
in [`capability-loading-baseline.md`](capability-loading-baseline.md)
(#408) and
[`specialist-depth-progressive-loading-proof.md`](specialist-depth-progressive-loading-proof.md)
(#411); it does not re-run or re-derive that evidence, and per #412's own
Non-Goals it does not create the follow-up migration issue it names.

## 1. Did progressive loading materially reduce the instruction surface?

Yes, modestly. Per the #411 proof (§2), `specialist-depth` is the single
largest attributed capability in either adapter's surface, and making its
loading conditional removes that surface from a review that does not need
it:

| Adapter | Reduction when `specialist-depth` is not loaded |
| --- | --- |
| `local-code-review` | 11.28% (83,154 → 73,775 words) |
| `github-pr-review` | 8.35% (112,342 → 102,963 words) |

This is a real, measured reduction, not a projection — but it is one
capability out of the thirteen §M.4 names, and packaging membership is
unaffected (the archive still ships `specialist-depth`'s files
unconditionally; only the instruction surface a review's own reasoning
applies is conditional). A double-digit reduction from the single largest
capability does not by itself establish what the remaining twelve, mostly
smaller, capabilities would contribute in aggregate.

## 2. Did benchmark behavior remain stable?

Yes. The #411 proof (§3) re-ran #408's own 4-case regression corpus live
through the real reviewer runtime and recorded 0 false negatives / 0 false
positives on every case — identical to #408's recorded baseline. No
existing pinned benchmark expectation was rewritten to force this result
(#411's Non-Goals).

## 3. Were activation predicates reliable, or did they need frequent fallback?

Reliable on the evidence gathered, but that evidence is three live cases,
not a large population — this question is answered provisionally, and the
caveat matters for §6 below. `specialist-depth`'s predicate is decidable
entirely from evidence `review-scope.md`'s base pass already produces
while resident (`shared/policies/specialist-depth.md`, "Conditional
loading: fail-closed"; `shared/policies/review-scope.md`,
"Semantic change-implication reasoning"), so evaluating it never requires
opening `specialist-depth.md` itself. Across the three activation-relevant
live cases in #411:

- Case A (not needed): correctly did not activate; base reasoning alone
  caught the pinned defect.
- Case B (must activate): correctly activated; security deepening
  correctly identified the pinned vulnerability.
- The one ambiguous case (§5 below): correctly fell back to loading.

That is 3/3 correct routing decisions and exactly one observed
fallback-to-load, triggered exactly when the underlying signal was
genuinely ambiguous (not spuriously). Nothing in this evidence shows
*frequent* unwarranted fallback — but nothing in it establishes reliability
at any real scale either. A 3-case sample cannot distinguish "the
predicate is robust" from "the predicate has not yet been tested against
disagreement."

## 4. Did fail-closed behavior actually hold under test?

Yes, at two independent layers:

- **Text/manifest level** (#410):
  [`tests/policy/review/specialist_depth/test_specialist_depth_410.py`](../../tests/policy/review/specialist_depth/test_specialist_depth_410.py)
  pins the fail-closed contract in `specialist-depth.md` and
  `capability.yaml`.
- **Live-run level** (#411 §5): a genuinely ambiguous cardinality signal
  (a new per-order query with undocumented cardinality in either
  direction) produced a finding rather than silence, matching the
  fail-closed contract after the fixture was calibrated to the observed
  (not yet pinned) reviewer behavior.

Both layers agree, and the live-run layer is the first evidence that the
declared contract is not merely text-pinned but actually holds when
executed.

## 5. Did the manifest/resource ownership model stay understandable, or did it add orchestration complexity that outweighed what it removed?

Stayed understandable. `capabilities/specialist-depth/capability.yaml`
remains the thin, additive, build-time declaration §J.2 Step 1 designed it
to be. No new runtime orchestration component was introduced: the
activation predicate is one prose section in `review-scope.md` plus one
mirrored "Conditional loading: fail-closed" section in
`specialist-depth.md` — not a router, not a new service, not a new class
of file. `capability-architecture-model.md` §J.2 deliberately stopped
before Step 5 (kernel/router separation), which it rates as the
highest-risk step in the whole migration precisely because a router that
grows unbounded has already happened once (`review-scope.md` after #288).
Because that step was not attempted, this extraction cannot yet show
whether the model *stays* understandable as more capabilities are added —
only that it did for the first one, at the cost of exactly one
hand-authored predicate section and one manifest file.

## 6. Is specialist-depth representative enough of the other 12 capabilities to justify repeating the pattern as-is?

**No, and the model's own design record already says so.**
`capability-architecture-model.md` §J.2 chose `specialist-depth` first
*because* it is the easiest case, not because it is typical:

> `specialist-depth`: **never named by either `SKILL.md`; zero co-change
> among members; identical link signature; explicit pre-existing
> activation/composition contract; five dedicated corpora; a dedicated
> composition corpus (A–G) that tests the routing decision itself.** If
> this one cannot be extracted cleanly, the architecture is wrong — which
> is exactly what a first step should be able to tell you.

The same table names concrete reasons the other candidates are harder,
not merely different: `publication-github` touches the mutation/
authorization boundary ("the highest-consequence area in the
repository"); `runtime-execution`'s policy half is entangled with
`capability-posture` and needs a grant/deny split first; `conditional-
passes` has three different activation shapes and a policy with in-degree
7; `stateful-review` contains environment-neutral semantics owned
nowhere else, forcing an ownership decision mid-migration. `specialist-
depth` proving out cleanly tells us the *mechanism* (manifest + fail-
closed predicate + conditional load) works on the least-entangled
material available. It does not tell us the mechanism survives contact
with higher-coupling, higher-consequence, or ownership-ambiguous
capabilities — those are exactly the cases §J.2 named as harder before
this extraction ever ran.

## 7. Should future capability activation continue as hand-authored runtime policy mirrored by `capability.yaml`, or should the next migration step generate the runtime routing/predicate projection from the manifest?

**Continue the current pattern (hand-authored policy + manifest
mirroring) for the next extraction; do not generate a runtime projection
yet.** `capability-architecture-model.md`'s own migration sequence (§J.2)
already places "Step 5 — Kernel/router separation" *after* "Step 4 —
Measurement harness" and describes it as "highest risk of any step,"
explicitly because `review-scope.md` has already become an unbounded
router once (#288) and because Step 4's baseline is a precondition, not
an afterthought, for taking that risk. Only one capability has been
extracted so far — enough to prove the manifest/predicate/fail-closed
mechanism, not enough to design a generator against, since a generator
built from a population of one activation predicate risks encoding that
one predicate's shape as if it were general. Generating routing now would
repeat, in reverse, the exact mistake #412 exists to avoid: committing to
an architectural mechanism before evidence of its need exists. The
existing text-pinning/cross-check test
(`test_specialist_depth_410.py`) is a sufficient drift guard at today's
scale of one hand-authored predicate; it does not need to scale
indefinitely to be sufficient for the *next* single extraction, and
whether it remains sufficient at three or four extracted capabilities is
a question for a future checkpoint, not this one.

## 8. Decision

**Continue the specialist-depth extraction pattern — but for exactly one
more capability next, not a batch, and not yet with generated routing.**
This is option 1 of #412's required decision statement:

> Continue current pattern — hand-authored runtime policy remains
> acceptable and manifests remain mirrored declarations.

This decision is qualified by §6: because `specialist-depth` was
deliberately the easiest case, the justification for continuing is "the
mechanism worked on the case designed to prove it," not "the mechanism is
now validated for all thirteen capabilities." The next step should
therefore be sized to keep testing generalizability, not to capitalize on
a false sense of proof — one capability, benchmarked the same way #411
did, before any further batching.

### Next capability and issue structure

`capability-architecture-model.md` §J.2's own Step 6+ ordering names the
sequence explicitly: "`scale` → `context-resolution` → `remediation` →
`finding-placement` → …", and §L8 already classifies this group as
"contributor-owned, once L7 [`specialist-depth`] sets the pattern." `scale`
is the concrete next pick: it is first in that ordering, it is already a
declared dependency of `specialist-depth` itself ("`review-kernel`,
`finding-contract`, `scale` (for ring bounds)"), and its own capability
manifest (`capabilities/scale/capability.yaml`) already exists with a
threshold-gated activation predicate and two owned corpora
(`corpus/risk-depth/`, `corpus/repository-intelligence/`), unlike several
later capabilities in the ordering that still need a boundary split first
(`conditional-passes`, `runtime-execution`).

- **Extend #403**, do not open a new epic. #403 is already the parent of
  #408/#410/#411/#412, and §M.2's "one repository, no split" recommendation
  applies equally to issue structure: there is no new coordination surface
  this migration step needs that #403 does not already provide.
- **One new child issue of #403**, scoped to `scale` alone (mirroring
  #408→#410→#411's shape: baseline diff against this checkpoint's
  numbers, conditional-loading change, benchmark-backed proof) — not a
  combined issue for `scale` + `context-resolution` + `remediation`
  together. Batching those three into one issue would repeat the "one
  large, irreversible batch" failure mode #412's Problem statement names,
  just one level down from "all twelve capabilities" to "all three of
  L8's group."
- Per §L8, this next issue may be **contributor-owned** rather than
  maintainer-led, since `specialist-depth`'s extraction is the
  maintainer-led precedent L8 was waiting on. The concrete issue is not
  created here, per #412's Non-Goals.

## 9. Out of scope

- Creating the `scale` extraction issue itself (#412 Non-Goals).
- Re-litigating #410's fail-closed proof or #411's benchmark methodology —
  both are cited, not re-run.
- Designing the eventual router/generation mechanism (§J.2 Step 5) — this
  record only decides *when* to attempt it (not yet), not *how*.
- Re-scoring the other eleven capabilities named in §M.4 individually;
  §6 explains why `specialist-depth` cannot stand in for that analysis,
  not what each of the other eleven would individually require.

## Related

- [#403](https://github.com/amirbena/code-review-skill/issues/403) —
  parent epic this checkpoint's next-capability issue extends.
- [`capability-architecture-model.md`](capability-architecture-model.md)
  §J.2 (migration sequence), §K (risks and rollback), §L8 (follow-up
  issue breakdown), §M.4 (capabilities remaining to extract) — the design
  record this checkpoint applies without re-deriving.
- [`capability-loading-baseline.md`](capability-loading-baseline.md)
  (#408) — the pre-extraction baseline this checkpoint's §1 evidence is
  diffed against.
- [`specialist-depth-progressive-loading-proof.md`](specialist-depth-progressive-loading-proof.md)
  (#411) — the benchmark evidence this entire checkpoint is scoped to
  cite, per that document's own "Status and canonical home" section.
- [`shared/policies/specialist-depth.md`](../../shared/policies/specialist-depth.md),
  "Conditional loading: fail-closed" — the hand-authored activation
  contract §7 recommends continuing to mirror rather than generate, for
  now.
