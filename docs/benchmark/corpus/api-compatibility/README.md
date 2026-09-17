# API / Contract Compatibility Benchmark Corpus

Repository-development artifact for GitHub Issue
[#184](https://github.com/amirbena/code-review-skill/issues/184), a
deterministic fixture corpus for the API / contract compatibility review
capability tracked by parent Issue
[#175](https://github.com/amirbena/code-review-skill/issues/175). This is
a **focused sub-corpus** of [`benchmark-case/v2`](../../fixture-format.md)
fixtures pinning the expected `compatible` / `breaking` /
`context-dependent` classification for the common change shapes #175's
scope lists. It landed before the reviewer capability itself did; the
capability is now designed and packaged in
[`../../../api-compatibility/README.md`](../../../api-compatibility/README.md)
and [`../../../../shared/policies/review-scope.md`](../../../../shared/policies/review-scope.md),
"API / contract compatibility review," which this corpus's expectations
must stay consistent with.

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of [`../`](../README.md)
and [`../../`](../../README.md) this is **not** packaged into either Skill
archive and no packaged Skill resource depends on it — it is consumed only
by this repository's own test suite, through the single reference
validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
(never a second one).

## Selection principle

**One case per change shape** #184's scope requires, each isolating that
shape from the others so a regression in any one is unambiguous:

- **Add optional field** — unconditionally compatible: nothing existing
  breaks.
- **Remove field** — unconditionally breaking: an existing consumer loses
  the property outright.
- **Optional to required** — breaking without deleting anything: it
  narrows the set of previously-valid inputs.
- **Add enum member** — **context-dependent**: additive for a permissive
  consumer, breaking for one with an exhaustive switch/case or strict
  closed-set validation. The fixture format has no separate
  "context-dependent" `decision` token (only `clean` /
  `changes-required`, mechanically derived — see
  [`../../fixture-format.md`](../../fixture-format.md) §7), so this case
  pins the fail-closed reading required by #175's Goal ("Unresolvable
  consumer/intent context produces a deterministic no-finding outcome"):
  `decision: clean` with an **optional** finding that surfaces the
  ambiguity rather than a required finding that invents a breakage claim
  the diff cannot support.
- **Remove enum member** — unconditionally breaking, the deliberate
  asymmetric pair to "add enum member": no existing consumer can already
  tolerate a value ceasing to exist.
- **Rename response property** — breaking in both directions (existing
  readers of the old name, and, once required, senders that never knew
  the new one), and a distinct change shape from plain removal even
  though the underlying failure mode rhymes with it.

Each case is a crafted, self-contained JSON Schema patch (`input.patch` +
`input.base`), keeping the corpus runnable without network access and
consistent with the other corpora under [`../`](../README.md). JSON Schema
is used uniformly across all six cases so the compatibility reasoning the
cases pin is never entangled with a per-format parsing detail — #175's
scope separately enumerates OpenAPI, protobuf, and event/message schemas
as other recognized contract types, which is a `format`-recognition
concern the reviewer capability owns, not this fixture corpus.

## Cases

| File | Change shape | A correct review must… | Decision |
|---|---|---|---|
| [`api-compat-add-optional-field-compatible.yaml`](api-compat-add-optional-field-compatible.yaml) | add optional field | report nothing — `User` gains an optional `email` property | `clean` |
| [`api-compat-remove-field-breaking.yaml`](api-compat-remove-field-breaking.yaml) | remove field | report one **P1**: `OrderResponse` drops `currency` | `changes-required` |
| [`api-compat-optional-to-required-breaking.yaml`](api-compat-optional-to-required-breaking.yaml) | optional to required | report one **P1**: `CreateTicketRequest.description` becomes mandatory | `changes-required` |
| [`api-compat-add-enum-member-context-dependent.yaml`](api-compat-add-enum-member-context-dependent.yaml) | add enum member | report **no required finding**; an *optional* `P1`/`P2` note may flag the ambiguity — `PaymentStatus` gains `refunded` | `clean` |
| [`api-compat-remove-enum-member-breaking.yaml`](api-compat-remove-enum-member-breaking.yaml) | remove enum member | report one **P1**: `PaymentStatus` drops `failed` | `changes-required` |
| [`api-compat-rename-response-property-breaking.yaml`](api-compat-rename-response-property-breaking.yaml) | rename response property | report one **P1**: `Profile.full_name` becomes `fullName` | `changes-required` |

The two `PaymentStatus` cases (`api-compat-add-enum-member-context-dependent.yaml`
/ `api-compat-remove-enum-member-breaking.yaml`) are a deliberately matched
pair: same enum, same kind of edit (one member), the only difference being
addition versus removal — so a correct review's behavior is shown to turn
on which change shape it is, not on "an enum changed" alone.

Per-case provenance and a one- or two-sentence rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`) and in the
header comment.

## Validation

[`../../../../tests/unit/benchmark/test_api_compatibility_corpus.py`](../../../../tests/unit/benchmark/test_api_compatibility_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
used for the worked example and every other corpus. It never defines a
second one, and asserts: the sub-corpus stays small and documented; every
required change shape is present; every case pins an explicit `decision`
consistent with its required findings; the enum add/remove pair edits the
identical schema; and every finding's anchor resolves inside its own
case's patch or base. Matching a reviewer's output to these expectations
and scoring it are out of scope here (Issues #41 / #52 / #54). Peer review
of the expected findings themselves happens on the pull request.
