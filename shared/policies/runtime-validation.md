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

This policy does not authorize autofixes, generated reproductions, CI
orchestration, retries, matrix execution, dependency installation, service
startup, deployment, or any other expansion of review scope.

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

## Where this runs in the review flow

After target-repository instruction discovery and before findings are
finalized, each Skill's runbook resolves this policy, optionally performs the
bounded validation, and carries its outcome records into the shared
[`review-summary.md`](../templates/review-summary.md) `Validation` section.
