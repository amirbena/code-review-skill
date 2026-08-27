# PYTHON_AUTHORING.md

Authoring policy for this repository's own Python (`scripts/*.py` —
validators, packaging helpers, reference/decision-table modules, and their
tests). It is a repository-development policy; it is **not** packaged into
either Skill archive and has no bearing on how the Skills review external
code. [`AGENTS.md`](AGENTS.md) carries only a one-line pointer to this file.

## Comment policy

Prefer self-explanatory code over commentary. The goal is clarity, not a
comment count.

- Remove redundant comments that merely restate what the code does.
- Remove large narrative/explanatory comment blocks when the code is
  understandable without them.
- Keep comments for information that cannot be expressed clearly through
  naming and structure.
- A normal explanatory comment is generally **1–3 lines**.
- When a branch or decision path is non-obvious, a short explanation
  immediately above it is appropriate.
- Complex decision logic may carry one or two concise lines explaining *why*
  the branch exists — not a narration of every operation inside it.
- **Preserve** comments that explain non-obvious invariants, safety
  constraints, compatibility requirements, external-system quirks, or
  intentionally unusual behavior.
- Do not delete a comment whose removal would make the code materially
  harder to understand.
- Avoid long prose blocks inside implementation files. Durable architectural
  or contractual explanation belongs in a policy or doc
  ([`shared/policies/`](shared/policies/), [`ARCHITECTURE.md`](ARCHITECTURE.md),
  a Skill's own `policies/`), not in a module docstring or comment block.

### Example

Good — explains a non-obvious external-system quirk and the resulting branch:

```python
# GitHub returns stale review threads too; only unresolved findings
# on the current head should influence the final decision.
if is_relevant_review_thread(thread):
    ...
```

Avoid — narrates the obvious, step by step:

```python
# First we iterate through all of the comments and then we inspect
# each comment and determine if it is relevant and then we check
# whether it was resolved and after that we decide whether it should
# be included in the resulting list...
```

## Module docstrings

A module docstring states what the module is and the one or two constraints a
reader genuinely needs (for example: "reference/decision-table module,
mirrors `<policy>`, not packaged, not runtime logic"). It is not the place to
reproduce the policy's reasoning — link to the policy instead.

## Applying this policy

Apply it to Python files you touch. When editing a file that predates this
policy, bring its comments into line with the rules above as part of the same
change, but do not open a sweeping comment-only refactor of untouched files.
