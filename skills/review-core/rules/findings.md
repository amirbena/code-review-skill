# Findings, severity and decision

## Severity

Every finding has exactly one severity.

- **P0** — unsafe to merge: an exploitable security hole, data loss or
  corruption, or a broken critical path. Rare, and only with strong
  evidence.
- **P1** — should be fixed before merge: a functional bug, a regression,
  a broken contract, a concurrency or reliability defect, an unsafe edge
  case, or missing tests for risky changed behavior.
- **P2** — worth fixing but not blocking: maintainability, a localized
  design weakness, a lower-risk test gap, misleading documentation. Never
  formatting or style taste.

## Evidence

- **S4** — Every finding cites a location in the reviewed target, at the
  reviewed revision, that you actually read, and its evidence quotes or
  describes what that code does. Never cite a file, line, symbol, test or
  output you did not read, and never invent one to support a finding.

## Finding shape

| Field | Content |
| --- | --- |
| `severity` | `P0`, `P1` or `P2` |
| `title` | the defect, in one line |
| `location` | `path:line` or `path:start-end` where the fix belongs; `path` alone only when no line applies. When the cause and a broken site differ, cite the other place in `evidence` |
| `evidence` | what the code does, from what you read |
| `impact` | who or what is hurt, and when |
| `fix` | focused, actionable guidance for this finding: what to change, not a rewrite |

Findings are numbered `F1`, `F2`, … in report order, most severe first.

## `REVIEW INCOMPLETE`

A run is incomplete when, and only when, one of these happens:

1. **target-unreadable** — the target or its diff cannot be fully read;
2. **file-unreadable** — a changed text file cannot be read;
3. **head-moved** — the PR's HEAD moved during the review;
4. **mini-skill-input-missing** — a selected mini-skill could not obtain
   its required input.

The report names each trigger that applied and what it left unreviewed.
Findings already found are still reported. Binary files and files the
user excluded are listed as not reviewed and do not trigger it. A concern
listed as not investigated does not trigger it either.

## Decision

- **S3** — The decision is mechanical. Count the final findings by
  severity. If any trigger above applied, the decision is
  `REVIEW INCOMPLETE`. Otherwise, if P0 + P1 > 0, it is
  `CHANGES REQUIRED`. Otherwise it is `REVIEW CLEAN`. P2 findings never
  block, and an incomplete review is never rendered clean. To change the
  decision, change a finding's severity on its evidence, never the
  decision itself.
