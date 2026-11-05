# v2 retirement record

Explanatory record for [#849](https://github.com/amirbena/code-review-skill/issues/849),
under the [v3 ADR](adr-v3-review-core.md) (§6, §8, §10). It lists what the
retirement removed from `release/v3`, the purpose bucket of every deleted
test module, and where each guarantee that survives is now checked. It
changes no behavior of the v3 Skills.

## Purpose buckets

| Bucket | Meaning |
| --- | --- |
| **P** | Pins the wording of a removed policy, runbook, template or design record. Guards no behavior. |
| **S** | Tests a Python shadow copy of a removed policy's decision table (`tests/reference/review/`). The copy was never shipped, so the test checked the copy against itself. |
| **F** | Fixtures, harness or loader for a mechanism ADR §6 removes (delegation, mutation pipeline, status check, policy loading, and so on). |
| **R** | Guards packaging, archive or release behavior of the two v2 archives. The generic mechanism is kept and tested; the v2-specific assertions are not. |

No deleted module guarded behavior that v3 keeps. Where a surviving
guarantee was exercised by one, the replacement is named below.

## Source trees

| Removed | Reason | v3 owner |
| --- | --- | --- |
| `skills/local-code-review/`, `skills/github-pr-review/` | The two v2 Skills ([disposition](packaged-file-disposition.md)). | `skills/review-core/`, `skills/review-publish-github/` |
| `shared/` (policies and templates) | Moved into the Core and the mini-skills, or removed. | The Skill that owns each rule (disposition table) |
| `capabilities/` and `scripts/capability_architecture/` | The capability-manifest and loading-inventory layer. | None: selection is model judgment under ADR §5.1 |
| `scripts/governance/canonical_homes*` | Registry of `shared/` anchors. | One owner per rule, by Skill name |
| `scripts/github_integration/{enforcement,status_publisher,required_check_setup,lifecycle_proof}.py` | Status check and required-check machinery. | `boundary.py` is kept for S7 |
| `scripts/packaging/generate_package_manifest.py`, `generate_skill_metadata.py` | Generated the v2 manifest and `metadata/skill.yaml` from capability manifests. | The v3 manifest is written by hand in #851 |
| `scripts/validation/context_size_report.py` | Measured the v2 §2 loading inventory. | None |
| `scripts/security/validate_threat_model_traceability.py` | Joined the threat model to the removed mutation, delegation and security-event corpora. | `validate_threat_model.py` is kept |
| `scripts/skill_metadata/` v2 checks | Required `metadata/skill.yaml`, shared-template markers and per-family layouts. | `frontmatter.py`: name equals folder, one-line description, optional strict `version` |

## Documentation removed

`docs/features/`, `docs/CODE_REVIEW_COMPARISON.md`, `docs/canonical-homes/`,
`docs/capability-architecture/`, and the design records of removed
mechanisms: `api-compatibility`, `candidate-finding-validation`,
`dependency-supply-chain`, `deployment-infrastructure`,
`engineering-design-review`, `finding-confidence`, `findings`,
`github-integration`, `reasoning-checkpoint`, `rendered-inspection`,
`repository-intelligence`, `review-base-policy`, `review-context`,
`review-result`, `review-telemetry`, `security-events`,
`workspace-sibling-context`, `benchmark-reference-dependency`,
`large-file-decomposition.md`, `runtime-parallelism.md` and
`github-review-status-mechanism-research.md`. Their git history keeps them.
Docs for the v3 Skills follow in [#850](https://github.com/amirbena/code-review-skill/issues/850).

## Deleted test modules

| Deleted | Bucket | Guarantee that survives, and where |
| --- | --- | --- |
| `tests/policy/review/**` (78 modules) | P | v3 structure is checked by `tests/unit/review/core/` |
| `tests/reference/review/**` (48 modules) | S | The v3 verdict rule is checked by `benchmark_blocking_verdict` (below) |
| `tests/unit/review/**` except `core/` (58 modules) | S | Tests of the shadow models above |
| `tests/policy/governance/`: `canonical_homes`, `capability_manifest_schema`, `skill_entrypoint_guards`, `skill_md_shared_template_declarations`, `skill_policy_inventory_810`, `contribution_ownership_policy` | P | Routing structure: `test_instruction_architecture.py` (rewritten, structural only) |
| `tests/policy/release/`: `changelog_semver_guidance`, `release_intent_precheck_232` | P | The checker itself: `tests/unit/release/` |
| `tests/policy/security/**` (3 modules) | P | `tests/unit/security/test_validate_threat_model.py` |
| `tests/policy/benchmark/*_docs.py` (11 modules) | P | The harness behavior: `tests/unit/benchmark/` |
| `tests/unit/benchmark/` corpus tests for `decision_derivation`, `delegation_spawn`, `github_enforcement_authorization`, `mutation_boundary`, `publication_mode`, `reasoning_checkpoint`, `security_event`, `trusted_host_nl_authorization`, `verdict_consistency`, `workspace_sibling` (corpus and harness), `dependency_tree`, `external_contract_context`, `scale_progressive_loading_proof`, `specialist_depth_progressive_loading_proof` | F | `test_blocking_verdict_corpus.py` keeps the P0/P1-never-clean check; S7 publication shapes: `tests/integration/github/test_review_publish_github.py`; S8 sandbox: `tests/integration/sandbox/` |
| `tests/unit/benchmark/`: `policy_loading_resumption`, `policy_read_verification`, `reviewer_brief_*`, `structured_result_properties` | F | None: loading inventory, Reviewer Brief and the v2 structured-result option are removed |
| `tests/unit/security/`: `mutation_authority`, `external_contract_context_security`, `workspace_sibling_context_security`, `multi_repository_membership`, `validate_threat_model_traceability` | S, F | S1 is stated in `review-core/rules/safety.md` |
| `tests/unit/github_integration/`: `enforcement`, `lifecycle_proof`, `required_check_setup`, `status_publisher` | F | `test_boundary.py` is kept for S7 |
| `tests/unit/capability_architecture/**` | F | None |
| `tests/unit/governance/test_context_size_report.py` | F | None |
| `tests/integration/github/test_pr_checkout.py` | S | Tests the shadow `pr_checkout` model. S10 is stated in `review-core/rules/safety.md` |
| `tests/integration/packaging/`: `generated_package_manifest`, `generated_skill_metadata`, `github_archive_content`, `local_archive_content`, `adapter_capability_subsets`, `hidden_runtime_dependency`, `ordinary_packaging_version`, `skill_tree_output`, `distribution_consumer_install` | R | Manifest path safety and script parity are kept (`test_manifest_path_safety.py`, `test_script_parity.py`); archive and tree checks return with the v3 manifest in #851 |
| `tests/integration/release/test_skill_archive_release_version.py` | R | `tests/unit/release/test_skill_version.py` and `test_release_finalization.py`; the archive-level check returns in #851 |
| `tests/repository/test_review_bucket_layout.py` | P | The buckets it watched no longer exist |
| `tests/support/`: `policy_docs`, `shared_policy_wiring`, `deepening_contract`, `benchmark_doc_contract`, `pr_simulation` | S | Helpers of the deleted modules |

Kept and unchanged in purpose: the packaging domain, release,
sandbox, GitHub-integration boundary, benchmark harness and validator
tests, and the CI-routing guards. `tests/unit/benchmark/test_production_adapter.py`
lost its structured-result boundary class, which exercised the removed
invocation options.

## Benchmark corpora

[#848](https://github.com/amirbena/code-review-skill/issues/848) moved the
active corpus to `benchmark-case/v3` and froze the original v2 corpus,
byte-identical, in `benchmark/corpus-v2/` for the experiments that pin its
bytes (including the concurrency campaign). The frozen archive is untouched.

This retirement removes from the **active** corpus the sub-corpora whose
mechanism the ADR removes and whose loader or test is deleted:
`delegation-spawn`, `github-enforcement-authorization`, `mutation-boundary`,
`publication-mode`, `reasoning-checkpoint`, `security-events`,
`trusted-host-nl-authorization`, `verdict-consistency`, `reviewer-brief`,
`dependency-tree-inspection`, `specialist-depth-progressive-loading-proof`
and `scale-progressive-loading-proof`. `benchmark/corpus-index.json` is
regenerated. The workspace-sibling, external-contract, multi-repository and
specialist-depth-composition sub-corpora stay in the active corpus with their
v3 conversion and tests.

The publication and trusted-host cases can be rebuilt for v3 from the frozen
archive, using the mappings in [`review-publish-github.md`](review-publish-github.md) and
[`review-runtime-check.md`](review-runtime-check.md). The deepening corpora and
the remaining cases stay; some of their prose still names v2 paths.

## Left for later children

- **Benchmark adapter.** `benchmark_review_adapter.py` and `run_benchmark.py`
  still invoke the v2 `local-code-review` name; they move to `review-core` or
  the compatibility wrapper with #851.
- **Packaging and release.** `package-manifest.json` declares no Skill, so the
  build produces an empty tree manifest. Registering the v3 Skills, the
  pre-release no-`version:` rule and the archive checks are #851. The release
  tooling's semantics are unchanged.
- **Release and distribution text.** `docs/RELEASE.md`, `docs/distribution.md`, the `distribution/` plugin descriptions and the asset names in `release-publish.yml` still describe the two v2 archives. They belong to the published v2 line and change with the cutover (#851).
- **Docs.** The v3 README, per-Skill docs and migration guide are #850.
