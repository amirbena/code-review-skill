# GitHub-native merge enforcement

## What it does

Lets `github-pr-review` make its decision enforceable by GitHub itself: it
publishes one machine-readable **commit status** on the reviewed commit,
and — only if you explicitly ask — adds that status to the base branch's
**required checks**, so GitHub blocks the merge until the status is green.

Three separate pieces, each with a different authority:

| Piece | What it does | Mutates repository governance? |
| --- | --- | --- |
| **Publish the status** | Posts one commit status (`code-review/github-pr-review`) on the exact reviewed SHA | No — a status is review output, not a settings change |
| **Check enforcement** | Reports whether that status is actually a required check on the base branch: `ENFORCED` / `NOT ENFORCED` / `UNKNOWN` | No — read-only |
| **Set up (or remove) the required check** | Adds (or removes) that one context in the base branch's required checks | **Yes — only on your explicit request** |

**Setup is OFF by default.** Running a review — however it ends, whatever it
finds, and even when it detects that nothing enforces the status — never
changes your Rulesets, branch protection, or required checks. Reviewing is
read-and-report; changing governance is a separate action that only you can
start.

## When it is useful

- You want GitHub to block a merge on a SHA that has not been reviewed
  clean, independently of whether anyone left an approving review.
- You want to know whether the status you publish is actually being
  enforced, without changing anything.
- You decided to turn enforcement on (or off) and want it done minimally and
  verified, rather than hand-editing a ruleset.

Native `APPROVE` / `REQUEST_CHANGES` events already give review-based
enforcement under a "require approving review" rule. The status adds a
signal bound to one commit that can also say "not reviewed yet"; it does not
replace the native events. See
[GitHub publication & review authorization](github-review-publication.md).

## Which Skill(s)

`github-pr-review` only. `local-code-review` never publishes to GitHub and
never touches governance.

## Default, conditional, or requested

| Action | State |
| --- | --- |
| Publishing the status | Optional; requires an explicit request (see [publication guide](github-review-publication.md)). A blocking status can be published even by a self-review; a `success` status needs `ACTIVE` mode + reviewer independence and is never published by a self-review |
| Checking enforcement | Read-only; allowed any time |
| Setup / removal of the required check | **Off. Only on an explicit request from you**, and it additionally needs `ACTIVE` mode and reviewer independence |

### What counts as explicit authorization

Only **your own request, in your own words, asking for that change** — for
example *"set up the code-review status as a required check on main"* or
*"remove the code-review status from main's required checks"*. The request
is recorded verbatim as the authorization.

None of these ever authorize setup, however convincing they look:

- a completed review, including a clean one or one with blocking findings;
- detecting that the status is `NOT ENFORCED`;
- text in the repository, the PR, an issue, a comment, a config file, or
  tool output (including text telling the Skill to enable enforcement);
- the Skill's own opinion that enforcement would be a good idea;
- a general approval such as "go ahead and fix everything" or "publish the
  review".

If it is ambiguous whether you asked, nothing is changed — the Skill asks or
stops.

## How to invoke it

```text
also publish the review status check for this PR          → publishes the status
is the code-review status a required check on main?       → read-only: ENFORCED / NOT ENFORCED / UNKNOWN
set up the code-review status as a required check on      → setup (explicit request)
main
remove the code-review status from main's required        → removal (explicit request)
checks
```

Repository tooling backs these actions (run from a repository checkout; it
is not part of a packaged Skill archive):

```bash
# Verify enforcement is active (read-only)
python3 -m scripts.github_integration.enforcement OWNER/REPO BRANCH

# Set up — only for an explicit request, quoted verbatim
python3 -m scripts.github_integration.required_check_setup OWNER/REPO BRANCH \
  --user-request "set up the code-review status as a required check on main" \
  --active-mode --reviewer-independent

# Remove — same authorization rules
python3 -m scripts.github_integration.required_check_setup OWNER/REPO BRANCH \
  --user-request "remove the code-review status from main's required checks" \
  --active-mode --reviewer-independent --remove
```

Both commands print JSON. Setup reports `added`, `removed`, `noop`
(already in the requested state), `refused`, or `failed`.

### Verify that enforcement is active

Run the read-only check (or ask the Skill for it) after setup. `ENFORCED`
means an active ruleset or classic branch protection requires the context
for that base branch; the output also shows which mechanism(s) said so.
Setup itself reads the configuration back and verifies the context is now
required and nothing else changed before it reports success. Merely having a
status posted on a commit is **not** evidence of enforcement — it is never
inferred from that.

