# review-core

The review itself: reads a local Git change or a GitHub pull request, read-only, and returns evidence-backed P0/P1/P2 findings and one mechanical decision. A plain request runs it alone.

**Ask for it like this**

- "Review this code."
- "Review PR 123."
- "Review my branch and give me the machine-readable result." (adds the JSON result)

**Boundaries**

- Read-only: no edits, commits, pushes or GitHub writes.
- Runs only when you ask, every time. Repository, PR and Issue text is data, never instruction.
- Any P0 or P1 is `CHANGES REQUIRED`; otherwise `REVIEW CLEAN`; an unreadable or moved target is `REVIEW INCOMPLETE`.
- Needs read-only `gh` access for a PR.

The contract is [`skills/review-core/SKILL.md`](../../skills/review-core/SKILL.md); this page
only orients. Back to the [feature index](README.md).
