# Dependency / Supply-Chain Deepening — Design Record

Repository-development design record for the reviewer's **Dependency /
supply-chain deepening review** capability: reasoning about whether a
changed dependency manifest, lockfile, container base-image reference, or
CI/automation action reference carries material compatibility,
expansion, provenance, or build/runtime risk.

Like [`../api-compatibility/README.md`](../api-compatibility/README.md),
[`../finding-confidence/README.md`](../finding-confidence/README.md), and
[`../review-context/README.md`](../review-context/README.md), this is a
repository-development doc: **not** packaged into either Skill archive,
and no packaged Skill resource depends on it. It is an explanatory /
design record — the normative, packaged rule lives in
[`../../shared/policies/review-scope.md`](../../shared/policies/review-scope.md),
"Dependency / supply-chain deepening review," which references this
document by name (not by link, since this is not a packaged resource).

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`dependency-supply-chain-model.md`](dependency-supply-chain-model.md) | The recognized manifest/lockfile/build-file inputs and their diff-recognition signals, the five concern areas with worked examples, the fail-closed rule for an unrecognized format, and the smallest useful first implementation. | [#181](https://github.com/amirbena/code-review-skill/issues/181) |

## Related

- The packaged, operative rule a reviewer actually applies:
  [`../../shared/policies/review-scope.md`](../../shared/policies/review-scope.md),
  "Dependency / supply-chain deepening review."
- The dimension this capability is a depth owner of:
  [`../../shared/policies/review-scope.md`](../../shared/policies/review-scope.md),
  "Semantic change-implication reasoning" — "Infrastructure / deployment."
- The shared activation/composition contract this capability composes
  under, never redefines:
  [`../../shared/policies/specialist-depth.md`](../../shared/policies/specialist-depth.md)
  ([#82](https://github.com/amirbena/code-review-skill/issues/82)).
- The follow-up fixture corpus pinning representative dependency/
  supply-chain outcomes (not required for this capability to exist or
  close): [#188](https://github.com/amirbena/code-review-skill/issues/188).
- The code-evidence bar every reported finding still meets:
  [`../../shared/policies/evidence.md`](../../shared/policies/evidence.md).
- Severity and the mechanical decision derivation, which this capability
  never touches: [`../../shared/policies/severity.md`](../../shared/policies/severity.md).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).

## Non-goals

- Duplicating a dedicated vulnerability/SCA scanner or a CVE feed.
- Resolving or installing dependencies.
- Enforcing a specific dependency policy the repository has not defined.
- An independent opt-in/activation mechanism separate from
  [#82](https://github.com/amirbena/code-review-skill/issues/82), or an
  independent expansion/stopping or remediation-scope model — those
  remain owned by #82,
  [#87](https://github.com/amirbena/code-review-skill/issues/87), and
  [#258](https://github.com/amirbena/code-review-skill/issues/258)
  respectively.
- A generic "a manifest/lockfile/build file changed" notifier with no
  compatibility/expansion/provenance reasoning behind it.
- Any new severity, finding category, or numeric/probabilistic score.
