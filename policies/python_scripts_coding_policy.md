# Python Scripts Coding Policy

Authoring policy for this repository's own Python tooling — `scripts/**/*.py`
(validators, packaging helpers, reference/decision-table modules, and their
tests) and any other repository-owned Python.

This is **not** a universal Python style guide, and it is **not** packaged
into either Skill archive. Its purpose is narrow: keep repository Python
scripts readable by preventing long narrative comments and module docstrings
from becoming a second documentation layer.

Durable explanation about repository architecture, Skill packaging, runtime
boundaries, historical reasoning, policy ownership, or cross-Skill
relationships belongs in [`docs/`](../docs/), [`policies/`](.), or
[`shared/policies/`](../shared/policies/) — not repeated inside Python
implementation files. If it is already documented there, remove the
duplication rather than moving it to a new file.

## Comments and docstrings

**Default:** comments and docstrings in implementation files are short, local,
and necessary. Prefer code structure, naming, types, and small helper
functions over explanatory prose.

**Normal limit:** an ordinary explanatory comment or internal docstring is
usually 1 line, occasionally 2, and at most 3 concise lines when genuinely
needed. Three lines is a ceiling, not a target — not a mechanical rule.

### Keep a comment when it explains something the code cannot

- a non-obvious invariant;
- a safety constraint;
- a compatibility requirement;
- an external-system quirk;
- a subtle ordering requirement;
- a surprising decision branch;
- an intentional deviation from the obvious implementation.

```python
# Resolution must happen before scope reasoning; a Jira key alone
# is not usable task context.
if jira_reference:
    ...
```

```python
# Preserve policy order because the packaging validator checks it.
for policy in policies:
    ...
```

### Remove or shorten a comment that mainly explains

- what the next lines obviously do;
- repository history, or why a file was introduced in a previous change;
- which other files conceptually own the feature;
- packaging/runtime-boundary architecture already documented elsewhere;
- an extended restatement of a policy document;
- test philosophy or an implementation walkthrough.

```python
# Avoid:
# This function loops over all findings and then checks every severity
# and determines whether there is a P0 or a P1, because according to
# our shared severity policy either one should cause the final review
# decision to become CHANGES REQUIRED...

# Prefer:
# P0/P1 mechanically require CHANGES REQUIRED.
```

## Module docstrings

A module docstring says what the module is, in one line — occasionally with
one extra line for a constraint a reader genuinely needs. It does not
reproduce the policy the module mirrors.

```python
"""Test-only implementation of the shared severity-to-decision contract."""
```

or, when one detail matters:

```python
"""Test-only severity-to-decision model.

Used to verify shared policy semantics; not packaged at runtime.
"""
```

## Decision paths

A non-obvious decision path may keep a short comment (1–2 lines) immediately
above it. Do not narrate every branch.

```python
# Unresolved Jira context stops grading; continuing would invent scope.
if resolution_failed:
    return JIRA_CONTEXT_UNRESOLVED
```

If a branch needs more than 2–3 lines to understand, improve the naming,
extract a helper, or move the durable explanation to a policy/doc.

## Public / API docstrings

A function or class that forms a meaningful reusable interface may keep a
concise docstring covering purpose, important input/output semantics, and
exceptional behavior. Do not embed repository-architecture essays in it, and
do not mechanically strip useful API documentation — this policy reduces
noise, it does not eliminate documentation.

## Test files

Communicate intent through descriptive test and helper names and clear
assertions. Do not restate, in comments, a contract that already lives in a
policy file. A concise pointer is enough where useful:

```python
# Contract: shared/policies/severity.md
```

## Applying this policy

Apply it to Python files a change touches, and bring an edited file's
comments into line as part of that change. Surgical cleanup of existing files
is fine; do not rewrite functioning code, remove genuinely important
reasoning, or open a sweeping comment-only refactor of untouched files.
