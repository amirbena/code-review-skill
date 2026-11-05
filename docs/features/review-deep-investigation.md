# review-deep-investigation

Lifts the Core investigation bound for suspicions that need more than one hop: wider tracing, root cause, affected tests, failure, retry and null paths.

**Ask for it like this**

- "Trace this root cause all the way through."
- "Which tests outside the diff does this change affect?"

**Boundaries**

- Read-only, using Git and grep only; it runs no project code.
- Never changes severity or the decision rule.

The contract is [`skills/review-deep-investigation/SKILL.md`](../../skills/review-deep-investigation/SKILL.md); this page
only orients. Back to the [feature index](README.md).
