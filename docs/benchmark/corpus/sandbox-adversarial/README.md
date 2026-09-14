# Sandbox Adversarial Benchmark

Repository-development artifact for Issue
[#306](https://github.com/amirbena/code-review-skill/issues/306),
depends on [#302](https://github.com/amirbena/code-review-skill/issues/302)
(the real sandbox runner) and maps to the `SBOX-###` scenarios in
[`../../../threat-model/catalog/sandbox-runtime-validation.yaml`](../../../threat-model/catalog/sandbox-runtime-validation.yaml)
(Issue [#300](https://github.com/amirbena/code-review-skill/issues/300)).

## Why this isn't a `benchmark-case/v1` corpus

Every other sub-corpus under [`../`](../README.md) uses the
`benchmark-case/v1` fixture format
([`../../fixture-format.md`](../../fixture-format.md)): a code patch plus
an expected set of review *findings*, scored for finding
precision/recall. That schema has no field for a capability boundary, a
resource ceiling, or a contained/denied/unavailable outcome, and — more
importantly — #306 requires these cases to run against the **real**
sandbox runner (`scripts/sandbox/`), never a fake or reference model.
Stretching the finding-shaped schema to also carry adversarial-payload
semantics would blur exactly the line #306 asks to keep sharp:

> Security-boundary results remain separate from finding
> precision/recall metrics.

So this corpus is not a set of fixture files at all. It **is** the real,
executable adversarial suite already required to exist for #302's own
"structural security proof":
[`../../../../tests/integration/sandbox/test_adversarial_containment.py`](../../../../tests/integration/sandbox/test_adversarial_containment.py).
Each test method there fires one real hostile payload (real subprocess,
real Docker container or real macOS Seatbelt profile — no mocked
isolation) and is a single case in this benchmark. A payload that
succeeds is a test failure; containment, denial, or an explicit
`unavailable` result are the only passing outcomes.

## Coverage

| `SBOX-###` | Threat | Case(s) |
| --- | --- | --- |
| SBOX-001 | outbound HTTP | `NetworkDenialTests::test_sbox_001_outbound_http_is_denied` |
| SBOX-002 | DNS resolution | `NetworkDenialTests::test_sbox_002_dns_resolution_is_denied` |
| SBOX-003 | raw socket connect | `NetworkDenialTests::test_sbox_003_raw_socket_connect_is_denied` |
| SBOX-004 | `$HOME`/`/root`, SSH agent, GitHub/cloud env credentials, browser/session credential stores | `CredentialAccessTests` (5 cases) |
| SBOX-005 | unrelated repo/host path reads, symlink escape, host-absolute-path write, path-traversal write | `FilesystemBoundaryTests` (host-path/traversal cases) |
| SBOX-006 | write to reviewed source | `FilesystemBoundaryTests::test_sbox_006_write_to_the_original_reviewed_source_is_unreachable` |
| SBOX-007 | `.git` config and hooks mutation | `FilesystemBoundaryTests` (git config/hooks cases) |
| SBOX-008 | GitHub/external write API call | `ExternalWriteApiTests::test_sbox_008_github_api_call_is_denied` |
| SBOX-009 | fork bomb / process-count budget | `ResourceExhaustionTests::test_sbox_009_process_count_budget_contains_a_fork_bomb` |
| SBOX-010 | wall-clock, CPU, memory, output, filesystem-growth budgets | `ResourceExhaustionTests` (5 cases) |
| SBOX-011 | descendant process and generated-artifact persistence past teardown | `PersistenceTests` (2 cases) |
| SBOX-012 | install/publish/deploy side effects | `NoMutationAuthorityTests::test_sbox_012_sandbox_cannot_install_or_publish_packages` |
| SBOX-013 | missing isolation primitive | `UnavailablePrimitiveTests::test_sbox_013_no_primitive_reports_unavailable_never_falls_back` |

## Invariant this corpus exists to guard

```
sandbox unavailable -> explicit `unavailable` result   (SBOX-013)
sandbox unavailable -> host execution fallback          NEVER
```

Every denied/terminated case additionally asserts, where applicable:

- the reviewed source tree and `.git` directory are byte-for-byte
  unchanged after the run (most directly in the `FilesystemBoundaryTests`
  cases, and structurally for every case via `SandboxRunner`'s own
  `verify_source_unchanged` fingerprint check);
- no disposable sandbox workspace, cache, or generated artifact survives
  teardown (`PersistenceTests::test_sbox_011_generated_artifacts_and_caches_do_not_persist_on_the_host`);
- no descendant process survives teardown
  (`PersistenceTests::test_sbox_011_background_process_does_not_survive_teardown`).

## `#299` security events

`docs/threat-model/catalog/sandbox-runtime-validation.yaml`'s
`expected_security_event` field is **provisional** pending
[#299](https://github.com/amirbena/code-review-skill/issues/299) (the
security-event class taxonomy is not yet implemented). This corpus does
not assert on emitted events for that reason — only on the observable
sandbox `Outcome` and on host/source state.

## Running just this benchmark

```bash
python3 -m pytest tests/integration/sandbox/test_adversarial_containment.py -v
```

A primitive genuinely absent from the host (no Docker, no Seatbelt, no
bwrap) skips the whole suite rather than silently passing — see
[`../../../../tests/integration/sandbox/_harness.py`](../../../../tests/integration/sandbox/_harness.py).

## Validation

Exercised by the repository's normal test run
(`python3 -m unittest discover tests` / `pytest`) and by
[`scripts/security/validate_threat_model.py`](../../../../scripts/security/validate_threat_model.py),
which checks that every `SBOX-###` scenario's `benchmark_reference` is a
well-formed, non-`COVERAGE_GAP` pointer into this corpus.
