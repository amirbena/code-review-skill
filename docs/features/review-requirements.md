# review-requirements

Checks the change against a Jira key, GitHub Issue or acceptance criteria you supply, with a status and evidence per requirement.

**Ask for it like this**

- "Does this meet PROJ-123?"
- "Check this against these acceptance criteria: ..."

**Boundaries**

- Needs a reference you supply in this conversation; it is never inferred from a branch name, commit or PR text.
- Jira and Issue reads are read-only; an unresolved reference ends the run `REVIEW INCOMPLETE`.

The contract is [`skills/review-requirements/SKILL.md`](../../skills/review-requirements/SKILL.md); this page
only orients. Back to the [feature index](README.md).
