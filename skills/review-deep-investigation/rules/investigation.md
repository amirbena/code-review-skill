# Deep investigation

Every rule of `review-core`'s credible-defect bar, candidate validation and
root-cause dedup still applies. This skill changes how far the trace goes,
not what counts as a finding.

## Stop rule

Name the suspicion in one sentence, trace until the code confirms or
dismisses it, and stop. There is no hop limit, but each hop must follow
from the last: stop when the next one is unrelated to the suspicion, and
list the question as not investigated if it still cannot be settled.

## Investigation types

- **Multi-hop tracing.** Follow callers of callers, and the consumers of
  a changed contract past the Core's one direct-reference hop, with
  `git grep -n -w '<name>'` and the name as a string (config, routes,
  registries). Read the sites that could break. Use `git log -S '<text>'`
  or `-G '<regex>'` to find where a guard, check or default was removed or
  re-added, and `git show` what that commit changed and why.
- **Root cause and model completeness.** When symptoms share a cause,
  report the cause once, at its location. When a change adds a case to a
  set (an enum value, a status, a type, a route, a flag), find every place
  that enumerates or switches over that set, and check each handles the new
  case.
- **Affected tests.** Find the tests that cover what changed
  (`git grep` for the changed symbols under test paths). Judge whether each
  still describes the new behavior, and whether risky changed behavior has
  any test. A test you did not read is not evidence.
- **Failure and retry paths.** Follow errors, timeouts, partial failure and
  retries through the changed path: is the operation idempotent, is state
  left half-written, can a retry duplicate an effect?
- **Null and absence.** Follow empty, missing and default values from where
  they enter to where they are used, including values the change newly
  allows.

## What cannot be traced

A text search misses dynamic dispatch, reflection, dependency injection,
generated code and other languages. When one may reach the change and you
could not check it, list it as not investigated. Never state that nothing
else is affected.

## Report section

Add after "Findings":

```markdown
### Investigation

- <suspicion> — <confirmed as F<n> | dismissed: <reason, with `path:line`> | not settled: <what stopped it>>
  Traced: `<path>` → `<path>` (<`git grep` or `git log` used>)
```

One bullet per investigated suspicion. List only what was traced.
