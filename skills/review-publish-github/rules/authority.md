# Authority and event

## Who the reviewer is

Resolve the authenticated GitHub identity and the PR author. The review is a
**self-review** when any of these holds:

- the identity is the PR author;
- the identity shares the author's authority: a bot or service account, an
  alternate account or token, or a GitHub App identity that the agent which
  wrote or orchestrated the change can act as;
- either fact cannot be resolved with confidence.

A different login alone does not make a reviewer independent. Analysis is
never skipped for a self-review; only the event is limited.

## Event

| Situation | Event |
| --- | --- |
| Self-review, any decision | `COMMENT` |
| Draft PR, any decision | `COMMENT` |
| Fork PR whose upstream review permission is not confirmed | `COMMENT` |
| Decision `REVIEW INCOMPLETE` | `COMMENT` |
| Decision `CHANGES REQUIRED` | `REQUEST_CHANGES` |
| Decision `REVIEW CLEAN` | `APPROVE` |

A `COMMENT` carries the real decision in its summary. It never counts as an
approval and the decision is never rewritten to fit the event. An event the
repository refuses is reported, never retried as a stronger one.

## Fails closed

Publish nothing and report the review in the conversation when:

- the repository or PR cannot be reached with the identity;
- the identity lacks permission to submit a review (read access, an expired
  or insufficient token, or a refused submission);
- permission cannot be determined.

Never fake a publication, and never switch to another account or token to
get permission.

## Never

Merge, close, reopen, label, edit the PR, push, change the PR's draft state,
dismiss another reviewer's review, or approve a HEAD that is not the
reviewed HEAD.
