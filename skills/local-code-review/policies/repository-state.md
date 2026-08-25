# Policy — Repository State Categories and Staged Delta Fingerprint

This Skill's own policy defining the explicit Git state categories that
make up "the local implementation state," how each is detected, and the
staged-delta fingerprint used to distinguish an unchanged staged delta
from a new one across separately-approved re-review invocations. This
file is the single canonical owner of these definitions; the Skill's own
[`../SKILL.md`](../SKILL.md) and
[`../runbooks/local-review.md`](../runbooks/local-review.md) state the
concise behavioral consequence and reference this file rather than
redefining it.

## Why explicit categories, not "relevant files"

"All relevant files" is not a Git state — it conflates several
distinct, independently detectable categories that behave differently
and require different handling. Treating them as interchangeable makes
it impossible to say precisely where a finding came from, and makes
re-review comparisons unreliable. This Skill instead distinguishes:

- **Committed** — changes already present in commits relative to the
  chosen review base; part of the repository's commit history.
- **Staged** — tracked changes currently in the index (`git add`ed) and
  not yet committed.
- **Unstaged** — tracked working-tree changes not present in the index.
- **Tracked** — files already known to Git (present in the index or a
  commit).
- **Untracked** — files present in the working tree but not yet tracked
  by Git.

Staged and Unstaged are about *where a tracked change currently lives*
(index vs. working tree); Tracked and Untracked are about *whether Git
knows about the file at all*. A file can be tracked-and-unstaged,
tracked-and-staged, or untracked — these are not synonyms, and an
untracked file has no staged/unstaged distinction until it is added.

## Detection commands per category

Each category has its own explicit, narrow command — never one broad
command whose output mixes categories without attribution:

| Category | Detection command |
|---|---|
| Committed delta relative to base | `git log <base>..HEAD --oneline` (commits); `git diff <base>...HEAD` (content; files: `git diff --name-status <base>...HEAD`) |
| Staged tracked delta | `git diff --cached` (files: `git diff --cached --name-status`); fingerprint source: `git diff --cached --raw -M -z` (see "Staged delta fingerprint" below) |
| Unstaged tracked delta | `git diff` (working tree vs. index; files: `git diff --name-status`) |
| Untracked files | `git ls-files --others --exclude-standard` |
| Tracked vs. untracked, at a glance | `git status --porcelain=v1` (informational grouping only — never the sole source for any one category's detailed delta; use the dedicated command above for that category's actual content) |

Running one broad status/diff command to eyeball the repository is fine
for orientation, but the delta actually reviewed, and the delta a
finding is attributed to, must come from the category-specific command
above — never from an undifferentiated blend.

## Committed delta is not push status

`<base>..HEAD` (and `<base>...HEAD`) measures commits/content relative
to the **review base** (e.g. `main`) — this says nothing about whether
those commits have been pushed to a remote. Do not describe `<base>..HEAD`
output as "local-only" or "not yet pushed": once a branch has been
pushed at all, `<base>..HEAD` still returns every commit unique to the
branch, including ones that already exist on the remote, which would
mislabel already-public commits as unpushed. Push/synchronization status
is a distinct concern — see "Push / synchronization status" below, this
policy's single source of truth for it; the runbook only says when in the
execution order it is resolved.

## Push / synchronization status

Resolved against the branch's own configured upstream, never against the
review base:

```text
git log @{u}..HEAD --oneline
```

(local-only, unpushed commits) and

```text
git log HEAD..@{u} --oneline
```

(remote-only commits not yet merged locally), or the equivalent
ahead/behind counts. If the branch has no configured upstream (resolving
`@{u}` fails), report "no tracking branch configured" explicitly — never
guess or substitute an assumed `origin/<branch>` ref, since no such remote
tracking relationship may actually exist. This is informational for the
report and the caller, not a decision this Skill makes on its own, and it
is not a sixth repository-state category alongside
Committed/Staged/Unstaged/Tracked/Untracked above — it is the "Committed
delta is not push status" distinction made operational.

## Attribution in findings

A finding must identify which category its evidence came from —
committed, staged, unstaged, or untracked — so the report can say
precisely where it originated, not merely that "something changed." See
[`../templates/local-review-report.md`](../templates/local-review-report.md).

## Staged delta fingerprint

For the **staged** category specifically, this Skill computes a stable,
deterministic fingerprint so a caller can tell, across two separately
user-approved invocations, whether the staged delta actually changed.

**Command (exact, byte-for-byte):**

```text
git diff --cached --raw -M -z
```

- `--cached` scopes the diff to the index (staged content) only —
  never unstaged or untracked state.
- `--raw` produces machine-oriented per-path change records (mode,
  blob SHAs, status, path), not a human-readable patch — filenames
  alone are not sufficient input; the raw record set is.
- `-M` enables rename detection, so a staged rename changes the raw
  record set (and therefore the fingerprint) the same way any other
  staged content change does.
