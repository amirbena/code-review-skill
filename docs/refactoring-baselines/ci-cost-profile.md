# FULL CI and Skill-tree packaging cost profile

Evidence record for [#798](https://github.com/amirbena/code-review-skill/issues/798),
feeding [#793](https://github.com/amirbena/code-review-skill/issues/793) under Epic
[#786](https://github.com/amirbena/code-review-skill/issues/786). It measures; it
proposes no optimization and changes no gate. Not packaged into any Skill archive.

**Status.** CI-side FULL samples, tier timings and a rebuild inventory are recorded
below. Not done: PARTIAL per-test sums (they depend on the changed paths of each PR),
the optional dependency scan (item 7), `package-skills.ps1` phase profiling, and a Linux
packaging profile. Findings are evidence for #793, not conclusions about safe savings.

## Tooling added

| Tool | Purpose |
| --- | --- |
| `scripts/validation/suite_timing_report.py` | Additive fields on `test-timing/v1`: `provenance`, per-run `counts` (ran/skipped/failed/errored), `cpu_seconds`, `environment.node`; `--provenance KEY=VALUE`. Existing readers are unaffected. |
| `.github/workflows/ci-timing-measurement.yml` | Non-required, `contents: read`, no secrets. Three independent fresh jobs, CI-order setup, `DISTRIBUTION_INSTALL_CHECK=1`, one cold run each, 30-day artifact. Triggered by `workflow_dispatch` or a draft PR touching the file. |
| `scripts/validation/packaging_profile.py` | Profiles `package-skills.sh` on a scratch copy via an interposed `python3` shim; the production script is untouched. |

## Rerun

```bash
python3 scripts/validation/packaging_profile.py --out /tmp/pkg.json
```

```bash
python3 scripts/validation/suite_timing_report.py --runs 1 --out /tmp/timing.json
```

Tier durations come from the jobs API (`gh api repos/OWNER/REPO/actions/runs/RUN_ID/jobs`,
step `started_at`/`completed_at`, for the 40 most recent `validate.yml` pull_request runs).
Derived tier sums: `ci_test_route.py run-fast|run-partial|run-docs --list`, summed over
the per-test data (these exclude per-run startup and fixture overhead).

## Packaging profile (local, one machine, one sample per row)

bash 3.2.57 (macOS), Python 3.14.6, sequential runs on one machine; compare shares, not seconds, with CI.
One bare `python3` start: 21 ms.

| Mode | Cold | Wall s | CPU s | python3 spawns | Spawn s | Shell/other s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| local | yes | 6.03 | 5.03 | 74 | 4.31 | 1.72 |
| local | no | 6.03 | 5.19 | 74 | 4.44 | 1.59 |
| github | yes | 7.22 | 6.19 | 88 | 5.27 | 1.95 |
| github | no | 11.58 | 6.42 | 88 | 8.65 | 2.92 |
| all | yes | 12.42 | 10.93 | 161 | 9.55 | 2.86 |
| all | no | 12.09 | 11.05 | 161 | 9.50 | 2.59 |

Phases for `all` (cold): `package_adapt.py adapt-shared-links` 134 spawns, 7.80 s
(about 63% of wall); `validate-skill-metadata.py` 4 spawns, 0.39 s; every other
phase 0.06–0.20 s. Manifest hashes were identical between cold and warm runs per mode.

Findings and limits:

- The per-Markdown-file `adapt-shared-links` loop dominates wall time. Interpreter
  start-up alone (21 ms x 134 spawns, about 2.8 s) is roughly a third of that phase's
  7.8 s; the rest is work inside each call plus the timing shim's own `perl`
  timestamps, and the split is not measured here.
- The `github` warm run (11.58 s) is an outlier against its cold run; variance was
  not characterised (one sample). Treat as noise until repeated.
- Shim overhead inflates every spawn; phase sums are within wall time by construction
  (spawn + shell/other = wall), not an independent check.
- The PowerShell script (`package-skills.ps1`) and a Linux runner were not profiled.

## FULL CI samples (3 cold jobs)

Run [39783067263](https://github.com/amirbena/code-review-skill/actions/runs/39783067263),
head `fb6538a`, base `c973e57`, merge `1877949f`; ubuntu-latest, Python 3.13.16, Node 22,
4 CPUs, `DISTRIBUTION_INSTALL_CHECK=1`. Each job: 6,738 ran, 7 skipped, 0 failed, 0 errored.
Samples 1 and 2 used runner image `20261021.345.10`, sample 3 `20261012.334.1`.

| Sample | Suite wall s | Sum of per-test s | Unattributed s | CPU s (incl. children) |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 330.2 | 281.2 | 49.0 | 262.0 |
| 2 | 302.2 | 257.8 | 44.4 | 228.9 |
| 3 | 274.5 | 234.8 | 39.7 | 205.9 |

The residual (13–15% of wall) is class/module fixtures and imports; it is not
attributed to tests. Median wall 302 s, range 274–330 s.

| Group | Median s | Range s |
| --- | ---: | ---: |
| `tests.unit` | 136.0 | 125.8–152.8 |
| `tests.integration` | 114.6 | 102.5–119.7 |
| `tests.policy` | 7.2 | 6.4–8.7 |

| Slowest modules | Median s | Range s |
| --- | ---: | ---: |
| `unit.benchmark.test_run_concurrency_experiment` | 52.9 | 50.3–56.8 |
| `integration.packaging.test_ordinary_packaging_version` | 41.7 | 37.1–45.0 |
| `integration.sandbox.test_adversarial_containment` | 38.3 | 38.2–38.5 |
| `integration.release.test_skill_archive_release_version` | 22.9 | 20.5–24.9 |
| `unit.governance.test_partial_routing` | 21.5 | 18.4–24.4 |
| `unit.benchmark.test_concurrency_campaign_config` | 9.1 | 7.9–11.0 |

The slowest single tests: a termination test in `test_run_concurrency_experiment` (31.2 s),
a CPU-budget test in `test_adversarial_containment` (25.1 s), and four to five 10–11 s
packaging/release tests that each run one build. Per-test figures are the median over
the three jobs.

## Tier timings from run metadata

Query: for each of the 40 most recent `validate.yml` `pull_request` runs (ids
38589099668 to 39783066741, newest listed 2026-10-22), `gh api
repos/OWNER/REPO/actions/runs/RUN_ID/jobs`, job `test`, step `started_at`/`completed_at`;
the tier is the `Run ...` step that succeeded. Two failed runs are excluded.

| Tier | Runs | Step seconds (min / median / max) |
| --- | ---: | ---: |
| FULL | 20 | 208 / 297 / 345 |
| FAST | 8 | 41 / 64.5 / 169 |
| PARTIAL | 4 | 23 / 168 / 170 |
| DOCS | 6 | 2 / 4 / 4 |
| Tree build step | 34 | 6 / 11 / 12 |

Derived from the FULL per-test medians: the router's FAST list (4,496 tests) sums to
50.4 s against a 64.5 s median step, and the DOCS list sums to about 2.3 s against 4 s;
the gaps are per-run startup and fixtures. PARTIAL cannot be represented without a
specific module set, so no sum is given. The two older FAST runs at 158–169 s remain
unexplained.

## Rebuild inventory

Per-PR-run callers of `package-skills`: the `test` job step (`all`, 6–12 s), the
`skill-tree-parity` jobs (bash `all`, 21 s; PowerShell `all`, 40 s on Windows, parallel
to `test`), and, only for release-worthy PRs, the `release-worthiness` package job
(skipped on this PR). Only `test` gates PR latency.

Test-driven builds were measured locally on a scratch copy, one module at a time, with a
logging wrapper around the script (input = hash of `skills/`, `shared/`,
`scripts/packaging/` and `CHANGELOG.md`; output = `dist/skills-manifest.json` hash):

| Module | Builds | Distinct inputs | Local s | Note |
| --- | ---: | ---: | ---: | --- |
| `packaging.test_ordinary_packaging_version` | 5 | 5 | 37.2 | 2 exit non-zero by design |
| `release.test_skill_archive_release_version` | 2 | 2 | 19.6 | |
| `packaging.test_skill_tree_output` | 2 | 1 | 18.5 | **identical input and output** |
| `packaging.test_distribution_consumer_install` | 1 | 1 | 10.2 | pristine `all` |
| `packaging.test_github_archive_content` | 1 | 1 | 5.1 | `github` |
| `packaging.test_local_archive_content` | 1 | 1 | 4.2 | `local` |

Of the 12 test builds, 4 are `all` on the pristine tree (output hash `7cb1394a926c`,
equal to the profiled build), so 3 are repeats of the same input; the CI `test`-job build
step is a fifth. The other builds vary version or changelog and are distinct by design.
`test_script_parity` failed under the wrapper (it compares the script itself) and is not
counted. Counts come from per-module runs; Windows/pwsh and CI timings were not
fingerprinted.

Critical path: removing a repeated build saves only on the `test` job (about 9 s locally
per identical pair; the real CI figure is unmeasured). Aggregate runner-minutes also
include the parity jobs; the Windows job carries a 2x multiplier on private repositories,
and this repository is public, so it is capacity and queue cost rather than spend.

## Ranked hotspots and #793 links

| Rank | Candidate | Evidence | Label |
| --- | --- | --- | --- |
| 1 | `test_run_concurrency_experiment` (53 s, 18% of test time; one 31 s termination test) | 3 CI samples, range 50–57 s | Largest single module; retention is tied to #683 |
| 2 | Packaging-heavy integration tests (`ordinary_packaging_version` 42 s, `skill_archive_release_version` 23 s, `skill_tree_output`) | 3 CI samples; build inventory | Three repeated pristine builds are a candidate; distinct-input builds are not |
| 3 | `adversarial_containment` CPU-budget test (25 s, deliberately a busy loop) | 3 CI samples | Likely inherent to what it tests |
| 4 | Per-file `adapt-shared-links` spawns inside the build | Local profile only | CI effect unproven |
| 5 | `test_partial_routing` (21.5 s; one exhaustiveness test 8 s) | 3 CI samples | Cause not investigated |

No proven benefit is claimed for any candidate. Findings are for ranking under #793.

## Raw data

Artifacts of run 39783067263 expire 2026-11-21 (30 days); the SHA-256 below pins the
files so a copy can be verified after expiry.

| File | SHA-256 |
| --- | --- |
| `timing-1.json` | `69cc8e12c29dc144441af1c619475b0687b2980d35c5aea904961b5e3e6cc209` |
| `timing-2.json` | `cf9ae3f0f5f9c23a8aa9e971e326e8b998b7b70a3e619a9c84c00b3e5d389cd3` |
| `timing-3.json` | `744e81675f0ac0249f28f0f68f67421c4fb71a7201ad5aceb78949ba679f852b` |
