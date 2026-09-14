# Threat-Scenario Catalog

The canonical, machine-checkable adversarial-scenario catalog for
[#300](https://github.com/amirbena/code-review-skill/issues/300). Not
packaged; explanatory data consumed by repository-development tooling and
by the runtime-enforcement issues in
[`../README.md`](../README.md). See
[`../threat-model.md`](../threat-model.md) for the trust-domain
architecture this catalog implements.

## Layout

One file per threat domain, each holding every scenario in that domain as
a `threat-scenario-catalog/v1` document:

| File | Category | Scenarios | Enforcement owner |
| --- | --- | --- | --- |
| [`mutation-authority.yaml`](mutation-authority.yaml) | `AUTH` | 16 | [#301](https://github.com/amirbena/code-review-skill/issues/301) |
| [`spawn-delegation.yaml`](spawn-delegation.yaml) | `DELEG` | 11 | [#303](https://github.com/amirbena/code-review-skill/issues/303) |
| [`sandbox-runtime-validation.yaml`](sandbox-runtime-validation.yaml) | `SBOX` | 13 | [#302](https://github.com/amirbena/code-review-skill/issues/302) |
| [`repository-prompt-injection.yaml`](repository-prompt-injection.yaml) | `INJECT` | 6 | mixed — see each scenario's `enforcement_owner` |
| [`checkout-git-safety.yaml`](checkout-git-safety.yaml) | `GIT` | 9 | mixed — several already `existing:` |
| [`scope-evidence-integrity.yaml`](scope-evidence-integrity.yaml) | `SCOPE` | 6 | mixed — mostly decision-semantics correctness |
| [`resource-abuse.yaml`](resource-abuse.yaml) | `DOS` | 7 | shared with `#302`/`#303` |

Validated by the single reference validator,
[`../../../scripts/security/validate_threat_model.py`](../../../scripts/security/validate_threat_model.py)
— never a second one. Run it directly with:

```bash
python3 scripts/security/validate_threat_model.py
```

or through the test suite: `python3 -m unittest tests.unit.security.test_validate_threat_model`.

## Format: `threat-scenario-catalog/v1`

Each file is a mapping:

```yaml
format: threat-scenario-catalog/v1
category: AUTH          # one of AUTH/SBOX/DELEG/INJECT/GIT/SCOPE/DOS
scenarios:
  - id: AUTH-001
    ...
```

### Scenario fields

Every scenario is a mapping with exactly these keys (`notes` optional,
everything else required):

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string, `<CATEGORY>-<3 digits>` | Stable identifier, assigned deliberately — never derived from a test filename or line number, and never renumbered when a scenario is reworded or a file is moved. |
| `title` | string | One-line scenario summary. |
| `category` | one of `AUTH`/`SBOX`/`DELEG`/`INJECT`/`GIT`/`SCOPE`/`DOS` | Must match the `id` prefix and the file's own `category`. |
| `attacker_model` | one of the six §4 values in [`../threat-model.md`](../threat-model.md) | `malicious_contributor`, `prompt_injected_context`, `compromised_agent`, `confused_deputy`, `runtime_misconfiguration`, `resource_abuse`. |
| `attacker_controlled_inputs` | list of strings, non-empty | What the attacker/condition actually controls in this scenario. |
| `assumed_attacker_capabilities` | list of strings, non-empty | What capability the attacker is assumed to already have (e.g. "authorship of arbitrary repository content") — never "the model decides to misbehave." |
| `trusted_inputs` | list of strings, may be empty | Any input this scenario treats as trusted context, when relevant. |
| `protected_asset` | string | The boundary/asset the scenario protects. |
| `required_capability_state` | string | The capability state that must hold for the safe outcome (e.g. "no APPLY_PATCH capability granted"). |
| `enforcement_owner` | `COVERAGE_GAP`, an issue reference (`#301`), or an `existing: <path>` citation | Who is responsible for the runtime check. Must agree with `enforcement_point` (§ "Coverage-gap semantics"). |
| `enforcement_point` | `COVERAGE_GAP` or a description | Where in the runtime the check happens. |
| `expected_safe_outcome` | string | The observable, capability-level outcome when the attack is attempted. |
| `expected_security_event` | one of the provisional event classes, or `NOT_APPLICABLE` | See "Provisional event taxonomy" below. |
| `benchmark_family` | comma-separated list from `mutation/#305`, `sandbox/#306`, `delegation/#307`, `security-event/#308`, `none` | Which benchmark issue(s) this scenario belongs to. `none` requires a justification in `benchmark_reference`, never a bare gap. |
| `benchmark_reference` | `COVERAGE_GAP`, a real path/issue reference, or (when `benchmark_family: none`) a justification sentence | The actual benchmark case, when one exists. |
| `regression_evidence` | `COVERAGE_GAP` or a real path/issue reference | The actual regression test proving this scenario, when one exists. Never a prose description of absence — use `COVERAGE_GAP` and put explanation in `notes`. |
| `threat_severity` | one of `CRITICAL`/`HIGH`/`MEDIUM`/`LOW` | A closed set **distinct from** review-finding `P0`/`P1`/`P2` (see [`../threat-model.md`](../threat-model.md), §9). The validator rejects a `P0`/`P1`/`P2` token here. |
| `notes` | string, optional | Nuance that doesn't fit a structured field — e.g. why a scenario shares an enforcement point with another id, or what a partial existing mitigation covers. |

### Coverage-gap semantics

Because `#301`/`#302`/`#303`/`#305`/`#306`/`#307`/`#299`/`#308` are
unmerged or not yet started, most scenarios legitimately have:

```yaml
enforcement_owner: COVERAGE_GAP      # or an issue ref, e.g. "#301"
enforcement_point: COVERAGE_GAP
benchmark_reference: COVERAGE_GAP
regression_evidence: COVERAGE_GAP
expected_security_event: NOT_APPLICABLE   # only when the outcome is not itself a denial
```

`COVERAGE_GAP` and `NOT_APPLICABLE` are literal, machine-detectable
tokens — never an empty string, an omitted field, or a prose sentence
describing the gap (that explanation belongs in `notes`). The validator
enforces this: `enforcement_owner` and `enforcement_point` must **agree**
on whether a real owner exists (one cannot be `COVERAGE_GAP` while the
other names a real reference), and every non-gap reference field must be
syntactically well-formed — a real repository path (`tests/`, `docs/`,
`shared/`, `skills/`, `scripts/`), an `existing: ...` citation, or an
issue reference (`#NNN`) — **well-formed, not necessarily resolvable
yet**, per #300's own constraint never to invent a fake file/line
reference for unlanded `#301`/`#302`/`#303` work.

### Provisional event taxonomy

`expected_security_event` draws from a small, fixed vocabulary defined in
[`../../../scripts/security/validate_threat_model.py`](../../../scripts/security/validate_threat_model.py)
(`PROVISIONAL_EVENT_CLASSES`) — for example
`DENIED_MUTATION_UNAUTHORIZED`, `DENIED_SANDBOX_NETWORK_ACCESS`,
`DENIED_SPAWN_BUDGET_EXCEEDED`. These are **provisional**: `#299` owns the
real, authoritative event taxonomy and may rename, split, or merge these
classes when it lands. `NOT_APPLICABLE` is used when the scenario's safe
outcome is not itself a capability denial (a reasoning-discipline
scenario, a decision-semantics correctness property, or a genuine
platform-unavailability outcome).

## Traceability

For any scenario id, the schema alone answers:

- **Which enforcement component owns it** — `enforcement_owner` /
  `enforcement_point`.
- **Which regression proves it** — `regression_evidence` (or
  `COVERAGE_GAP`).
- **Which benchmark case exercises it** — `benchmark_family` /
  `benchmark_reference` (or `COVERAGE_GAP`).
- **Which denied-capability event should fire** —
  `expected_security_event` (provisional pending `#299`).
- **Whether any layer is missing** — any of the four reference fields
  equal to `COVERAGE_GAP`.

This is the structural contract
[#310](https://github.com/amirbena/code-review-skill/issues/310) is
designed to query mechanically, and the one
[#305](https://github.com/amirbena/code-review-skill/issues/305)/[#306](https://github.com/amirbena/code-review-skill/issues/306)/[#307](https://github.com/amirbena/code-review-skill/issues/307)
select their category's required scenarios from by filtering
`category`/`benchmark_family`, never by re-deriving their own scenario
list.

## Non-goals

- A second parser/validator competing with
  `scripts/security/validate_threat_model.py`.
- Benchmark fixtures themselves (owned by `#305`/`#306`/`#307`).
- Security-event recording or emission (owned by `#299`/`#308`).
- Any enforcement implementation (owned by `#301`/`#302`/`#303`).
- Redefining review-finding severity, verdict, or mutation semantics
  already owned by `shared/policies/`.
