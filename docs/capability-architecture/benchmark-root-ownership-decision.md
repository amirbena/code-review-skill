# Root `benchmark/` Ownership Decision

Repository-development decision record for issue
[#578](https://github.com/amirbena/code-review-skill/issues/578), child C1
of epic [#577](https://github.com/amirbena/code-review-skill/issues/577).
It **amends** the
[benchmark ownership boundary checkpoint](benchmark-ownership-boundary-checkpoint.md)
(#425) and fixes the final ownership table **before any file moves**.

Like the rest of [`./`](README.md), this is a repository-development doc:
not packaged into either Skill archive, and no packaged Skill resource
depends on it. It moves no file, changes no path constant, and edits no
fixture, prompt-block, or contract byte.

**Status: proposed — awaiting maintainer approval.** Approval is recorded
on #578 itself, and no implementation child of #577 (#579–#583) starts
until it is.

## 1. The conflict being resolved

The #425 checkpoint (§7) directs corpus ownership to
`capabilities/<name>/corpus/` and says relocation should follow model §E.2
"rather than any new topology". Epic #577 proposes a root `benchmark/`,
which is a new topology. Left as is, the repository would hold two
conflicting ownership statements. The same checkpoint's README claim that
the remaining `docs/benchmark/` files are not machine contracts is also
inaccurate for one file (§5).

## 2. Decision

1. **Ratify a first-class root `benchmark/`** as the home of the corpus,
   `corpus-index.json`, `examples/`, and the routine/operator/reference
   content that #457 left under `docs/benchmark/`.
2. **Amend #425 §4 and §7**: corpus ownership is `benchmark/` now, not
   `capabilities/<name>/corpus/`. The per-capability corpus split is
   **deferred, not blocked and not cancelled** (§6).
3. **Keep `runtime_platform/benchmark/` unchanged.** Having both
   `benchmark/` and `runtime_platform/benchmark/` is intentional (§3).
4. **`cloud-routine-integration.md` is operational, executable benchmark
   content** that moves with `benchmark/` (§5).
5. The pure prefix swap `docs/benchmark` → `benchmark` keeps internal
   structure 1:1. It is performed by later children, not here.

What stays true from #425: the benchmark subsystem is infrastructure, not
generic documentation, and `docs/` must not hold it (§3 of that record).
Only the *destination* of the corpus half changes.

## 3. Boundary: `benchmark/` vs `runtime_platform/benchmark/`

The two directories are distinct on purpose. The test is what a file *is*:

| If the file is… | It belongs in |
| --- | --- |
| A contract, schema, scoring rule, or code that the harness enforces or executes as logic | `runtime_platform/benchmark/` |
| Data the harness reads (fixtures, index, worked examples) or operator/routine content a person or scheduled entrypoint consumes | `benchmark/` |

Consequences:

- Contract docs, schemas, harness scripts, publisher, schedule manifest
  and `scheduled-operations/` internals stay in
  `runtime_platform/benchmark/`. This decision does not relocate them.
- `benchmark/` holds no harness logic and no contract; it holds what the
  harness is pointed at.
- Data flows one way: `runtime_platform/benchmark/` code reads
  `benchmark/`. A `benchmark/` file never carries behavior a contract
  depends on except the pinned prompt block in §5.

## 4. Final ownership table

The canonical, maintained copy of this table is in
[`benchmark/README.md`](../../benchmark/README.md); this one is the
record as ratified.

| Location | Owns |
| --- | --- |
| `benchmark/` | `corpus/` fixtures, `corpus-index.json`, `examples/`, operator/routine/reference docs (`README.md`, `cloud-routine-integration.md`, `reviewer-brief-examples.md`, `senior-voice-examples.md`, `shadow-validation-burn-in-report.md`) |
| `runtime_platform/benchmark/` | contracts, schemas, harness scripts, publisher, schedule spec/manifest, scheduled-operations internals (unchanged) |
| `docs/` | architecture and decision records and pointers; `docs/benchmark-measurement-architecture/` unchanged; `docs/benchmark/` ends with no tracked canonical content |
| Wiki | user-facing benchmark guidance |

## 5. `cloud-routine-integration.md` classification

`docs/benchmark/README.md` says none of the remaining files "is a machine
contract that harness code actively enforces". That is wrong for this
file. `runtime_platform/benchmark/scripts/benchmark_lane_run.py` reads its
§9 prompt template block at runtime, and `spec_sha256` is derived from
those bytes. It is therefore **operational, executable benchmark content**:

- it is not generic documentation and does not stay under `docs/`;
- it is not a contract doc, so it does not move to `runtime_platform/benchmark/`;
- it moves with `benchmark/`, with the §9 routine prompt block bytes
  unchanged so `spec_sha256` stays stable. `spec_sha256` hashes only that
  block and the manifest, so the rest of the file may have its relative
  links rewritten by the move.

The other four remaining files are reference/example material and are not
read by harness code. The README claim is corrected by the child that
rewrites that README (#581); this record is the correction of record.

## 6. Per-capability corpus split

The `capabilities/<name>/corpus/` destination in model §E.2 and #425 §7
item 1 is unchanged as a *future* refinement. It is deferred until each
capability directory holds more than a manifest, not blocked by this
decision. A later move out of `benchmark/` would be its own decision and
would again be a prefix-preserving relocation, so root `benchmark/` is not
a dead end.

## 7. Invariants for the implementation children

- Fixture bytes, including the stale header comments inside the corpus
  YAMLs, and the routine prompt-block bytes stay unchanged: `corpus_id`,
  `fixture_digest` and `spec_sha256` are byte-derived.
- No compatibility bridge and no duplicate corpus (Comprehensive
  discovery is an `rglob`).
- Sealed records on `benchmark-history` and SHA-pinned permalinks are
  never rewritten.
- Sentinel/Comprehensive lane discovery, cadence, schedule manifest,
  publication boundary and sealed-record schema do not change.

## 8. Out of scope

Moving any file or changing any path constant; relocating contract docs
out of `runtime_platform/benchmark/`; redesigning lane discovery.

## Related

- [#577](https://github.com/amirbena/code-review-skill/issues/577) — the
  epic; [#425](https://github.com/amirbena/code-review-skill/issues/425),
  [#457](https://github.com/amirbena/code-review-skill/issues/457) — the
  boundary checkpoint and first migration slice this builds on.
- [`benchmark-ownership-boundary-checkpoint.md`](benchmark-ownership-boundary-checkpoint.md)
  — amended by this record.
- [`capability-architecture-model.md`](capability-architecture-model.md)
  §E.2, §H — carry matching amendment notes.
