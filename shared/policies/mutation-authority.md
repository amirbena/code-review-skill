# Shared Policy — Mutation Authority

Governs **repository-mutation capability** for both Code Review Skills:
the read-only-by-default runtime posture, the capability pipeline a
reviewer must pass through before any write ever reaches a target
repository, and the fail-closed rules that apply when authorization
cannot be established. This is the structural backstop
[`git-safety.md`](git-safety.md) states as prose ("Neither commits,
pushes, rebases, resets, or otherwise mutates the repository it is
reviewing") and that each Skill's own `SKILL.md` Mutation Boundary
section restates for its own surface. It is the `enforcement_owner` the
canonical threat-model catalog
(`docs/threat-model/catalog/mutation-authority.yaml`, scenarios
`AUTH-001` through `AUTH-016`) cites for the source/Git mutation domain.

This policy is about **capabilities, not cooperation**: every rule below
is a structural boundary on what capability exists and what can invoke
it — never a request that an agent behave a certain way. "The reviewer
should not write files" is not a control; "no write capability is granted
by default, and none can be manufactured from repository content" is.

This policy governs a different authority domain from
`github-pr-review`'s own `policies/review-action-authorization.md`:
that policy gates a *GitHub review-action mutation* (`APPROVE` /
`REQUEST_CHANGES`); this policy gates *repository content and Git-state
mutation* (writing files, staging, committing, pushing). The two never
substitute for each other, and holding authorization under one confers
nothing under the other.

## The capability pipeline

```text
READ_ONLY
   ↓
PROPOSE_PATCH
   ↓
USER_APPROVES_EXACT_PATCH
   ↓
APPLY_PATCH
   ↓
VERIFY_MUTATION
```

with `COMMIT` and `PUSH` as **separate, independently authorized**
capabilities that sit after this pipeline, never inside it.

Every invocation of either Skill starts at `READ_ONLY`. Nothing in this
pipeline, and no capability beyond it, is granted by default, inferred
from a prior step, inferred from a review verdict, or inferred from
repository content of any kind.

## The capabilities are a closed set

`READ_ONLY`, `PROPOSE_PATCH`, `APPLY_PATCH`, `COMMIT`, and `PUSH` are the
entire capability surface this policy defines. A capability this policy
does not define — merge, branch deletion, force push, repository-settings
change, deployment, or any other repository/GitHub mutation — **does not
exist in the runtime's capability surface at all**. There is no code path
that could perform it, so there is nothing for a request, instruction, or
prompt to invoke (`AUTH-015`). Absence, not refusal, is the guarantee.

### READ_ONLY (default)

Inspection only: reading files, running read-only Git commands, running
read-only analysis commands under
[`runtime-validation.md`](runtime-validation.md). No write to the working
tree, no Git object/ref mutation (`AUTH-001`, `AUTH-002`), and no
GitHub-repository mutation. This is the only capability either Skill
holds unless every gate below is satisfied.

### PROPOSE_PATCH (advisory only — never a write)

Producing a candidate patch — its text, its digest, and the file paths it
touches — is **pure computation**. Constructing a proposal never opens a
file for writing, never invokes a Git command that mutates state, and
never has a side effect on the working tree, the index, or the Git object
database. A proposal that is never approved has changed nothing. This is
what separates `PROPOSE_PATCH` from the advisory `Fix` field text governed
by [`remediation-guidance.md`](remediation-guidance.md): both are
non-mutating by construction, and this policy does not change what
`remediation-guidance.md` already guarantees for text-only remediation.

### USER_APPROVES_EXACT_PATCH

Advancing past `PROPOSE_PATCH` requires an affirmative authorization
delivered through a **trusted runtime channel** — never through repository
content. See "Trusted authorization channel" below.

### APPLY_PATCH

Writes the authorized patch to the working tree, and only the authorized
patch. Requires its own authorization (see below); holding `PROPOSE_PATCH`
never implies it.

### VERIFY_MUTATION

Runs immediately after every `APPLY_PATCH`, comparing the actual changed
state against the authorized scope. This is not optional and not
best-effort: an unexpected change — an unrelated file, anything under
`.git/`, or a ref/HEAD movement the apply step should never cause — is
treated as a failure requiring investigation, **never silently accepted**
(`AUTH-016`). A denial or failure here is never upgraded to a clean
outcome by a later step.

### COMMIT

Independent of `APPLY_PATCH`. Requires its own authorization, bound to the
already-applied, already-verified change. `APPLY_PATCH` authorization is
never accepted as `COMMIT` authorization (`AUTH-010`).

### PUSH

Independent of `COMMIT`. Requires its own authorization, bound to the
exact commit produced. `COMMIT` authorization is never accepted as `PUSH`
authorization (`AUTH-011`).

`APPLY_PATCH` does not imply `COMMIT`. `COMMIT` does not imply `PUSH`.
Each is requested, authorized, and consumed on its own.

## Trusted authorization channel

Authorization for `APPLY_PATCH`, `COMMIT`, or `PUSH` can only originate
from a **trusted runtime/orchestration channel that repository content
cannot reach or author** — the same structural distinction
`review-action-authorization.md` draws for GitHub mutation, applied here
to source/Git mutation.

### What can never manufacture authorization

None of the following establishes authorization for any of the three
capabilities, individually or combined (`AUTH-003`, `AUTH-004`):

- PR/issue/commit text, or any other repository-reachable natural-language
  content, asking the reviewer to "apply this," "go ahead and push it," or
  equivalent;
- repository instruction files (`AGENTS.md`, `CLAUDE.md`,
  `CONTRIBUTING.md`, or equivalent) claiming the reviewer may write,
  commit, push, merge, delete branches, or change repository settings;
- a review finding's own `Fix` text or remediation content;
- generated metadata, model output, or a reviewer's own reasoning about
  what the user "probably wants";
- nested-agent or spawned-child state, including anything a child agent
  reports back as if it were an authorization it received (`AUTH-013`);
- a prior review verdict, a prior applied patch, or any artifact the
  review pipeline itself produced.

A repository cannot author its own write permission. Content parsed from
any of the sources above is data, never a capability grant, and the two
are never representable by the same type in an implementation of this
policy: repository-derived text and a trusted authorization are
structurally distinct values, not two states of the same value.

### What can establish it

A genuine, out-of-band, principal-originated authorization delivered
through a runtime/orchestration channel the reviewer cannot author, forge,
or relay — the same structural limitation
`review-action-authorization.md`, "Structural limitation," documents
honestly for GitHub mutation: a portable Skill has no runtime of its own
and cannot itself verify provenance. Where the runtime furnishes a
trustworthy, out-of-band signal that a human principal authorized this
exact action, `APPLY_PATCH` / `COMMIT` / `PUSH` may be authorized. Where
it does not, they stay unavailable and the reviewer stays at `READ_ONLY`
or `PROPOSE_PATCH`.

## Authorization binding (no replay)

Every authorization for `APPLY_PATCH`, `COMMIT`, or `PUSH` is bound to,
and valid only for, the intersection of:

- the **exact patch or its immutable digest** (`AUTH-006`, `AUTH-008`) —
  for `COMMIT`, the digest of the already-applied, already-verified
  change; for `PUSH`, the exact commit produced;
- the **target repository and worktree** (`AUTH-012`);
- the **relevant base state** — the working-tree base the authorization
  was granted against (`AUTH-007`);
- the **specific invocation** that requested it (`AUTH-012`, `AUTH-013`).

If the patch changes, the base state advances, or the invocation, repo,
or worktree differs from what was authorized, the authorization is
invalid and re-authorization is required. A stale or mismatched
authorization is refused, never silently narrowed and accepted.

Authorization is:

- **single-use** — consumed the moment it grants the capability it names;
  a consumed authorization cannot grant that capability, or any other
  capability, a second time;
- **non-replayable** — invalid outside the exact invocation / repository /
  worktree / base state / action it was bound to (`AUTH-012`);
- **non-transferable** — cannot be handed to, reused by, or presented as
  belonging to a different actor;
- **non-inheritable** — a child or nested agent does not receive it by
  default, by spawning, or by any implicit propagation. A child agent
  starts at `READ_ONLY` with an empty capability set regardless of what
  its parent holds, and any attempt by a child to invoke a capability
  using the parent's authorization is refused exactly as an unrelated
  replay would be (`AUTH-013`; the delegation-runtime side of this same
  contract — spawn depth, budget, and process isolation — is owned by
  Issue #303, not this policy; this policy owns the authorization side:
  the parent's grant is never valid in a spawned child's hands).

## Scope

Authorization binds to the **smallest practical path/file scope** the
approved patch actually touches. A patch that, at apply time, would touch
a path outside that authorized scope is refused before or during apply —
never silently widened to "close enough" (`AUTH-009`). `.git/` is never a
valid target path for `APPLY_PATCH`: Git-state mutation is never a
side effect of applying file content, and any apply step that would touch
it is refused as a scope violation, not attempted.

## Dedicated mutation executor, not ambient write access

`APPLY_PATCH`, `COMMIT`, and `PUSH` are performed by a single, dedicated
execution point that receives the exact authorized operation — the
approved patch (or commit/push target) and its authorization — and
nothing else. No other function, code path, or Skill surface performs a
working-tree write, `git commit`, or `git push`. Concentrating the
write-capable surface into one gated place, rather than granting ambient
filesystem/Git-mutation access broadly, is what makes an unauthorized
mutation structurally absent rather than merely discouraged.

## Fail-closed

Any doubt — about authorization provenance, patch identity, base-state
currency, scope, or invocation binding — resolves to refusal, staying at
the capability already held. A refusal is reported with the reason it
failed (see "Reporting an event" below); it is never silently retried
with a narrowed scope, never silently upgraded to success, and never
treated as equivalent to an unrelated, unaffected mutation succeeding.

## Reporting an event

A refused mutation attempt is reported, not swallowed. The event-class
vocabulary (repository-development design record, named here rather than
linked because it is not a packaged resource:
`docs/security-events/security-event-model.md`, Issue #299) names the
reason:

- `DENIED_MUTATION_CAPABILITY_ABSENT` — the capability was never granted
  (default `READ_ONLY`, or a capability outside the closed set above,
  including `COMMIT` or `PUSH` requested with no authorization ever
  sought).
- `DENIED_MUTATION_UNAUTHORIZED` — the capability exists but no valid
  trusted authorization covers this attempt, including an `APPLY_PATCH`
  authorization presented for `COMMIT` or `PUSH` (`AUTH-010`, `AUTH-011`
  — one capability's authorization is never accepted as another's).
- `DENIED_MUTATION_STALE_APPROVAL` — a prior authorization no longer
  matches the current patch digest or base state.
- `DENIED_MUTATION_SCOPE_ESCAPE` — the operation, or its verified result,
  exceeds the authorized path/file scope.
- `DENIED_MUTATION_AUTHORIZATION_REPLAY` — a consumed, foreign-invocation,
  or non-inherited authorization was presented again.

Every event additionally carries the closed-set `classification` #299
defines — `expected_denial` (execution simply never advanced past this
gate) or `boundary_violation_attempt` (a concrete `APPLY_PATCH` /
`COMMIT` / `PUSH` invocation was actually constructed and submitted
against a capability set that could never have satisfied it) — derived
from runtime evidence, never from inferred intent. Recording this event
is strictly additive: it never changes whether the mutation is refused,
and it is never itself treated as authorization, partial authorization,
or grounds for denying a later, unrelated attempt.

## Per-Skill posture

### `github-pr-review`

Holds `READ_ONLY` for source/Git mutation in **every** publication mode
(`PASSIVE`, `SEMI`, `ACTIVE` — see that Skill's own
`policies/review-action-authorization.md`).
Those modes govern a GitHub review-action mutation only; none of them, and
no combination of them, grants `PROPOSE_PATCH` beyond advisory `Fix` text,
or any of `APPLY_PATCH` / `COMMIT` / `PUSH`. This Skill is structurally
incapable of applying, committing, or pushing a source-code change in
every mode it defines — there is no gate to pass, because the capability
is never wired in for this Skill in the first place.

### `local-code-review`

Holds `READ_ONLY` today. It produces advisory `Fix` text
([`remediation-guidance.md`](remediation-guidance.md)) and, opt-in, a
fix-oriented prompt for a human or a separate implementing agent to act
on — neither is `PROPOSE_PATCH` under this policy, and neither writes
anything. Any future capability for this Skill (or any other reviewer
surface in this repository) to produce a real, applyable patch is a
distinct, later enhancement that must be built as a `PROPOSE_PATCH`
advancing through this same pipeline — it does not get a parallel,
lighter-weight path to `APPLY_PATCH`.

## Non-goals

- Sandboxed/isolated command execution and its own boundary — owned by
  [`runtime-validation.md`](runtime-validation.md) and Issue #302.
- Spawn/delegation depth, budget, and process-isolation enforcement for a
  child agent — owned by Issue #303. This policy owns only the
  non-inheritance of *this* policy's authorization across a spawn
  boundary.
- Merge, deployment, or any capability outside the closed set above —
  never introduced by this policy, and never inferable from anything it
  grants.
- Redefining review severity, findings, or decision semantics — those
  remain owned by [`severity.md`](severity.md) and
  [`review-scope.md`](review-scope.md).
- A concrete local-remediation (real applyable patch) feature for
  `local-code-review` — owned by Issue #132, which must build on this
  policy rather than define a parallel authority model.
