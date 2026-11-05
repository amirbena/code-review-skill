# review-publish-github

Posts a finished review to its pull request as one batched review: inline comments, a summary and a review event.

**Ask for it like this**

- "Review PR 123 and post the review."
- "Publish that review to the PR."

**Boundaries**

- Runs only when you ask to publish; `auto` never adds it.
- Never approves its own work: a review of your own PR is a `COMMENT`.
- Revalidates the PR HEAD before submitting, never merges, submits exactly one review.
- A local change cannot be published.

The contract is [`skills/review-publish-github/SKILL.md`](../../skills/review-publish-github/SKILL.md); this page
only orients. Back to the [feature index](README.md).
