# Private Evidence Cutover Runbook

Maintainer procedure for GitHub Issue
[#690](https://github.com/amirbena/code-review-skill/issues/690) (epic
[#686](https://github.com/amirbena/code-review-skill/issues/686)). It executes the
cutover order and rollback forms of the [ADR](private-evidence-repository.md) §10 and does not
change them. Like the rest of [`./`](README.md), a repository-development record, not packaged
into either Skill archive.

**Ownership.** Repository creation, rulesets, App installation and Routine configuration are
provider-side and **maintainer-only**; a coding agent does not perform them, handle credentials,
or delete a ref. The agent-owned part is the read-only
[`benchmark_evidence_migration.py`](../scripts/benchmark_evidence_migration.py) and this record.
Never write a token, key or private URL with credentials into this file or an issue.

```bash
export SRC=amirbena/code-review-skill EVD=amirbena/code-review-skill-evidence
```

## 0. Preconditions (stop if any is false)

| Check | How |
| --- | --- |
| Gate passes on the commit being cut over from | the command block in the [validation gate](private-evidence-validation-gate.md) |
| G-open-1 closed (§5.4 allowlist, F12/F13 tests pass) | the gate's §6; tracked by [#704](https://github.com/amirbena/code-review-skill/issues/704) — **blocks the operational cutover, not this PR** |
| X1–X3 maintainer experiments observed | ADR §12; record outcomes in §6 below. X3 is recorded `PASS` (§6); X1 is outstanding |
| X4 is `PASS` or `INCONCLUSIVE — ACCEPTED` (maintainer-approved) | ADR §12.2; states in the table below. `INCONCLUSIVE — BLOCKED` and `FAIL` stop the cutover |
| No campaign run is due during the window | ADR §10 "Counted refs" |

### X4 readiness states

| State | Meaning | Cutover |
| --- | --- | --- |
| `PASS` | Empirically verified: a provider-created checkout was observed fetching a non-default branch that existed at its provisioning time. | proceed |
| `INCONCLUSIVE — ACCEPTED` | Not empirically verified, and the maintainer explicitly approved the ADR §12.2 disposition on #690 (link recorded in §6). | proceed |
| `INCONCLUSIVE — BLOCKED` | Not verified and not approved, or controls 1–5 of ADR §12.2 are not in place. The baseline (control 6) is recorded at cutover; it gates reassessment, not this state. | stop |
| `FAIL` | A demonstrated failure. | stop |

**Current state: `INCONCLUSIVE — ACCEPTED`** ([maintainer approval of ADR §12.2](https://github.com/amirbena/code-review-skill/issues/690#issuecomment-6099209734), 2026-10-10). This is not an empirical `PASS`, and it does not authorize the cutover: every other precondition in this section still applies, and the §12.2 controls (including the cutover baseline, §4 step 5) must be in place.

**Evidence limitation.** The provider checkout was provisioned before the X1 probe branch existed and is reused across sessions, so no provider fetch of a pre-existing non-default branch was observed. The wildcard refspec and non-shallow configuration, and the explicit clone that fetched the X1 branch, are not direct proof. Do not rerun the same experiment.

**Required safeguards (ADR §12.2).** Minimal default branch; no unnecessary long-lived temporary branches; evidence refs kept under the existing retention contract; provider checkouts treated as possibly stale and local refs as non-authoritative; baseline measurement (ref count, packed size, cold full-clone time) recorded at cutover (§4 step 5) as the reassessment reference. The numeric threshold is a follow-up set by the maintainer from that baseline ([#712](https://github.com/amirbena/code-review-skill/issues/712)). X1, X2 and X3 are unchanged.

## 1. Preparation (ADR §10 pre-steps)

1. Create `$EVD` as **private**. Verify: `gh api repos/$EVD --jq '{private,visibility}'` → `true`, `private`.
2. Install `benchmark-publication` on `$EVD` only; grant the provider's Routine access to `$EVD`.
   Record least-privilege identities and rulesets in §6 (IDs only, no secrets).
3. Verify read/write: `git ls-remote https://github.com/$EVD.git` succeeds with the maintainer's access.

## 2. Freeze, drain, inventory (ADR §10 steps 1–2)

1. Pause every lane Routine and every other evidence-producing Routine (a campaign Routine stays enabled; cut over between two of its runs).
2. Drain the public store so every staging ref has a receipt (publisher sweep, not a dry run).
3. Inventory the source (read-only; namespaces and history branch come from the manifest):

```bash
python3 runtime_platform/benchmark/scripts/benchmark_evidence_migration.py inventory \
  --remote https://github.com/$SRC.git --out source-inventory.json
```

### Reset-aware rules (ADR §1.1 O1–O4, §10)

- **Reset refs are not inputs.** The 7 `claude/benchmark-result-sentinel-*` and 5 `claude/severity-observation-*` refs deleted on 2026-10-10 are absent from the live inventory, so they are never copied. List their names (`gh api "repos/$SRC/activity?activity_type=branch_deletion"`) one per line in `reset-refs.txt` and pass it to `reconcile`: a reset ref found in the source or in the target fails the report, so a restoration cannot pass unnoticed.
- **`benchmark-history` continuity.** It is copied by SHA, so records, receipts and `baselines/<lane>.json` stay identical; reconcile fails on any differing SHA. Never recreate the branch or rewrite its history.
- **Post-reset evidence** (refs created after 08:27Z on 2026-10-10 and before the freeze) is in the inventory, so it is copied like any other ref. Take the inventory only after the Routines are paused and the store is drained; the severity stop-condition count then continues from what the private store holds (O4), not from the pre-reset count.
- **Dangling `raw.location`.** Pre-reset records name staging refs that no longer resolve (O3). The tool reads ref names and trees only, never record content, and nothing here attempts to restore or rewrite a location.
- **Routine lifecycle.** Routines are paused, their prompts updated and re-enabled; none is deleted, recreated or rescheduled, and no new Routine is activated by this runbook.
- **No split-brain.** Run order is pause → inventory → copy → reconcile → cutover commit → prompt update → re-enable. Until the commit merges every Routine is paused; after it, the public store receives no writes (checked in §4 step 4 with `--forbid-extra`).

## 3. Copy by SHA and reconcile (ADR §10 step 3, I4)

Copy without rewriting history: one `git push` per inventoried ref from a mirror clone, same ref name, same SHA
(`git push https://github.com/$EVD.git <sha>:refs/heads/<ref>` for each key of `source-inventory.json`). Then:

```bash
python3 runtime_platform/benchmark/scripts/benchmark_evidence_migration.py inventory \
  --remote https://github.com/$EVD.git --out target-inventory.json
python3 runtime_platform/benchmark/scripts/benchmark_evidence_migration.py reconcile \
  --source source-inventory.json --target target-inventory.json --reset-refs reset-refs.txt \
  --out reconciliation-report.json
```

Exit 0 means every inventoried ref is present with an identical commit and tree and the fetched
objects pass `git fsck --strict`; exit 1 lists `missing_in_target`, `differing`, `reset_refs_still_in_source` or `reset_refs_restored_in_target`; exit 2 is a tooling
or access error. Refs removed by a maintainer-authorized reset (O2) are not inputs. Attach the report to #690.

## 4. Cutover (ADR §10 steps 4–6)

1. Merge the cutover commit: `evidence.phase: private`, `evidence.repository: <EVD>`, workflow token scope (F11) in one change; then apply the public creation ruleset (Q4).
2. Update every evidence-producing Routine's prompt with the private remote (V6); run one `auth-check` against `$EVD`.
3. Re-enable the Routines. Verify once per Routine (record in §6): a run publishes privately; a repeated trigger is a no-op (duplicate protection); stop conditions count the private store; the publisher sweep and watchdog read `$EVD`.
4. Confirm no new evidence refs reached the source: re-run `inventory` on `$SRC`, reconcile the old against the new source inventory with `--forbid-extra`; exit 0 means no evidence ref was written to the public repository after the cutover.
5. Record the X4 baseline (ADR §12.2 item 6): the evidence repository's ref count (`git ls-remote --heads`), packed size (`git count-objects -vH` on a fresh full clone) and the wall-clock time of that cold full clone. Attach it to #690 and to #712.

## 5. Cleanup and rollback

**Cleanup (never automatic; R4).** Delete public evidence refs only after (a) exit-0 reconciliation, (b) §4 verified, and (c) a maintainer comment on #690 naming the refs and approving deletion — record it in §6. Dispose of public issues per ADR §10 step 8.

**Rollback.** R-a (preferred): pause the Routines and fix forward; no store changes. R-b: with Routines paused, disable the public creation ruleset (Q4), copy post-cutover evidence back by SHA, `reconcile` in the reverse direction (swap `--source`/`--target`), revert the cutover commit (restores `pre_cutover` and the source repository together), then re-enable. R-b republishes private evidence publicly and needs approval recorded in an issue. Two stores never accept writes at once: Routines stay paused across each transition.

**Rollback dry run (documented, not executed against production):** run the inventory/reconcile pair with `--source`/`--target` swapped on a scratch mirror; `tests/unit/benchmark/test_benchmark_evidence_migration.py` exercises copy-by-SHA, extra refs, missing refs and rewritten refs on local bare repositories.

## 6. Records (maintainer fills in; keep on #690)

| Record | Content | Status |
| --- | --- | --- |
| Visibility and access | `private: true`; App installation ID; ruleset IDs | pending |
| Experiments X1–X3 | observed outcomes | X3: **`PASS`** — [run 38066153068](https://github.com/amirbena/code-review-skill/actions/runs/38066153068), job `114254101385` (2026-10-10): private-repository Activity API read with the `benchmark-publication` App token, origin attributed, wrong-actor / missing-activity / wrong-SHA rejected, `publish` skipped; fail-closed policy unchanged; ADR §12.3. This verifies X3 only and does not approve the cutover. X1: pending |
| Experiment X4 | state (below), maintainer approval link, baseline measurement (ADR §12.2 item 6) | state `INCONCLUSIVE — ACCEPTED`, [approval on #690](https://github.com/amirbena/code-review-skill/issues/690#issuecomment-6099209734) (2026-10-10); baseline pending (recorded at cutover) |
| Reconciliation report | `reconciliation-report.json` summary: counts, `reconciled`, date | pending |
| Cutover record | cutover commit SHA, window start/end, Routine prompt updates | pending |
| Per-Routine verification | run IDs for sentinel / comprehensive / severity / concurrency; duplicate, stop-condition, sweep results | pending |
| Public cleanup approval | approver, date, refs approved (or "not performed") | pending |
| Rollback | R-a/R-b chosen if used, approval link | n/a unless used |
