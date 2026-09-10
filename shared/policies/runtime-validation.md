# Shared Policy — Runtime Validation

Applies identically to `local-code-review` and `github-pr-review` when the
reviewer considers running a repository-defined test, lint, or validation
command. This policy adds an evidence step to review; it does not create a
second review engine, a merge gate, or a mutation capability.

## Purpose and boundary

Runtime validation is optional, bounded evidence about the reviewed change.
The reviewer may execute a command only after resolving an exact command from
the target repository's existing instruction/task sources and applying the
gates below. The execution boundary is read-only with respect to the target
repository: it must not edit source files, create or alter Git state, call
GitHub write APIs, or perform another repository mutation. A command that
cannot be shown to meet that boundary is not run.

An isolated checkout by itself is not the required execution boundary. It is
repository context for review and may still share the reviewer's host
filesystem, credentials, network, or other ambient state. Repository
validation remains dormant and unavailable unless the consuming runtime can
separately establish and verify every required isolation property below.
The metadata capability value `conditional` describes this contract: it does
not imply that any current runtime supports live execution.

This policy does not authorize autofixes, CI orchestration, retries, matrix
execution, dependency installation, service startup, deployment, or any other
expansion of review scope. It authorizes exactly one narrow generation path —
the smallest targeted reproduction for a single suspected finding, under
"Targeted validation of a suspected finding" below — and that path is
disposable, boundary-bound, and can never become a repository change.

## Trust model and execution boundary

Runtime validation executes target-repository-controlled code. A command is
not safe merely because its name is conventional, it appears in `AGENTS.md`,
`CONTRIBUTING.md`, or task-runner configuration, it is described as a test,
lint, or validation task, or its visible argv is syntactically benign. A
declaration establishes **command-source trust** (where the command came
from); it does not establish **execution-payload trust** (what repository code
the command, hooks, dependencies, scripts, or subprocesses will execute).
The payload remains untrusted, including for `pytest`, `npm test`, `cargo
test`, `make test`, scripts, and task-runner aliases.

Consequently, static command screening is necessary but insufficient. A
selected command requires a disposable, bounded execution boundary before it
may start. The minimum boundary is:

- filesystem isolation from the reviewer host, with access limited to a
  bounded target checkout/work copy and explicitly required read-only inputs;
- no access to host secrets or credentials, including SSH agents, GitHub
  tokens, cloud credentials, browser/session data, home-directory secrets, or
  unrelated repositories;
- network denied by default, with no broad declared-command exception;
- no host Git/GitHub mutation capability, privilege escalation, or inherited
  mutation credentials;
- bounded non-interactive process, runtime, and resource limits;
- disposable execution state; and
- post-run verification that the reviewed source tree and Git state were not
  mutated outside explicitly allowed ephemeral outputs.

This is a policy contract, not a new container or CI platform. If the
reviewer's runtime has no existing abstraction that can establish and verify
this boundary, record the command as `unavailable` with the missing boundary
capability. If the boundary is present but cannot be established for this
command, record `skipped` with the concrete safety reason. Never fall back to
direct or unsandboxed host execution.

## Declaring and discovering commands

Reuse the target repository instruction hierarchy and applicable repository
context resolved by
[`repository-instructions.md`](repository-instructions.md). Read only the
relevant existing sources named by that hierarchy or by the changed area's
repository conventions: `AGENTS.md` / `CLAUDE.md`, contribution or validation
documentation, and an explicitly declared task-runner command. A declaration
must identify the exact command, its source location, and enough surrounding
context to judge what it does.

There is no new command-discovery mechanism here. Do not search arbitrary
scripts, package metadata, CI workflows, shell history, or tool caches to
invent a command. A familiar command name, a generic language convention, or
the presence of a test directory is not a declaration. If no trustworthy
command is declared, record a skipped validation with reason `no declared
command` and run nothing.

A declaration is not permission to run. Inspect the command and the narrow
referenced task definition/configuration needed to establish its behavior.
If that behavior or its safety cannot be established, record `skipped` with a
reason rather than guessing.

## Selection and scope

Use the blast-radius guidance in
[`review-scope.md`](review-scope.md) to choose the narrowest declared command
that exercises the changed behavior. A focused command is preferred over a
package- or repository-wide command. Select a broader command only when the
changed interface, shared policy, schema, build graph, or other concrete
blast-radius evidence justifies it, and record that justification.

Do not automatically add commands, expand a task into a matrix, retry a
command, or fall back to a broader command after a focused command fails or
is unavailable. A repository-declared command may itself run the repository's
documented suite; that is one declared command and must still pass the safety
gates. Every command selected for consideration receives one visible outcome
record.

## Safety gate

Run a selected command only when all of the following are established:

