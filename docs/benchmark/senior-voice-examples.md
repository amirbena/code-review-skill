# Senior Voice — Paired Before/After Reference Examples

A documented reference set for Issue
[#231](https://github.com/amirbena/code-review-skill/issues/231)
(implementing the voice-quality contract validated in
[#229](https://github.com/amirbena/code-review-skill/issues/229)): eight
findings, each rendered as the structured field-oriented block and as the
senior/human voice from
[`../../shared/templates/finding-rendering.md`](../../shared/templates/finding-rendering.md),
"Senior voice contract", side by side.

This is a **documented reference set, not a CI gate** — unlike
[`corpus/`](corpus/README.md) (the #40/#41 benchmark machinery, driven by
`benchmark-case/v1` fixtures and scored by a runner), nothing here is
consumed by a test or a runner. It exists so a reviewer of a future voice
change has worked examples to compare against, and so the rubric in #229
("Quality eval") has a concrete corpus to point at. Like the rest of
[`docs/benchmark/`](README.md), it is a repository-development document:
not packaged into either Skill archive, and no packaged Skill resource
depends on it.

## How to read each pair

- The **structured** rendering is [`finding-rendering.md`](../../shared/templates/finding-rendering.md),
  "Canonical full rendering" — the default, always-available form.
- The **senior** rendering applies the "Senior voice contract" the same
  rendering file owns.
- Both renderings are the **same finding** — identical identity, severity,
  location, and evidence bar. Only the wording differs.
- Each pair is annotated with which voice principle(s) from the contract
  it demonstrates, per #229's rubric: defect-first, no repetition,
  severity-proportional tone, required vs. optional, and repo-specific
  wording.

## 1 — P0, security (decisive, no hedging)

**Structured**

```markdown
### F1 [P0] Path traversal in report export bypasses the sandbox root

- **Location:** `app/exports.py:63`
- **Evidence:** `export_report(name)` joins the caller-supplied `name`
  directly onto `SANDBOX_ROOT` with `os.path.join`, without resolving or
  rejecting `..` segments.
- **Impact:** A caller can read or overwrite any file the process can
  reach, outside the intended export sandbox.
- **Fix:** Resolve the joined path and reject any result outside
  `SANDBOX_ROOT`, or use a path-safe join helper that already does.
```

**Senior**

```markdown
### F1 P0: Path traversal in report export bypasses the sandbox root

`app/exports.py:63`

`export_report(name)` joins the caller-supplied `name` directly onto
`SANDBOX_ROOT` with `os.path.join`, so a `name` containing `..` segments
escapes the sandbox and reaches any file the process can read or write.
Resolve the joined path and reject any result outside `SANDBOX_ROOT`
before this ships.
```

Demonstrates: decisive P0 tone, no hedging or question, required fix
stated directly (never "I'd resolve the path…").

## 2 — P1, correctness (no first-person on a required fix)

**Structured**

```markdown
### F2 [P1] Paginated file listing stops after page 1

- **Location:** `app/github_client.py:88-104`
- **Evidence:** `list_files()` reads only the first page returned by the
  GitHub API and does not follow the response's pagination cursor.
- **Impact:** A large PR's file list is silently truncated, so files
  outside the first page can reach a clean review decision unreviewed.
- **Fix:** Exhaust pagination and verify scope completeness before
  permitting a clean decision.
```

**Senior**

```markdown
### F2 P1: Paginated file listing stops after page 1

`app/github_client.py:88-104`

`list_files()` reads only the first page, so a large PR can reach a
clean review decision with files that were never seen. Exhaust the
pagination before permitting a clean decision.
```

Demonstrates: the required correction ("Exhaust the pagination…") is
stated as an outcome, not a first-person preference — the gap #229 named
("no P0/P1 senior exemplar existed").

## 3 — P2, quality (proportional tone, optional framing)

**Structured**

```markdown
### F3 [P2] Sync and async retry paths decide eligibility separately

- **Location:** `app/retry.py:41-58`
- **Evidence:** `should_retry()` in the sync flow and the inline check in
  `AsyncRunner.retry` independently implement the 429-handling decision
  and already disagree on it.
- **Impact:** The two flows can silently drift further apart whenever one
  is updated and the other is missed.
- **Fix:** Move eligibility into one helper that both paths call.
```

**Senior**

```markdown
### F3 P2: Sync and async retry paths decide eligibility separately

`app/retry.py:41-58`

`should_retry()` in the sync flow and the inline check in
`AsyncRunner.retry` already disagree on 429 handling. Move eligibility
into one helper that both paths call.
```

Demonstrates: same underlying fact stated once (the heading names the
duplication; the prose adds the concrete disagreement and the fix — see
"Semantic restatement, not lexical"), proportional P2 tone, no manufactured
urgency.

## 4 — P1, correctness (severity-proportional length, no boilerplate)

**Structured**

```markdown
### F4 [P1] Stale HEAD can still receive a formal review action

- **Location:** `skills/github-pr-review/policies/review-status-enforcement.md:112`
- **Evidence:** The review-action gate re-checks authorization but not
  whether `reviewed_head` still matches the PR's current HEAD before
  submitting `APPROVE`.
- **Impact:** A push that lands between analysis and submission can be
  approved without ever having been reviewed.
- **Fix:** Re-validate `reviewed_head == current HEAD` immediately before
  submission and abort with `NO NEW DELTA` handling on a mismatch.
```

**Senior**

```markdown
### F4 P1: Stale HEAD can still receive a formal review action

`skills/github-pr-review/policies/review-status-enforcement.md:112`

The review-action gate re-checks authorization but not whether
`reviewed_head` still matches the PR's current HEAD, so a push landing
between analysis and submission can be approved without ever being
reviewed. Re-validate the HEAD immediately before submission and abort on
a mismatch.
```

Demonstrates: no "The evidence shows…" / "The impact of this is…"
announcing sentences — evidence and impact are carried directly by the
prose; length stays proportional to the finding's real complexity.

## 5 — P2, no-op change (concise, one sentence is enough)

**Structured**

```markdown
### F5 [P2] Renamed helper still logs its old name

- **Location:** `app/logging_utils.py:19`
- **Evidence:** `configure_logger` was renamed from `setup_logger`, but
  its internal log line still reads `"setup_logger invoked"`.
- **Impact:** Log-based debugging references a function name that no
  longer exists in the codebase.
- **Fix:** Update the log line to the current function name.
```

**Senior**

```markdown
### F5 P2: Renamed helper still logs its old name

`app/logging_utils.py:19`

`configure_logger`'s log line still reads `"setup_logger invoked"` — its
pre-rename name. Update it to the current function name.
```

Demonstrates: length follows complexity — a trivial finding stays two
short sentences, no padding to match a template's usual length.

## 6 — P1, consolidated root cause (affected locations never dropped)

**Structured**

```markdown
### F6 [P1] `sanitize_path` bypass reaches two call paths

- **Location:** `app/pathsafe.py:5`
- **Affected locations:**
  - `app/reports.py:read_report` — routes user input through
    `sanitize_path` before this bypass
  - `app/exports.py:read_export` — same shared helper, same bypass
- **Evidence:** `sanitize_path` treats a leading `//` as already-absolute
  and returns it unchanged instead of rejecting it.
- **Impact:** Both callers inherit an unresolved traversal vector through
  one shared helper.
- **Fix:** Reject a leading `//` in `sanitize_path` itself, at the shared
  cause, rather than patching each caller.
```

**Senior**

```markdown
### F6 P1: `sanitize_path` bypass reaches two call paths

`app/pathsafe.py:5`

`sanitize_path` treats a leading `//` as already-absolute and returns it
unchanged, so both `read_report` and `read_export` inherit the same
unresolved traversal vector through this one helper. Reject a leading
`//` here, at the shared cause, instead of patching each caller.

Affected locations: `app/reports.py:read_report`, `app/exports.py:read_export`.
```

Demonstrates: the senior re-voicing still names every affected call path
— a consolidated finding's blast radius is never a casualty of the
prose re-voicing.

## 7 — P2, genuine open question (uncertainty as a question, not an assertion)

**Structured**

```markdown
### F7 [P2] `null` return on the settled-tradeoff path is unexplained

- **Location:** `app/reconcile.py:210`
- **Evidence:** The settled-tradeoff branch returns `null` to the caller
  with no comment, unlike every other branch, which returns a typed
  result object.
- **Impact:** A caller cannot distinguish "no conflict" from "not yet
  evaluated" without reading this function's source.
- **Fix:** If `null` here is intentional, document why; otherwise return
  the same typed result the other branches use.
```

**Senior**

```markdown
### F7 P2: `null` return on the settled-tradeoff path is unexplained

`app/reconcile.py:210`

Every branch but this one returns a typed result object; this one returns
bare `null` with no comment. Was routing the settled-tradeoff case to a
bare `null` here deliberate, or should it return the same typed result as
the other branches?
```

Demonstrates: genuine uncertainty is phrased as a question rather than
asserted as a defect — reserved for a real open question, not used to
soften a P0/P1's required fix.

## 8 — P1, evidence-only praise alongside a blocking finding (no manufactured praise)

**Structured**

```markdown
### F8 [P1] Config schema drift spans three unlinked files

- **Location:** `config/*.yaml` (schema vs. loader vs. docs)
- **Evidence:** `config/schema.yaml` declares `retry_budget` as required,
  `config/loader.py` still treats it as optional with a silent default,
  and `docs/config.md` doesn't mention the field at all.
- **Impact:** A deployment can pass schema validation while the loader
  silently ignores an operator's `retry_budget` override, with no
  documented way to notice.
- **Fix:** Make the loader honor the schema's `required` declaration (or
  relax the schema to match the loader), and update the docs to match
  whichever is authoritative.
```

**Senior**

```markdown
### F8 P1: Config schema drift spans three unlinked files

`config/*.yaml` (schema vs. loader vs. docs)

The schema declares `retry_budget` required, the loader still treats it
as optional with a silent default, and the docs don't mention it at all
— a deployment can pass schema validation while the loader silently
ignores an operator's override. Make the loader honor the schema's
`required` declaration (or relax the schema to match it), and update the
docs to match whichever is authoritative.

The schema/loader split for every other field stays consistent, which is
why this one stood out.
```

Demonstrates: the one line of praise is specific and evidence-backed (it
names what is actually consistent, not a generic compliment), appears
only because it is materially useful context for the reader, and is never
a required slot on a review that also has a blocking finding.

## Related

The voice contract these pairs render is owned by
[`../../shared/templates/finding-rendering.md`](../../shared/templates/finding-rendering.md),
"Senior voice contract". The #40/#41 finding-detection benchmark corpus is
[`corpus/`](corpus/README.md) and is unrelated to presentation quality.
