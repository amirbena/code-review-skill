# Workspace Sibling Context — Design

Explanatory companion to the canonical policy
[`workspace-sibling-context.md`](../../skills/local-code-review/policies/workspace-sibling-context.md).
If this page and the policy disagree, the policy wins.

## 1. Problem and shape

A review of one repository often raises a question only a neighbouring
repository can answer. #133 reads one named repository at a pinned
revision, but the caller must name both per review. This design adds a
second, weaker channel: the caller authorizes a **workspace root once**, and
the reviewer chooses within it for a specific unresolved question.

The invariant — local evidence may *nominate*, only the grant *authorizes*
— splits the problem in two. Everything about *where the reviewer may look*
is decided by invocation input; everything about *which sibling is
relevant* is judgment over untrusted content, bounded by the first.

## 2. Authorization model reconciliation

| Existing rule | How this design relates |
| --- | --- |
| Membership (#555): members are caller-listed, co-equal, carry findings | Unchanged. A sibling is non-member evidence; discovery excludes members and aliases; the multi-repository policy wording is clarified to say it concerns membership, not discovery. |
| Explicit channel (#133): path + pinned revision, per review | Unchanged and takes precedence. The workspace channel adds only the `workspace-resolved` basis. |
| Non-inheritance (AUTH-013 / DELEG-007) | The grant is primary-reviewer-only; workers receive no path, listing, or evidence. Same principle as mutation authorization. |
| Invocation-only authorization channel (INJECT) | The root comes only from invocation input; no file, workspace manifest, or resolved reference can supply it. |

## 3. Decisions and rejected alternatives

- **Immediate children only, one listing.** Recursive discovery makes the
  grant's effective reach depend on what repositories contain. One bounded
  listing keeps reach a function of the root the caller named.
- **HEAD at resolution time, read from the object database.** The working
  tree is what the engineer is mid-edit on; reading it would make evidence
  depend on uncommitted state invisible to the report. Resolving once to a
  full SHA gives a reproducible claim ("repo@sha") with a `dirty` flag
  instead of silent drift. Rejected: reading the working tree; tracking a
  branch tip.
- **Lower trust than a pinned revision.** The caller chose the workspace,
  not the revision; evidence therefore answers the question and corroborates,
  but cannot alone make a finding `confirmed`.
- **No per-sibling approval.** The grant is the authorization; bounds (caps,
  deny-list, no recursion) replace prompts. Rejected: asking per question,
  which makes the capability unusable and trains approval fatigue.
- **No new vocabulary.** No new severity, category, confidence value, or
  Decision rule; one new selection-basis value and one trust label.
- **Ambiguity reads nothing.** Two plausible siblings resolve to Context
  gaps, never to reading both.

## 4. Threat-model additions

| Scenario | Threat | Enforcement owner |
| --- | --- | --- |
| INJECT-015 | Reviewed or sibling content names a path to read as a sibling | #663 |
| INJECT-016 | A nomination, symlink, or relative path escapes the granted root | #663 |
| INJECT-017 | Content forges the workspace grant itself | #663 |
| INJECT-018 | A sibling excerpt exposes a secret into the report | #663 |
| DELEG-012 | A parallel worker inherits or exercises the grant | #303 (delegation non-transferability), #663 |

All are `COVERAGE_GAP` for regression evidence until #663/#664 land; the
catalog entries record the enforcement point and expected safe outcome.

## 5. What #663 must implement

1. Grant intake from invocation input only; rejection reasons in Context gaps.
2. A pure, testable discovery function: one non-recursive listing,
   realpath/common-dir exclusion, symlink containment, linked-worktree
   requirement, 200-entry cap.
3. Nomination and confirmation rules (exactly one candidate with a signal
   beyond a bare name match; ambiguity reads nothing; 3-sibling / 1-per-
   question caps).
4. HEAD → full SHA resolution, object-database read via the shared
   external-contract mechanism with `workspace-resolved` as an accepted
   label, dirty flag, provenance and trust label.
5. Deny-list, excerpt minimization, no-execution, no-instruction-following.
6. Primary-reviewer-only: workers receive nothing.
7. Wiring: capability declaration, activation, SKILL.md input line,
   manifest, finding-template provenance wording.

## 6. Non-goals

See the policy's "Non-goals". In short: no implementation, no GitHub mode
(#645), no change to #133 or membership.