- it is the exact command declared by an applicable target-repository source;
- the required disposable execution boundary above is established before
  process start, and the target payload is treated as untrusted;
- its relevant task definition and configuration can be inspected without
  executing repository code first;
- the isolated invocation reads the reviewed work copy and produces no source,
  generated-file, cache, Git, GitHub, deployment, or other target-repository
  mutation outside explicitly allowed disposable state;
- the isolated invocation has no secret, credential, approval, external
  service, network access, daemon, database, cloud resource, or other
  unavailable external state; and
- the boundary's runner invokes it in a bounded, non-interactive way without
  shell evaluation of untrusted text or hooks.

Skip and record a reason when a command is destructive or side-effecting
(including autofix, format, repair, clean, reset, migration, install,
publish, deploy, or write-capable task variants), secret-dependent,
service-dependent, network/external-dependent, interactive, or otherwise not
provably read-only. A command that may write caches or artifacts in the target
tree is unsafe unless the declaration and invocation explicitly keep those
writes outside the tree and the runner can verify that boundary. Do not rely
on a command's name alone, and do not run a command merely to learn whether it
is safe.

If a safe declared command cannot be started because its executable,
dependency, interpreter, or required local capability is unavailable, record
`unavailable` and the concrete missing capability. `unavailable` is not
`skipped` and neither is a pass.

If the required sandbox/isolated execution boundary is unavailable, record
`unavailable` with that safety reason. If a command's boundary cannot be
verified, record `skipped` with that safety reason. In both cases, do not
attempt the command unsandboxed.

## Outcome contract

The shared `Validation` section records one entry for every selected command
or explicit no-command result. Each entry contains the exact command, its
declaration source, scope/justification, and exactly one of these outcomes:

- `executed` — the command started and completed successfully (include the
  observed exit status and bounded output evidence);
- `failed` — the command started but completed unsuccessfully (include the
  observed exit status and bounded failure evidence);
- `skipped` — the command was not started because a declaration, scope, or
  safety gate was not satisfied (include the reason); or
- `unavailable` — the safe command could not start because a required local
  capability was missing (include the reason).

Do not collapse `skipped`, `failed`, or `unavailable` into “not run,” and do
not represent any non-execution outcome as passing. If no command is
declared, the report must say so explicitly. Validation output is evidence,
not an assertion that the reviewed behavior is correct.

## Findings and decision semantics

A successful validation run adds evidence only; it never removes, suppresses,
downgrades, or mechanically rewrites an existing finding. A failed run is
finding material when it is attributable to the reviewed change: surface the
failure and classify its severity from impact under
[`severity.md`](severity.md), not from the exit code, command category, or a
repository convention. Skipped and unavailable outcomes remain explicit
validation evidence with their reasons; they never become an implicit pass.

Finalize the complete finding set, including any validation finding material,
then derive the existing review decision exactly once through
[`severity.md`](severity.md). Runtime validation cannot create a second
decision path, change the `REVIEW CLEAN` / `CHANGES REQUIRED` or
`Approve` / `Request Changes` mapping, or authorize a Git/GitHub action.

## Targeted validation of a suspected finding

The sections above cover **repository-declared commands** as general evidence
about the change. This section covers a second, narrower mode: gaining
**runtime evidence for one specific suspected finding** by running the
smallest safe reproduction of it. Both modes share the same trust model,
execution boundary, and safety gate above; nothing here relaxes them.

Targeted validation is **never mandatory**. A finding that already rests on
sufficient static evidence per [`evidence.md`](evidence.md) is complete
without it, and the absence, unavailability, or inconclusiveness of a
targeted run never blocks, downgrades, or weakens such a finding.

### Eligibility

Eligibility is about the **finding and its reproduction**, not about whether a
runtime can execute it. Consider targeted validation for a finding only when
**all** hold:

- the finding is a **suspected** defect whose correctness genuinely hinges
  on runtime behavior that static reasoning left uncertain — not a finding
  already confidently established, and not a stylistic or structural
  observation;
- the smallest reproduction is a **bounded, deterministic, non-interactive**
  check whose pass/fail cleanly distinguishes "defect real" from "code
  correct";
- it needs no capability the isolated boundary lacks — no network, secrets,
  services, additional dependency installation, or external state beyond a
  focused check already running against the reviewed work copy.

