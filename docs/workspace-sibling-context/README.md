# Workspace Sibling Context — Design Record

Repository-development design record for letting a `local-code-review`
review use bounded, caller-authorized **sibling-repository** evidence to
resolve one specific unresolved question before escalating it to the
engineer. Contract-first (#662), implemented for both adapters by #663. This
directory is not packaged; no packaged Skill resource depends on it.

Issue: [#662](https://github.com/amirbena/code-review-skill/issues/662)
(parent epic [#661](https://github.com/amirbena/code-review-skill/issues/661);
implementation #663, benchmark #664, Wiki #665).

## Document map

| Document | Owns |
| --- | --- |
| [`../../shared/policies/workspace-sibling-context.md`](../../shared/policies/workspace-sibling-context.md) | The **normative contract** — grant, discovery, nomination, selection basis, trust, failure, privacy. Canonical. |
| [`workspace-sibling-context-design.md`](workspace-sibling-context-design.md) | Why the contract is shaped this way: alternatives rejected, authorization-model reconciliation, threat-model mapping, what #663 must implement. Explanatory. |

## Core invariant

**Local evidence may nominate where to look; only the caller-authorized
workspace determines where the reviewer is allowed to look.**

## Related

- Explicit external-repository channel (unchanged, takes precedence):
  [`../../skills/local-code-review/policies/external-contract-context.md`](../../skills/local-code-review/policies/external-contract-context.md).
- Membership (unchanged): [`../../skills/local-code-review/policies/multi-repository-review-target.md`](../../skills/local-code-review/policies/multi-repository-review-target.md).
- Threat scenarios: INJECT-015–020 in [`../threat-model/catalog/`](../threat-model/catalog/README.md).
- Evidence model: [`../review-context/contextual-evidence-model.md`](../review-context/contextual-evidence-model.md).
