---
name: github-pr-review
version: 3.3.1
description: Review an existing GitHub pull request and return or publish evidence-backed P0/P1/P2 findings.
---

# github-pr-review

Compatibility entrypoint for the v2 name. It reviews a GitHub pull request
by delegating to `review-core`.

When the user asks to review a pull request, run `review-core` on that PR
and return its report. Everything else — scope, severity, evidence, the
decision and the safety guarantees — is `review-core`'s and is not
restated here.

This Skill never publishes on its own. Posting a review to GitHub happens
only when the user explicitly asks for it in this conversation, and is
handled by `review-publish-github`.

Requires `review-core`; publishing also requires `review-publish-github`.
If a required Skill is not installed, stop and ask the user to install it.
