# FULL CI and Skill-tree packaging cost profile

Evidence record for [#798](https://github.com/amirbena/code-review-skill/issues/798),
feeding [#793](https://github.com/amirbena/code-review-skill/issues/793) under Epic
[#786](https://github.com/amirbena/code-review-skill/issues/786). It measures; it
proposes no optimization and changes no gate. Not packaged into any Skill archive.

**Status: partial.** Local packaging evidence is recorded below. The CI-side
items (three cold FULL samples, tier durations from run metadata, derived
FAST/PARTIAL/DOCS sums, retention and SHA-256 of the raw JSON) are **pending**:
they need the measurement workflow to run on GitHub. Nothing below is a CI number.

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

## Rebuild inventory (static, unverified by fingerprinting)

Callers of `package-skills.sh`/`.ps1` in `validate.yml`: the `test` job (`all`, once)
and the `skill-tree-parity` matrix (shell and pwsh, `all`). Test callers
(integration packaging and release modules, `setUpClass`) and the `release-worthiness`
package job were **not** inventoried or fingerprinted. Identical-versus-distinct
classification, critical-path versus runner-minute effect, and the Windows multiplier
are pending.

## Ranked hotspots and #793 links

| Rank | Candidate | Evidence | Label |
| --- | --- | --- | --- |
| 1 | Per-file `adapt-shared-links` spawns in packaging | Local profile above | Candidate for #793; CI effect unproven |
| 2 | FULL test step (dominant in the `test` job) | Step totals only; per-test CI data pending | Not rankable until CI samples exist |

No proven benefit is claimed for either.