- `-z` NUL-delimits records instead of newline-delimited text. This is
  load-bearing: paths may themselves contain characters that would be
  ambiguous in newline-delimited output. The fingerprint is computed
  over the **exact raw bytes** this command writes to stdout — do not
  decode/re-encode, strip or convert the NUL separators to newlines, or
  otherwise transform the output before hashing. Any such transform
  changes what the fingerprint represents.

**Fingerprint algorithm:**

```text
fingerprint = SHA-256(exact raw stdout bytes of `git diff --cached --raw -M -z`)
```

SHA-256 is used because it is a deterministic, collision-resistant,
widely available hash with no dependency beyond the standard library in
any common runtime. A repository with nothing staged produces empty raw
output, whose SHA-256 fingerprint is the well-known hash of the empty
byte string — this is a valid, stable fingerprint for "nothing staged,"
not an error.

A reference implementation used for deterministic testing lives in this
source repository at `scripts/staged_fingerprint.py` (not part of either
packaged Skill archive, and not linked here for that reason — the Skills
reason from this policy text directly, not from that script).

## Fingerprint scope and re-review comparison

The fingerprint represents **only the staged category's content** at the
moment it was computed — it carries no information about whether the
*review standard applied to that content* is also unchanged. This policy
is the single canonical owner of the complete fingerprint-comparison
contract, including the precondition below; the runbook only says when in
the execution order a re-review applies it.

### Precondition: the applicable review standard must be unchanged

A matching content fingerprint is **not by itself** sufficient to reuse
prior reasoning. Before comparing fingerprints at all, the
caller/orchestrator must first establish that everything this Skill's
review reasoning actually depends on is materially unchanged since the
prior review whose fingerprint is being compared against: this Skill's own
[`../SKILL.md`](../SKILL.md); the runbook
([`../runbooks/local-review.md`](../runbooks/local-review.md)); this
Skill's own policies
([`invocation-approval.md`](invocation-approval.md),
this file, and, when applicable, [`review-context.md`](review-context.md)
and [`pr-context.md`](pr-context.md)); the shared review policies
([`review-scope.md`](../../../shared/policies/review-scope.md),
[`severity.md`](../../../shared/policies/severity.md),
[`evidence.md`](../../../shared/policies/evidence.md),
[`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
[`git-safety.md`](../../../shared/policies/git-safety.md),
[`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
and, in orchestrated/multi-Agent contexts,
[`review-ownership.md`](../../../shared/policies/review-ownership.md)); and
the target repository's own applicable instructions (`AGENTS.md`,
`CLAUDE.md`, and any other repository-local context discovered for the
files in the staged category).

This does not require a new persisted cryptographic fingerprint over those
files — establishing "materially unchanged" is the caller's/
orchestrator's responsibility (for example, because nothing in this list
was touched between the two invocations in the same session/task, or
because the caller has otherwise confirmed their content is identical). If
any of these materially changed, or the caller cannot confirm they did
not, the short-circuit below **does not apply**: treat the staged category
as requiring fresh reasoning under the current standard, exactly as if the
fingerprint had not matched, regardless of what the content fingerprint
alone reports. This precondition never narrows what the runbook's review
steps otherwise require, and never substitutes for re-verifying previously
reported blocking findings, discovering new P0/P1s, or independently
(re-)detecting unstaged/untracked state.

### Comparison, given the precondition holds

- **Same fingerprint as the previously reported one** → this is a safe,
  testable short-circuit: skip re-deriving review reasoning for the
  staged category from scratch, and instead spend that effort verifying
  whether each previously reported blocking finding in the staged delta
  was actually resolved. This never shrinks scope — the staged category
  is still fully accounted for in the report, and a newly discovered
  P0/P1 in that same staged delta (found while verifying) is still
  reported.
- **Different fingerprint** → the staged delta changed and must be
  reviewed as new delta, same as any other newly detected content.
- **Precondition not established** → treat this exactly as a fingerprint
  difference: review the staged category as new content under the
  current standard, regardless of what the content fingerprint itself
  reports.

**The fingerprint must never be used to conclude that unstaged or
untracked state is unchanged.** It carries no information about those
categories. Unstaged and untracked state must be (re-)detected on every
invocation using their own commands above, independently of whatever the
staged fingerprint says. An unchanged staged fingerprint alongside
changed unstaged or untracked content is a normal, expected combination
— report it as such, not as "no changes."

This Skill remains stateless (see
[`../SKILL.md`](../SKILL.md), "Statelessness and Orchestration
Boundary"): it does not itself remember a fingerprint from a prior
invocation. It computes and reports the current fingerprint every time;
comparing it against a previously reported value (when the caller
supplies that prior value as context for a re-review) is the caller's/
orchestrator's use of the report, the same way prior blocking findings
are already carried forward as re-review context.
