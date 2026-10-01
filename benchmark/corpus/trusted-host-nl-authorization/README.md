# Trusted-Host Natural-Language Authorization Benchmark

Repository-development artifact for GitHub Issue
[#370](https://github.com/amirbena/code-review-skill/issues/370),
depends on [#369](https://github.com/amirbena/code-review-skill/issues/369)
(natural-language recognition in front of the canonical
`allow_trusted_host_execution` state
[#367](https://github.com/amirbena/code-review-skill/issues/367) defines).
It validates that natural-language trusted-host-execution authorization
resolves correctly by **semantic intent, not literal phrase-matching** —
covering both differently-worded equivalent requests and adversarial
attempts to manufacture authorization from untrusted sources — and that
this holds identically alongside the existing structured/sandbox
behavior.

## Why this isn't a `benchmark-case/v2` corpus

Every corpus under [`../`](../README.md) that reviews a code change
(each a self-contained inline patch plus expected review *findings*) uses
the `benchmark-case/v2` fixture format
([`../../fixture-format.md`](../../../../runtime_platform/benchmark/fixture-format.md)). This domain has no
patch and no finding: its input is a piece of trusted-invocation text (or
a structured boolean) and its expectation is a resolved
`allow_trusted_host_execution` boolean plus an execution-backend
provenance value. Rather than stretch the finding-shaped schema to also
carry authorization-resolution semantics, this corpus follows the same
test-only, data-driven reference-fixture pattern
[`../delegation-spawn/README.md`](../delegation-spawn/README.md) already
established for the structurally analogous agent-spawn/delegated-
authority domain:

- [`../../../../runtime_platform/benchmark/reference/trusted_host_nl_fixtures.py`](../../../../runtime_platform/benchmark/reference/trusted_host_nl_fixtures.py) —
  one `TrustedHostNLCase` per required outcome shape, each a
  zero-argument `run()` closure that exercises the *single* reference
  model,
  [`../../../../tests/reference/review/runtime_validation.py`](../../../../tests/reference/review/runtime_validation.py)
  (`resolve_allow_trusted_host_execution` and `select_backend`), plus the
  declarative metadata #370 requires: category, covered Scope tags, the
  Skills it applies to, expected resolved `allow_trusted_host_execution`
  boolean, and expected execution-backend provenance.
- [`../../../../tests/unit/benchmark/test_trusted_host_nl_authorization_corpus.py`](../../../../tests/unit/benchmark/test_trusted_host_nl_authorization_corpus.py) —
  runs every case's `run()` and asserts its actual outcome matches the
  declared expectation, plus corpus-completeness checks (every required
  category, every required coverage tag, every phrase in the reference
  model's own affirmative/negative vocabulary), a detection-power canary
  for the repository/malicious-file rejection, and the malformed-fixture
  rejection suite.

This corpus is **not** a duplicate of
[`../../../../tests/unit/review/test_runtime_validation.py`](../../../../tests/unit/review/test_runtime_validation.py)'s
`NaturalLanguageAuthorizationResolution` and `TrustedHostExecutionBackend`
classes, which #367/#369 already landed as hand-written regression tests
against the same reference model. That suite is *why* the boundary holds;
this corpus is the declarative, metadata-bearing **benchmark** layer #370
asks for — every case carries its expectation as structured *data*,
independent of a hand-written test method name, and adds coverage that
suite does not: the adversarial-source categories (repository-controlled,
malicious-instruction-file, PR-content-escalation, delegated-agent) and
authorization non-persistence across invocations. Both layers call into
the *same* single implementation; neither ever forks it.

## Evaluation style

Every comparison in this corpus is a **deterministic structural
assertion** — the resolved `allow_trusted_host_execution` boolean and the
selected `Provenance` (`sandbox` / `trusted-host` / `unavailable`) — never
an LLM/rubric score. This corpus is disjoint from the finding-precision/
recall/severity metrics
([#41](https://github.com/amirbena/code-review-skill/issues/41)): it
never touches a finding, a severity, or review prose, and it never scores
review *quality* — only authorization-resolution correctness.

## Why every case covers both Skills

[`shared/policies/trusted-host-execution.md`](../../../../shared/policies/trusted-host-execution.md)
states it "applies identically to `local-code-review` and
`github-pr-review`," and both Skills' runbooks consult the one reference
model this corpus benchmarks — there is no Skill-specific branch in
`resolve_allow_trusted_host_execution` or `select_backend` for a case to
diverge across. Every `TrustedHostNLCase` therefore declares
`skills=("local-code-review", "github-pr-review")` rather than being
authored twice, once per Skill: duplicating a case per Skill would
exercise the identical code path twice while adding no real coverage, and
`validate_case` rejects any case that declares fewer than both. If a
future change ever forked this resolution logic per Skill, that fork
would itself be the regression this corpus exists to catch — at which
point per-Skill fixtures would become meaningful and this structural
shortcut would need to be revisited.

## Categories and required outcome shapes

| Category | Required shape(s) |
| --- | --- |
| `structured_authorization` | canonical `allow_trusted_host_execution=true`/`=false`, sandbox unavailable |
| `direct_affirmative` | a direct, unambiguous affirmative natural-language authorization |
| `equivalent_affirmative_phrasing` | one case per affirmative phrase in the reference model's `TRUSTED_HOST_AFFIRMATIVE` vocabulary — differently-worded requests carrying the same intent |
| `explicit_denial` | one case per negative phrase in `TRUSTED_HOST_NEGATIVE` — forces `unavailable` even with sandbox unavailable |
| `ambiguous_non_authorizing` | vague helpfulness requests, a bare mention of "local," a question about availability or about the option itself — none ever resolve to authorization |
| `descriptive_non_authorizing` | discussing the feature, quoting the policy, asking how it works — none are mistaken for a grant |
| `repository_controlled_attempt` | README/AGENTS.md/CONTRIBUTING.md/code-comment/commit-message/issue-body content claiming authorization — rejected structurally by type, never by content inspection |
| `malicious_instruction_file` | content specifically crafted to impersonate a principal-originated authorization |
| `pr_content_escalation` | a PR description or review comment asserting the user already authorized trusted-host execution |
| `delegated_agent_attempt` | a spawned/delegated agent reporting back as if it received an authorization |
| `non_persistence` | an authorization valid for one invocation is not reused for a later invocation or a stateful re-review |
| `conflicting_instructions` | an affirmative and a negative signal in the same invocation fall through to denial; a structured `false` outranks an affirmative NL phrasing |
| `sandbox_preferred` | sandbox available always selects `sandbox`, regardless of a structured, NL, or absent authorization signal |
| `sandbox_unavailable_authorized` | sandbox unavailable, a valid structured or NL authorization, selects `trusted-host` |
| `sandbox_unavailable_unauthorized` | sandbox unavailable, no valid authorization, remains `unavailable` |

Every category listed above as required to resolve toward denial
(`explicit_denial` through `sandbox_unavailable_unauthorized`, minus the
two `sandbox_unavailable_authorized`/`sandbox_preferred` positive
categories) is enumerated in `DENIAL_REQUIRED_CATEGORIES` and
structurally checked, over the whole corpus, to never resolve `true` or
select `trusted-host` — see
`RequiredCategoryCoverageTests.test_every_denial_required_category_never_resolves_true`
and `StructuralOutcomeAssertionTests.test_no_denial_required_case_ever_actually_selects_trusted_host`.

## Repository test sandbox request (#535)

[#535](https://github.com/amirbena/code-review-skill/issues/535) adds a
second, separate case set, `SANDBOX_REQUEST_CASES`, for the repository
test sandbox request in
[`trusted-host-execution.md`](../../../../shared/policies/trusted-host-execution.md),
"Repository test sandbox request". It sits beside `ALL_CASES`, which is
unchanged, because its expected shape differs: `resolved` means "the
sandbox was requested", and an admitted repository test command's backend
is `host` by default rather than `unavailable`.

The cases cover the structured value, every closed request phrasing,
every trusted-host denial phrasing (which also requests the sandbox),
negative cases that leave the host default (no signal, the
`allow_trusted_host_execution=false` default, a negated phrasing, a
question, a bare "sandbox" mention), conflicts that resolve to the
sandbox (host-affirmative plus request, structured `false` plus request,
untrusted content trying to cancel it), untrusted content trying to make
the request, and the no-host-fallback case when no sandbox exists. Each
case runs once per Skill and the two outcomes must match.
`validate_sandbox_request_case` / `validate_sandbox_request_corpus`
enforce that `host` appears exactly when no request resolved, that
`trusted-host` never appears, and that untrusted-source and negative
categories never request the sandbox. `RepositoryTestSandboxRequestCorpusTests`
runs the set.

## Threat-model traceability

This domain has no dedicated `docs/threat-model/catalog/` entry yet —
unlike the delegation-spawn (`DELEG-###`) and sandbox-adversarial
(`SBOX-###`) corpora, #370 did not require adding one, and this corpus
does not invent scenario ids to cross-check against a catalog file that
does not exist. Coverage is instead tracked against #370's own Scope list
via `REQUIRED_COVERAGE_TAGS`, cross-checked structurally by
`RequiredCoverageTagCompletenessTests`. Should a future issue formalize a
`TRUST-###` (or similar) catalog family for this boundary, this corpus is
the natural target for a `benchmark_reference` cross-check exactly like
the two corpora above.

## Focused selection

Run this corpus independently of the rest of the benchmark suite:

```bash
python3 -m unittest tests.unit.benchmark.test_trusted_host_nl_authorization_corpus
```

exactly like every other `test_*_corpus.py` module under
[`../../../../tests/unit/benchmark/`](../../../../tests/unit/benchmark/)
(e.g. `test_delegation_spawn_corpus.py`) — no other benchmark case needs
to run first.

## Corpus validation

`trusted_host_nl_fixtures.validate_case` / `validate_corpus` reject a
malformed fixture: an unrecognized category, a non-empty-string
`case_id`/`description` missing, an empty `covers` set, a `skills` tuple
that is not exactly both Skills, a `provenance`/`resolved` pairing that is
internally inconsistent (`TRUSTED_HOST` without `resolved=True`,
`UNAVAILABLE` with `resolved=True`), or a `DENIAL_REQUIRED_CATEGORIES`
member that resolves toward authorization.
`MalformedFixtureRejectionTests` in the unit-test module exercises every
one of these against deliberately broken fixtures built from
`dataclasses.replace` over a real, passing case. The validator
deliberately encodes no runtime implementation internals — it is a clean
data schema, matching #370's own benchmark-layer scope.

## Non-goals

- Re-testing [#367](https://github.com/amirbena/code-review-skill/issues/367)'s
  structured-flag-only behavior or
  [#302](https://github.com/amirbena/code-review-skill/issues/302)'s
  sandbox isolation guarantees — those already have their own coverage
  (`TrustedHostExecutionBackend` in `test_runtime_validation.py`, and
  [`../sandbox-adversarial/README.md`](../sandbox-adversarial/README.md)
  respectively).
- Any change to the review-quality metrics under
  [`../../match-criteria.md`](../../../../runtime_platform/benchmark/match-criteria.md) and its siblings —
  this is a security-semantics benchmark, not a finding-quality one.
