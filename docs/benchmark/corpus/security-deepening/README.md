# Security Deepening Regression Fixture Corpus

Repository-development artifact for GitHub Issue
[#271](https://github.com/amirbena/code-review-skill/issues/271), a
deterministic fixture corpus for the Security deepening capability
tracked by parent Issue
[#83](https://github.com/amirbena/code-review-skill/issues/83) and its
own parent, the adaptive specialist-depth composition contract
[#82](https://github.com/amirbena/code-review-skill/issues/82). This is a
**focused sub-corpus** of [`benchmark-case/v2`](../../fixture-format.md)
fixtures pinning representative Security deepening outcomes as
follow-up quality hardening — it validates domain correctness after the
capability exists and does not define, gate, or redesign it. The
capability itself is designed and packaged in
[`../../../../shared/policies/security-deepening.md`](../../../../shared/policies/security-deepening.md),
which this corpus's expectations must stay consistent with.

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of [`../`](../README.md)
and [`../../`](../../README.md) this is **not** packaged into either
Skill archive and no packaged Skill resource depends on it — it is
consumed only by this repository's own test suite, through the single
reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
(never a second one).

## Selection principle

**One case per outcome shape** #271's scope requires, each isolating that
shape so a regression in any one is unambiguous. The six cases mirror
[`security-deepening.md`](../../../../shared/policies/security-deepening.md)'s
own worked examples and Activation section, and split evenly between
"the capability engages and finds a real defect" and "the capability
correctly stays quiet":

- **Alternate path** — a new route adds the authorization check base
  reasoning identifies, but an older route already reaching the same
  privileged helper still has none. Flagged on the actually-unenforced
  site, not the new, already-checked code.
- **Confused deputy** — a background worker uses its own service
  credential to act on a user-supplied job payload without re-checking
  the requesting user's authorization over the target. Flagged.
- **Sanitization assumption bypass** — a shared sanitizer's
  already-safe guarantee, relied on by an existing caller, does not hold
  on a new path that decodes after sanitizing. Flagged.
- **Single caller, check enforced** — the privileged helper has exactly
  one caller and the check is already correctly placed; base reasoning
  suffices and the capability contributes nothing further. `clean`.
- **Auth-named module, no trust-boundary crossing** — a change confined
  to an authorization-named module with no data/control flow across a
  privilege boundary; the domain is not materially implicated at all, so
  Activation condition 1 is never satisfied. `clean`.
- **Filename signal suppressed** — a security-adjacent filename
  (`auth_helper.py`) changes only a log message format; naming alone
  must not trigger engagement. `clean`.

The two `clean` "no engagement" cases above are deliberately distinct:
the auth-module case fails Activation condition 1 (the domain itself is
not materially implicated), while the filename-signal case is the
narrower guard from
[`specialist-depth.md`](../../../../shared/policies/specialist-depth.md)
that a naming coincidence is a signal, never independently sufficient —
so a regression that started treating filenames as triggers is caught
even if base activation logic stayed otherwise correct.

Each case is a crafted, self-contained Python patch (`input.patch` +
`input.base`), keeping the corpus runnable without network access and
consistent with the other corpora under [`../`](../README.md).

## Cases

| File | Outcome shape | A correct review must… | Decision |
|---|---|---|---|
| [`security-deepening-alternate-path-missing-check.yaml`](security-deepening-alternate-path-missing-check.yaml) | alternate path to an identified privileged operation | report one **P0**: the older `/legacy/records` route reaches `_delete_record` with no authorization check (an optional missing-security-test note is also acceptable) | `changes-required` |
| [`security-deepening-confused-deputy-worker-credential.yaml`](security-deepening-confused-deputy-worker-credential.yaml) | confused-deputy behavior | report one **P0**: the worker transfers funds using its own service credential without checking the requesting user's authorization over the source account (an optional missing-security-test note is also acceptable) | `changes-required` |
| [`security-deepening-sanitization-assumption-bypass.yaml`](security-deepening-sanitization-assumption-bypass.yaml) | sanitization assumption relied on elsewhere, shown not to hold | report one **P0**: `preview_upload` decodes after sanitizing, so an encoded traversal sequence bypasses `sanitize_filename` (an optional missing-security-test note is also acceptable) | `changes-required` |
| [`security-deepening-single-caller-check-enforced-clean.yaml`](security-deepening-single-caller-check-enforced-clean.yaml) | privileged operation, single caller, check already enforced | report **nothing** — base reasoning already suffices | `clean` |
| [`security-deepening-auth-module-no-trust-boundary-clean.yaml`](security-deepening-auth-module-no-trust-boundary-clean.yaml) | auth-named module, no trust-boundary-crossing behavior | report **nothing** — the domain is not materially implicated | `clean` |
| [`security-deepening-filename-signal-suppressed-clean.yaml`](security-deepening-filename-signal-suppressed-clean.yaml) | security-adjacent filename, no data/control-flow implication | report **nothing** — naming alone does not trigger deepening | `clean` |

Per-case provenance and a one- or two-sentence rationale also live in
each fixture's `metadata` block (`source`, `tags`, `rationale`) and in
the header comment.

## Validation

[`../../../../tests/unit/benchmark/test_security_deepening_corpus.py`](../../../../tests/unit/benchmark/test_security_deepening_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
used for the worked example and every other corpus. It never defines a
second one, and asserts: the sub-corpus stays small and documented;
every required outcome shape is present; every case pins an explicit
`decision` consistent with its required findings; every flagged case's
required finding is `P0`; every clean case carries no findings at all;
and every finding's anchor resolves inside its own case's patch or base.
Matching a reviewer's output to these expectations and scoring it are
out of scope here (Issues #41 / #52 / #54). Peer review of the expected
findings themselves happens on the pull request.