If any of these fails, the finding was never a candidate for a targeted run:
do not attempt one, and it keeps state `reasoned` (see "Finding validation
state").

Boundary availability is a **separate** gate applied only to an eligible
finding: when the disposable execution boundary in "Trust model and execution
boundary" cannot be established or post-run verified for this run, that is not
an eligibility failure — the finding was a genuine candidate, so it is
recorded `attempted-inconclusive` per "Budget and fail-safe", never
`reasoned`.

### Selecting or generating the smallest reproduction

Prefer **selecting an existing repository test** that already exercises the
suspected path over generating anything. Generate a reproduction only when no
existing test isolates the behavior, and then keep it **minimal**: a single
focused test or script, self-contained, deterministic, asserting exactly the
one behavior in question, with no repository-convention side effects (no new
fixtures in the tree, no config edits, no broad harness). One reproduction
per finding; do not expand it into a matrix or retry it after a clean or
inconclusive result.

### Generated artifacts never enter the working tree

A generated reproduction exists **only inside the disposable boundary's
ephemeral workspace**. It is never written into the reviewed work copy,
never `git add`-ed, staged, committed, stashed, or otherwise placed in the
target repository's Git state, and never emitted as a review artifact the
caller could mistake for a proposed patch. The post-run verification already
required by the safety gate must additionally confirm that **no generated
validation file, and no modification from the run, remains in the reviewed
source tree or Git state**. If that cannot be verified, the boundary is
treated as breached: discard the result and record the finding as
`attempted-inconclusive` with that reason. The reproduction's *content* may
be summarized in the validation evidence as text; it is never delivered as an
applyable change.

### Budget and fail-safe

Every targeted run has a strict wall-clock timeout and the bounded resource
ceiling from the execution boundary. A run that exceeds either is terminated
and recorded `attempted-inconclusive` with reason `budget exceeded`. Likewise
record `attempted-inconclusive` when the boundary is unavailable or
unverifiable, the reproduction cannot be made safe, or the observed result
neither confirms nor disproves the suspicion. In every one of these cases the
finding keeps its static evidence and remains valid. Never widen the budget,
retry, or fall back to unsandboxed execution to force a conclusive result.

### Finding validation state

Every finding carries exactly one **validation state**, surfaced on the
finding per [`../templates/finding.md`](../templates/finding.md):

- `reasoned` — no targeted validation was attempted, or the finding was
  ineligible; it rests on static evidence alone. This is the default and is
  always sufficient.
- `runtime-confirmed` — a targeted reproduction ran inside the boundary and
  its pass/fail evidence **confirms** the suspected defect (the reproduction
  failed exactly as the finding predicts, or a disproof-style check
  demonstrated the incorrect behavior). Include the bounded run evidence.
- `attempted-inconclusive` — a targeted reproduction was attempted but did
  not yield a confirmation: boundary unavailable or unverifiable, budget
  exceeded, unsafe to run, artifact-leak check failed, or an ambiguous
  result. Include what was attempted and why it was inconclusive.

When a targeted run instead **disproves** the suspicion — the reproduction
passes, showing the code behaves correctly — the finding is **not raised**;
record the run and its pass evidence in the shared `Validation` section so
the disproof is visible. Any residual, independently evidenced concern is a
separate finding in state `reasoned`.

The validation state is **provenance, not a severity input**. It never
raises, lowers, or overrides the severity derived from impact per
[`severity.md`](severity.md), never changes a finding's identity or
deduplication, and never creates a second decision path. `runtime-confirmed`
does not escalate a P2; `attempted-inconclusive` does not de-escalate a P1.
Severity and the `REVIEW CLEAN` / `CHANGES REQUIRED` (or `Approve` /
`Request Changes`) mapping are derived exactly once, after findings are
finalized, exactly as they would be without any targeted run.

This state is the runtime-specific input to the finding's single unified
`confidence` value per [`../templates/finding.md`](../templates/finding.md),
"Confidence and evidence state": `runtime-confirmed` rolls up as `confirmed`
and `attempted-inconclusive` as `runtime-validation-unavailable`, alongside
the contextual-evidence provenance. The unified value is likewise provenance
only — it never lowers the evidence bar, the severity, or the decision. The
closed value set and its derivation are the finding-confidence model
(a repository-development design record, named here rather than linked
because it is not a packaged resource).

### Outcome recording

Each attempted targeted validation also produces one entry in the shared
`Validation` section, using the same `executed` / `failed` / `skipped` /
`unavailable` vocabulary as a declared command, plus the finding id it
targeted and the resulting finding validation state. A disproving run is
recorded there even though it raises no finding. `skipped` and `unavailable`
targeted attempts are never represented as passing and never silently
dropped.

## Where this runs in the review flow

After target-repository instruction discovery and before findings are
finalized, each Skill's runbook resolves this policy, optionally performs the
bounded declared-command validation and any eligible targeted per-finding
validation, and carries its outcome records into the shared
[`review-summary.md`](../templates/review-summary.md) `Validation` section.
Targeted validation runs against suspected findings as they are formed and
before the finding set is finalized, so each finding carries its validation
state into the finalized set; it never runs after the decision is derived.
