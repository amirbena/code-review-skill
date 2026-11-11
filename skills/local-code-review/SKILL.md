---
name: local-code-review
version: 3.3.1
description: Review local Git changes and return evidence-backed P0/P1/P2 code-review findings.
---

# local-code-review

Compatibility entrypoint for the v2 name. It reviews local Git changes by
delegating to `review-core`.

When the user asks to review local changes, run `review-core` on the local
change and return its report. Everything else — scope, severity, evidence,
the decision and the safety guarantees — is `review-core`'s and is not
restated here.

Requires `review-core`. If it is not installed, stop and ask the user to
install it (`review-core` is invocable directly, with the same result).
