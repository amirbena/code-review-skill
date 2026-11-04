# v3 Architecture — Design Record

Repository-development design record for **v3.0.0**: one small, read-only
Review Core plus independently selectable `review-*` mini-skills, replacing
the v2 two-Skill + `shared/` + `capabilities/` architecture.

Like the other records under `docs/`, this is explanatory and
repository-development only: it is **not** packaged into any Skill archive,
and no packaged Skill resource depends on it. It is docs-only and changes no
v2 behavior. v2.x stays the published line until the cutover (#851).

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`adr-v3-review-core.md`](adr-v3-review-core.md) | The decision: Core and mini-skill boundaries, final Skill names, activation model, removal list, safety guarantees S1–S10 with owners, the `release/v3` integration-branch strategy, and the repository-development rules that conflict with v3. | [#842](https://github.com/amirbena/code-review-skill/issues/842) |
| [`packaged-file-disposition.md`](packaged-file-disposition.md) | The disposition of **every** current packaged file (`skills/*/**`, `shared/**`): Core, a named mini-skill, or removed, with a one-line reason. | [#842](https://github.com/amirbena/code-review-skill/issues/842) |

## Epic and delivery

Parent Epic [#841](https://github.com/amirbena/code-review-skill/issues/841).
This ADR merges into `main` through the normal PR workflow and blocks
[#852](https://github.com/amirbena/code-review-skill/issues/852) (creates
`release/v3`) and
[#843](https://github.com/amirbena/code-review-skill/issues/843) (Review
Core). Every later v3 implementation PR targets `release/v3`; only
[#851](https://github.com/amirbena/code-review-skill/issues/851) cuts over
to `main`.

## Related

- Current (v2) system map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
- The repository-development rules v3 must rewrite:
  [`../../AGENTS.md`](../../AGENTS.md) "Skill instruction ownership",
  [`../../policies/skill-development-policy.md`](../../policies/skill-development-policy.md),
  [`../../policies/review-orchestration-policy.md`](../../policies/review-orchestration-policy.md)
  — itemized in the ADR, §8.
