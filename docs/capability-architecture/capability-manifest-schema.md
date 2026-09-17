# Capability manifest schema (`capability.yaml`)

Status: Step 1 of the migration in
[`capability-architecture-model.md`](capability-architecture-model.md)
(§J.2, §M.4, §M.5) — issue #404. Purely additive: this document and the
`capabilities/<name>/capability.yaml` files it describes are declarative
records only. **No consumer reads them yet.** They introduce no packaging,
loading, or behavior change; `scripts/packaging/package-manifest.json`,
`metadata/skill.yaml`, and `SKILL.md` §2 remain the authoritative
declarations until a later step (§J.2 Step 1's second half) makes them
generated projections of this manifest.

## Purpose

`capability-architecture-model.md` §A.9 identifies three declarations of
the same dependency set that already disagree, and §J.2 identifies two
hand-maintained registries — `shared/policies/review-scope.md` and
`scripts/packaging/package-manifest.json` — that every capability addition
must edit by hand. `capability.yaml` is the single machine-readable
statement those declarations are meant to converge on: one file per
capability, naming what it owns, what it depends on, when it activates,
which adapters it applies to, what it may never do, and where its
benchmark evidence lives.

## Location

```text
capabilities/<name>/capability.yaml
```

`<name>` is the capability's canonical name from
[§M.4](capability-architecture-model.md#m4-what-becomes-independently-loadable)
and must match the manifest's own `capability:` field. The directory
holds only the manifest for now; a later step (§J.2 Step 3+) is what
would move the capability's owned files underneath it.

## Fields

| Field | Required | Type | Meaning |
| --- | --- | --- | --- |
| `capability` | yes | string | The capability's canonical name. Must equal the containing directory name (`capabilities/<capability>/capability.yaml`). |
| `summary` | yes | string, one line | The capability's responsibility in one sentence — not a restatement of its policy files' prose. |
| `loads` | yes | `always` \| `on-activation` | Whether the capability is always resident or lazily loaded. Every name in §M.4 is `on-activation`; `always`-resident capabilities (`review-kernel`, `finding-contract`, …) are out of scope for this issue but use the same schema when their manifests are authored. |
| `activation` | required iff `loads: on-activation` | list of strings | Predicates evaluable from the router's cheap inputs (§G.1) that must hold for the capability to engage. Omitted entirely when `loads: always`. |
| `adapters` | yes | list, subset of `[local, github]` | Which adapter(s) this capability applies to — mirrors the "Local/GitHub" column in §B.2/§B.4. `[local, github]` means both. |
| `files` | yes | list of repo-relative paths | The files this capability currently owns, i.e. its shared-policy footprint today. No file has moved yet; this is a declaration over the existing tree, checked against `scripts/packaging/package-manifest.json` and each Skill's `metadata/skill.yaml`. |
| `requires` | yes | list of capability names | Other capabilities this one depends on (§G.1's `requires`). `[]` when there are none. |
| `never` | yes | list of strings, at least one | The boundary's teeth (§G.1) — what the capability may not do, drawn from its owned policies' own non-goal/never statements wherever they already exist. |
| `benchmark` | yes | string | The corpus or reference-test path that exercises this capability, per §B.4's "Benchmarkable?" column. |

Field order in the examples below is the conventional order; the schema
test only asserts presence and type, not ordering.

## Worked example

```yaml
capability: repository-checkout
summary: >-
  Isolated, read-only, detached checkout of a PR's head commit, with
  guaranteed guarded cleanup.
loads: on-activation
activation:
  - adapter is github AND repository-backed context is requested
adapters: [github]
files:
  - skills/github-pr-review/policies/repository-checkout.md
requires: [capability-posture]
never:
  - silently falling back to API-only mode without emitting the
    `REPOSITORY CONTEXT UNAVAILABLE` signal
  - creating a new graded decision value out of degraded checkout state
  - changing the review standard, the severity model, or a finding's
    evidence bar because repository-backed mode was or was not available
benchmark: tests/reference/review/pr_checkout.py
```

This mirrors `skills/github-pr-review/policies/repository-checkout.md`'s
own stated invariants (its "never silently falls back" and "never changes
the review standard" language) rather than inventing new ones — the
manifest's `never` clauses are a projection of the owning policy's
existing non-goals, not a new source of truth.

## What this step does not do

Per issue #404's non-goals and §J.2 Step 1:

- It does not generate or validate `package-manifest.json` from these
  files (the next child issue).
- It does not change what either Skill archive packages, or what either
  `SKILL.md`/`metadata/skill.yaml` declares.
- It does not change any runtime loading behavior — nothing reads these
  manifests at review time.

`files:` is whole-file granularity — it cannot express that a single file
is split in substance between two capabilities. One case exists today:
`shared/templates/finding.md` is claimed by
`capabilities/finding-placement-derivation/capability.yaml`, but per
§B.2/§B.4 most of that file's words (the finding's fields and quality bar)
belong to `finding-contract`, an always-resident capability not yet
manifested because it is out of scope for this issue. Do not read
`finding-placement-derivation`'s `files:` entry as exclusive ownership of
`finding.md` until `finding-contract`'s own manifest is authored and the
two are reconciled.

## Validation

`tests/policy/governance/test_capability_manifest_schema.py` asserts,
for every `capabilities/*/capability.yaml`:

- the required fields listed above are present and non-empty;
- `capability` matches the containing directory name;
- `loads` is one of `always`/`on-activation`, and `activation` is present
  if and only if `loads: on-activation`;
- `adapters` is a non-empty subset of `{local, github}`;
- `files`, `requires`, and `never` are lists (empty allowed only for
  `requires`);
- every path in `files` exists in the repository tree.

It does not assert cross-file consistency against `package-manifest.json`
or `metadata/skill.yaml` — reconciling those is explicitly out of scope
for this issue (§J.2 Step 1's second half, tracked as a later child of
#403).
