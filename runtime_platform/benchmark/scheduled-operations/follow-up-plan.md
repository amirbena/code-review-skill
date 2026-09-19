# Follow-up Plan

Part of the [scheduled benchmark operations decision record](decision-record.md)
(GitHub Issue [#464](https://github.com/amirbena/code-review-skill/issues/464)).
Research / design only; not packaged into either Skill archive.

The smallest implementation issues, their order, and their ownership class.
**None are created by #464.** When a maintainer creates them, the declared
`Parent` / `Depends on` fields need the matching native GitHub relationships
([`../../../policies/github-issue-pr-authoring.md`](../../../policies/github-issue-pr-authoring.md),
"Native GitHub relationships"), verified by re-fetching.

Ownership classes follow
[`../../../policies/contribution-ownership-policy.md`](../../../policies/contribution-ownership-policy.md):
blast radius and privilege decide, not patch size. A bounded implementation
of an already-canonical contract may be *contributor-owned* under the
shared-contract exception, but only once the amendments it depends on are
approved and recorded — while any depended-on decision is open it stays
maintainer-led.

## 1. Issues

| ID | Issue | Depends on | Class | Why |
| --- | --- | --- | --- | --- |
| F1 | **Land the approved contract amendments** (A1–A13) as a docs-only change to the canonical documents, with the documentation-impact check. | maintainer approval of the rows | maintainer-led | Redefines shared benchmark contracts. |
| F2 | **Canonical result schema and validator** — `benchmark-result/v1`, `run_id`, per-case `fixture_digest`, receipt schema, canonical-JSON hashing, reference fixtures, first measurement of real record size (feeds the growth trigger). | F1 | maintainer-led until A4/A7 are approved; then contributor-owned eligible | Bounded conformance against a canonical contract; schema decisions must be closed first. |
| F3 | **Repo-owned schedule spec** — expected-run manifest (`max_gap_hours`, confirmation parameters, the pusher allowlist for origin attestation, label set, tracking-issue numbers), the thin Routine prompt spec, label definitions. | F1 | maintainer-led | Defines operating policy. |
| F4 | **Execution-side entrypoint** — lane run, in-run confirmation re-runs, drift evaluation from the record, seal to the handoff; removes `gh`/GitHub mutation from repository-owned execution code; adds a policy test that forbids it. | F2, F3 | maintainer-led | Execution semantics and the write-authority boundary. |
| F5 | **Publication CLI** — `sweep`: validate (including origin attestation from the activity API), persist (create-only), announce (run markers), reconcile drift issues with scope-aware resolution, receipts, recurrence links, caps, over every unpublished sealed ref in ascending `sealed_at`; plus `--once`. Runs entirely against in-memory fakes. Retires the in-Routine `GhCliIssueClient` path. | F2, F3 | maintainer-led | GitHub mutation authority; #339 lifecycle semantics. |
| F6 | **Watchdog and health status** — the `watchdog` subcommand of the publication CLI. | F3, F5 | maintainer-led | Failure-visibility semantics. |
| F7 | **Provisioning runbook and execution** — register the `benchmark-publication` App, set the permission matrix, create the `benchmark-publication` environment (deployment branch policy: default branch only) and store the App secrets there, create the `benchmark-history`, tag, and staging-ref rulesets, create the labels, create and lock tracking and health issues, and record an observed check of each. | F1 | maintainer-only (repository/account administration) | Privileged, non-delegable; a runbook in the repo, the actions by the maintainer. |
| F8 | **Publication workflow** — `benchmark-publish.yml`: `schedule` sweep and `workflow_dispatch` only, default-branch definition, a `contents: read` job token plus two phase-scoped App tokens, the concurrency group and environment; the policy test that enforces its triggers, credentials, and imports; a dispatch drill and a local `--once` drill including credential revocation. *Replaces the earlier publisher-host issue.* | F5, F6, F7 | maintainer-led | A privileged workflow; custody of the App key. |
| F9 | **Routine provisioning, verification, and first verified runs** — thin prompt spec, both schedules, observed residual-R1 check, DST verification, measured duration and usage for the comprehensive lane against the 04:00 window and the account's daily run cap. | F4, F8 | maintainer-only | Provider-side configuration; the repo cannot verify it. |
| F10 | **Actions-side read-only validation** — schema, manifest, and documentation-link checks in the existing `validate.yml`; no `schedule:`, no secrets. | F2, F3 | contributor-owned eligible | Bounded and deterministic; maintainer/CODEOWNERS review stays required. |
| F11 | **Repository documentation** — the canonical technical/operational specification (§2). | F9 | maintainer-led | Owns final semantics. |
| F12 | **GitHub Wiki page** — the maintainer/user-facing operating-model page (§3). | F11 | maintainer-led | Publishes to the Wiki; needs Wiki write access and verified-in-operation claims. |

**Conditional, opened only if triggered:** F13 — the publication workflow
fires a Routine API trigger to retry a missed run (deferred: adds a bearer token
as an environment secret); F14 — rotate `benchmark-history` or move records to
an external store when the growth trigger trips; F15 — shard the comprehensive
lane if F9 shows the 04:00 window is infeasible; F16 — an event-driven arrival
accelerator (an unprivileged `push` trigger on `claude/benchmark-result-*` plus
a `workflow_run` publication job), only if sweep latency ever matters and only
after a Routine push has been observed to fire it.

## 2. Order

```text
approve amendments (A1–A13) ─→ F1 ─┬─→ F2 ─┬─→ F4 ───────────────┐
                                    │       └─→ F5 ─→ F6 ─┐       │
                                    ├─→ F3 ─→ (F4, F5, F6)│       │
                                    └─→ F7 ───────────────┴─→ F8 ─┴─→ F9 ─→ F11 ─→ F12
                              F2, F3 ─→ F10   (any time after both)
```

Contract text lands before code (F1 first); privileged provisioning (F7) can
proceed in parallel with code; nothing is scheduled (F9) until the publication
workflow exists (F8), so no run can be sealed and left unpublishable. F8 is
enabled only after F7, so the App secrets, environment, and rulesets exist first.

## 3. Documentation work, both surfaces

The two surfaces have different jobs and must not duplicate each other or
this record. Both are gated on **F9**: claims about "how a maintainer verifies
health" are written only after they have been exercised against real runs.

### F11 — repository docs: the canonical technical / operational specification

- **Home:** `runtime_platform/benchmark/scheduled-operations/operations-specification.md`,
  linked from this directory's README and from
  [`../README.md`](../README.md)'s document map.
- **Nature:** canonical for behavior — the final, implemented architecture
  written as a specification, not as a decision. It supersedes the design
  content of this record; this record stays as the rationale and rejected
  alternatives.
- **Contents:** the boundary and components; the manifest and prompt spec; the
  sealed-result and receipt schemas; the `benchmark-history` layout;
  baselines and promotion; drift evaluation and confirmation; the publication
  workflow and CLI — triggers, sweep and watchdog steps, the App-token path,
  capability set, and idempotency markers; the failure table; the
  maintainer runbook (provisioning, health checks, recovery per failure
  case, rotating the App key, promoting a baseline).
- **Documentation-impact check** (per
  [`../../../policies/documentation-policy.md`](../../../policies/documentation-policy.md)):
  amend the four contract documents (F1), the measurement-architecture §6,
  [`../../../docs/benchmark/README.md`](../../../docs/benchmark/README.md),
  and [`../../../docs/ARCHITECTURE.md`](../../../docs/ARCHITECTURE.md) only where their
  component/boundary statements changed; link down rather than restate.

### F12 — GitHub Wiki: "How the Scheduled Benchmark System Works"

- **Home:** a new Wiki page, linked from the existing `Benchmark-Testing`
  page's related pages and from the Wiki's home/page map. The Wiki is a
  separate repository (`code-review-skill.wiki.git`), so it is edited and
  pushed separately from the code repository and never as part of a code PR.
- **Audience and tone:** maintainers and users who want to understand the
  system without reading a contract; plain language, one diagram, no schema
  dumps.
- **Sections:**
  1. *What it is and why* — measuring review quality over time; how it differs
     from the PR-time Top-K selection.
  2. *Scheduling* — the two lanes, cadence as a maximum gap, the Israel-local
     window, who owns the timezone (the Routine), and why it never runs on
     GitHub Actions.
  3. *Sentinel vs comprehensive* — what each covers, why both, why their
     baselines are independent, and what happens when they land on one night.
  4. *A run end to end* — execution, positive verification, confirmation
     re-runs, drift evaluation, seal, then publication.
  5. *Where results live* — the history branch, what a record contains, the
     tracking issue, and immutable links.
  6. *Baselines* — pinned per lane, bootstrap, explicit promotion, and why it
     is not "yesterday's run".
  7. *Drift detection* — the three drift types, noise, and what "confirmed"
     means.
  8. *GitHub publication and issue lifecycle* — the publication App, one issue
     per regression, comment on recurrence, close on resolution, `keep-open`.
  9. *Who can do what* — a short table of what holds credentials and what
     never does.
  10. *Is it healthy?* — the maintainer health checklist and what to do for a
      missed run, a stalled publication workflow, or a stale baseline.
  11. *Glossary and canonical references* — links to the repository
      specification; no duplicated rules.
- **Verification:** every operational claim is checked against F9's real
  runs; the page renders correctly and stays scoped to the pages it touches;
  the Wiki's own link checks pass.
- **Not included:** the decision record's alternatives and evidence — that is
  linked, not copied.
