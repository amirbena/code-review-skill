# Execution

Every rule of `review-core`'s credible-defect bar and evidence rule still
applies. A run is evidence for one suspicion. It never widens the review.

## The smallest check

- Prefer an existing repository test that already exercises the suspected
  path, run as a focused selection (one test, file or node id).
- Generate a reproduction only when no existing test isolates the behavior.
  Make it one self-contained, deterministic script or test that asserts
  exactly one behavior. It exists only inside the sandbox's disposable
  workspace. Never write it into the user's repository, stage it, commit it
  or hand it back as a patch. Summarize its content as text.
- One check per suspicion. No matrix, no retry after a clean or
  inconclusive result.
- Do not run installs, builds, formatters, autofixers, migrations, deploys,
  publishes or anything that needs network, secrets, services or
  interaction. Inspect a task definition before running it; if it cannot be
  read without executing code, do not run it.

## Where it runs

- **Sandbox (default).** The check runs on a disposable copy of the reviewed
  tree with: no access to host secrets or credentials, network denied, no
  Git or GitHub write capability, bounded time, processes, memory and
  output, and nothing left behind. The sandbox is the repository's own
  backend or an equivalent the runtime supplies. If no backend can provide
  all of this, the sandbox is unavailable.
- **Host.** Only under S8. The authorization must name the command, come
  from the user in this conversation, and apply to this run only. It never
  carries over, and it never covers a different command. It changes where
  the command runs, not what may run: every rule above still holds.
- **Never fall back.** An unavailable sandbox is never a reason to use the
  host, and a failed or unverifiable sandbox run is never repeated on the
  host. Ask the user once whether to run on the host; only an explicit yes
  to that command runs it.

## After the run

Check that the reviewed tree and Git state are exactly as before and that no
generated file remains. If that cannot be verified, discard the result and
record `inconclusive` with that reason.

## Outcomes

- **confirmed** — the check failed exactly as the suspicion predicts.
- **dismissed** — the check passed and showed the code behaves correctly.
- **inconclusive** — the sandbox or host was unavailable or unauthorized,
  the check timed out, could not be made safe, failed to start, or neither
  confirmed nor disproved the suspicion. The finding keeps its static
  evidence and stays valid.

A launcher or setup failure is `inconclusive`, never `confirmed`. Report
the command, where it ran, the outcome and the bounded output for each one.
