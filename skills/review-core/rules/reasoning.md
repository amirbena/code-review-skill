# Review reasoning

The goal is the defects that would hurt someone if this change shipped,
found with evidence and nothing invented.

## Understand the change

State, for yourself first and then in the report summary, what the change
does and **which behavior changes**: what a caller, user, operator or
stored record sees before and after. Read each changed file in full, not
just its hunks, so a hunk is judged in its context. Tests, configuration,
migrations, schemas and documentation in the change are part of it.

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
