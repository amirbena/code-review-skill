# Review reasoning

The goal is the defects that would hurt someone if this change shipped,
found with evidence and nothing invented.

## Understand the change

State, for yourself first and then in the report summary, what the change
does and **which behavior changes**: what a caller, user, operator or
stored record sees before and after. Tests, configuration, migrations,
schemas and documentation in the change are part of it.

Start from the diff, then read enough of each changed file to judge every
hunk in its context:

- **By default, read the changed file in full.** This is how you see
  state, invariants and other code in the same file that the change
  affects.
- **For a large file (roughly 500 lines or more) with a localized
  change,** read the whole definitions that enclose each hunk
  (`git diff --function-context`, or the definition itself), the file's
  declarations (imports, types, fields, constants, signatures), and every
  use in that file of a symbol the change adds, removes or alters. Read
  further only when an investigation needs it.

## Direct references

When the change alters a contract (a public or exported signature, a
return value, a raised error, a default, a config key, a schema or
serialized field, a route, an event or a CLI flag), search once for its
uses outside the diff with `git grep -n -w '<name>'`. Search for the
name as a string too, so config, registries and routes show up. Read the
call sites that could break, starting with the closest ones, and stop
after about ten. This is one hop: callers of a caller are
`review-deep-investigation` work.

A text search misses dynamic dispatch, reflection, dependency-injection
or config wiring and calls from other languages. When one of those may
reach a changed contract and you could not check it, list it as not
investigated.

## Implication checklist

For each behavior change, ask:

- **Callers:** who calls or depends on what changed, and do they still
  get what they rely on?
- **Contracts:** did a public signature, API response, event, file format,
  config key or CLI flag change in a way existing consumers break on?
- **Data:** can stored or in-flight data become wrong, lost, duplicated or
  unreadable, including during a rollout or rollback?
- **Security:** does the change touch authentication, authorization,
  input handling, secrets or trust boundaries?
- **Failure paths:** what happens on errors, timeouts, empty or missing
  values, retries and concurrent use?
- **Tests:** is the changed behavior tested, and do existing tests still
  describe the new behavior?

The checklist points where to look. It is not a report section, and an
item with nothing to say is skipped.

## Bounded investigation

When something looks wrong, investigate it before deciding:

1. Name the suspicion in one sentence: which input or state leads to
   which wrong result.
2. Follow that execution path through the changed code and its direct
   dependencies: the functions it calls, the callers of what changed, and
   the types, config and data it reads.
3. Stop as soon as the code confirms or dismisses the suspicion. Do not
   widen the search to unrelated modules or keep tracing past the point
   where the answer is clear.

When a suspicion can be settled only by going beyond that bound, do not
guess. In `intent`, ask before running `review-deep-investigation`; in
`auto`, add it. Without it, list the concern as not investigated.

## Credible-defect bar and candidate validation

A candidate becomes a finding only when all of these hold:

- it is caused or exposed by this change, not a pre-existing issue the
  change does not touch;
- a concrete input, state or sequence leads to the wrong result;
- the code you read shows it, and nothing you read prevents it, such as a
  guard, a validator, a caller's precondition or a test;
- it matters to behavior, safety, data or maintainability, not to taste.

Before keeping a candidate, look once for the reason it might be wrong:
the guard elsewhere, the caller that never passes that value, the
framework default. Drop it if that reason holds. Prefer no finding to a
speculative one, but never drop a confirmed defect to keep a report
short.

## Root-cause dedup

When several symptoms come from one cause, report one finding at the
cause's location and mention the other affected locations in its
evidence. When one location has two independent causes, report two
findings. Never repeat a finding under a second title.
