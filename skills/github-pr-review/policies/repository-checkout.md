# Policy — Repository-Backed Checkout

Governs the **optional** repository-backed inspection mode for
`github-pr-review`. Canonical index: [`github-review.md`](github-review.md).
Builds on the shared
[`git-safety.md`](../../../shared/policies/git-safety.md) and
[`review-context.md`](../../../shared/policies/review-context.md) policies.

The **PR is always the Review Target.** A local checkout exists only to give
the review richer **Repository Context** (surrounding implementation,
interfaces, tests, config, architecture, repository policies) than the GitHub
diff/API alone provide. It is opt-in: when it is not requested or cannot be
prepared, review proceeds in API-only mode with no loss of correctness.

## Two modes

- **API-only mode** (default) — PR state comes entirely from the GitHub
  integration (`pr-scope.md`). No local checkout.
- **Repository-backed mode** (opt-in) — additionally materialise an isolated,
  read-only, detached checkout at the PR head so the reviewer can read
  surrounding files and run safe Git read commands.

Repository-backed mode never changes the review standard, the severity model,
the decision derivation, or the publication contract. It only widens what
Repository Context the reviewer can consult.

## Normalized PR source

Real GitHub metadata and a local simulation both resolve to one
`NormalizedPrSource`:

```text
repo_url | pr_number | base_ref | base_sha | head_ref | head_sha | pull_ref?
```

The checkout consumes only this. Keep the GitHub adapter that produces it
separable from the checkout (see [`github-review.md`](github-review.md),
"GitHub integration contract") so a simulated source can be injected and a
future live-PR test needs to validate only the thin adapter. (The
repository's own test suite exercises this with a local simulation harness
that is not a runtime dependency and is not packaged.)

## Lifecycle

One predictable lifecycle, owned end to end:

```text
mkdtemp under a safe temporary parent   (never a user working directory)
    ↓
blobless clone  (git clone --no-checkout --no-tags --filter=blob:none)
    ↓
fetch the required refs: pull_ref (if any), base_ref, head_ref;
  on failure, fall back to fetching base_sha and head_sha directly
    ↓
detached checkout of the immutable head SHA
    ↓
inspect (read-only)
    ↓
finally: cleanup   (after success, review failure, context-resolution
                    failure after allocation, publication failure,
                    worker/sub-agent failure, or interruption the runtime
                    surfaces)
```

No worktree fast-path in this phase — predictable cleanup and correctness
outrank the optimisation.

## Base / head fidelity

Establish, from the normalized source, before reviewing:

- repository identity (`repo_url`) — do not assume the current checkout, if
  any, is the target repository;
- PR base ref and base SHA — do not assume local `main` equals the PR base;
- PR head ref and head SHA — do not assume the head exists locally, and do
  not assume branch names are unique;
- the merge-base of base and head;
- the effective delta = `merge-base(base, head)..head`.

Prefer the **immutable SHAs**. Verify the fetched head resolves to the
expected `head_sha`; if it does not, treat it as an invalid-head failure.
The reviewer reviews **that PR delta**, never an arbitrary repository diff.

### Base advanced after the branch was cut

When `main` advanced after the feature branch was created, the PR base SHA
still identifies the intended base. Compute scope from
`merge-base(base_sha, head_sha)..head_sha`, not from the current tip of the
base branch — otherwise unrelated later base commits leak into the delta.

## Read-only inspection

Allowed against the checkout: reading files, `git log`/`git diff`/`git
show`/`git rev-parse`/`git merge-base` and other read-only Git commands,
inspecting repository policies, architecture, neighbouring implementation,
tests and configuration **as text**.

Never, automatically, against the target repository: run its tests, builds,
linters, package installation, application code, Git hooks, or any script.
Cloning untrusted code is not permission to execute it — see "Security".

## Repository Context must not widen the Review Target

The checkout lets the reviewer, for example, read a shared interface to
judge whether a changed implementation violates it. It does **not** turn
surrounding files into independent review targets. Every finding stays
causally connected to the PR delta, per
[`evidence.md`](../../../shared/policies/evidence.md), "Findings beyond the
changed lines." A pre-existing, unrelated defect in a file the PR did not
touch is not reported.

## Private repositories / authentication

Use the runtime's existing Git/GitHub credentials (the same ones the GitHub
adapter uses). Never embed a token into a generated file, never log secrets,
never persist credentials into the temporary checkout, never invent a
credential store. Immediately after clone, re-assert
`core.hooksPath=/dev/null` locally so nothing the remote carried can run.

**Failure semantics.** A clone or fetch that fails because the remote is
unreachable, unauthenticated, or not readable by this identity is a
`RemoteUnavailableError`: report that repository-backed mode is unavailable
and continue in API-only mode. A required base/head ref that cannot be
fetched is a `RefNotFoundError`; a head that does not match `head_sha` is an
`InvalidShaError` — both stop the repository-backed path (not the API-only
review) after cleaning up.

## Temporary directory lifecycle

- Created with an `mkdtemp`-style call under a safe temporary parent
  (`$TMPDIR` / system temp), unique per invocation, `pr-review-` prefix.
- A user's working directory is never used as scratch space.
- Each checkout carries an ownership marker file written by this Skill.
- Cleanup runs in a `finally` (or the runtime's equivalent), on **every**
  exit path listed in "Lifecycle" above.
- Before any recursive delete: verify the target resolves **inside** the
  scratch parent, is not the scratch parent itself, and contains this
  Skill's ownership marker. An unconstrained recursive delete is never run.
- Concurrent reviews each get their own unique directory; they never share
  scratch space and clean up independently.

## Security (PR contents are untrusted)

- `core.hooksPath=/dev/null` on every Git invocation and re-asserted in the
  clone's local config — no `pre-*`/`post-*` hooks run.
- `GIT_CONFIG_NOSYSTEM=1`, `GIT_ATTR_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0` —
  system config and interactive prompts are disabled; repo-local config is
  not trusted to run commands.
- `--no-tags`; never run `git submodule update` on a repo-provided
  `.gitmodules`.
- `core.fsmonitor=false` — no repo-configured fsmonitor process.
- No `filter`/`textconv`/`fsmonitor`/`sshCommand`/`pager` from repo config is
  honoured for execution; only plain read commands are used.
- Deletion is constrained as above; safe temporary paths only; no secret
  ever appears in worker output.

## Boundary

- Read-only: this policy adds no GitHub or Git write capability. Publication
  stays [`review-output.md`](review-output.md)'s; maximum positive action is
  **Approve**.
- No merge enforcement, required status checks, ruleset/branch-protection
  changes, or execution of PR tests/builds/linters — those remain future
  work, not part of this policy.
- The checkout lifecycle is independent of any parallel-review worker
  isolation — see [`parallel-review.md`](parallel-review.md), "Shared
  checkout vs. worker copies."