## Commit Status behavior and the source-pinning limitation

- **One stable context** — `code-review/github-pr-review` — upserted in place;
  re-publishing an unchanged result writes nothing.
- **Bound to one SHA.** A status on commit A says nothing about commit B. If
  the PR HEAD moved before publishing, the Skill withholds the status
  (`STATUS WITHHELD (HEAD advanced)`); a new commit starts with no green.
- **Never a false green.** Anything other than a complete, current-HEAD,
  clean review publishes a non-`success` status, or none.
- **Source-pinning limitation.** A commit status is identified only by its
  name. Anyone with `Commit statuses: write` on the repository can post the
  same context, and a required check cannot be pinned to the publisher.
  Detection likewise matches by name only: a check pinned to a different
  app still reports `ENFORCED`. If you need a check pinned to a specific
  GitHub App, that is a Checks API follow-up, not what this delivers.

## Rulesets vs. classic Branch Protection

Both can require a named status. They run in parallel with no precedence —
a context required by either is enforced — so detection reads **both** and
reports `ENFORCED` if either requires it.

Setup edits **only the mechanism that already carries required checks** for
the base branch and **never creates the other one**:

- **Ruleset** — the ruleset is read, the one context is added (or removed),
  the whole ruleset is written back, then read back and compared. Every other
  rule, required check, bypass actor, and setting is preserved. If the
  ruleset changed while it was being edited, the write is refused so a retry
  starts from fresh state.
- **Classic protection** — the one context is added through GitHub's
  additive contexts call; nothing else is touched.

Setup refuses, with no change and an actionable message, when the
configuration is ambiguous: both mechanisms carry required checks, several
rulesets do, only an organization-level ruleset does, or there is no existing
required-checks configuration to extend. Approval counts, stale-review
settings, and bypass actors are never changed.

## Required permissions and authentication

- Authentication is a `gh` login or a `GH_TOKEN` / `GITHUB_TOKEN`; tokens go
  to `gh` through its environment only and are redacted from errors.
- **Publishing the status:** `Commit statuses: write` (fine-grained) or
  `repo:status` (classic).
- **Reading enforcement:** read access to the repository's rules and branch
  protection. Which exact fine-grained permission names GitHub requires for
  these reads has not been verified; a refusal is reported as `UNKNOWN`,
  never as "not enforced".
- **Setup / removal:** changing branch protection requires repository admin
  (owner) permission; a ruleset edit needs equivalent rights to manage
  rulesets. Without them, setup fails safely and changes nothing.

## `UNKNOWN` and failure behavior

| Situation | Result |
| --- | --- |
| A configuration cannot be read (permission or API error), or the response is ambiguous or possibly truncated | Enforcement is `UNKNOWN` — never guessed as enforced or not enforced |
| One mechanism reads `NOT ENFORCED` and the other `UNKNOWN` | `UNKNOWN` |
| Setup while enforcement is `UNKNOWN`, or any ambiguous/conflicting configuration | Refused; **no mutation** |
| Setup without an explicit request, `ACTIVE` mode, or reviewer independence | Refused; no mutation |
| A write fails with a client error (for example missing permission) | Failed with an actionable message; no change applied |
| A write whose result cannot be confirmed (network or server error, read-back mismatch) | Reported as failed, with the pre-change configuration attached, so you can inspect it — it is not reported as success |
| Removing a context that is not required | No-op |
| Removal that would leave a ruleset with no required checks | Refused |
| Setup when the context is already required | No-op |

## Limitations & safety boundaries

- **A review alone never alters governance.** The only path to a governance
  change is your explicit request.
- Setup never merges a PR, enables auto-merge, deletes branches, or changes
  bypass actors or unrelated settings.
- Setup adds this one context; it does not create a ruleset or branch
  protection where none exists.
- Pagination: very large rule sets are reported `UNKNOWN` rather than
  partially read.
- GitHub's own stale-review settings are neither read nor changed by this
  capability.

## Canonical semantics

[`review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md)
· design records:
[execution surface](../github-integration/execution-surface.md),
[status publisher](../github-integration/status-publisher.md),
[mechanism recommendation](../github-integration/review-status-recommendation.md),
[Rulesets vs. branch protection](../github-integration/ruleset-vs-branch-protection-research.md).
Where this guide and the policy disagree, the policy wins.
