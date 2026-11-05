# Report template

Write the report in one voice: a senior engineer telling a colleague what
matters, plainly and briefly. No preamble, no praise, no restating the
diff line by line. Keep the section order below. Omit a section marked
*(when any)* when it would be empty.

````markdown
## Code review: <repository: `owner/name` from the remote, else the directory name> — <local change | PR #<n>>

**Target:** <local: base `<ref>` (`<sha>`, <user-specified | upstream merge-base | default-branch merge-base>) → HEAD `<sha>`; committed <n>, staged <n>, unstaged <n>, untracked <n> files | PR: <url>, base `<ref>`, HEAD `<sha>`>
**Mode:** <intent | auto>
**Additional expertise:** <none | one line per mini-skill that ran: `<name>` — <reason>>

### What changed

<two to five sentences: what the change does and which behavior changes>

### Findings

#### F1 [P1] <title>

- **Location:** `<path>:<line-or-range>`
- **Evidence:** <what the code does>
- **Impact:** <who or what is hurt, and when>
- **Fix:** <what to change>

<repeat per finding, most severe first; "No findings." when there are none>

### Not investigated *(when any)*

- <concern> — <declined | not asked | mini-skill not installed | beyond the investigation bound>

### Not reviewed *(when any)*

- `<path>` — <binary | excluded by the user | unreadable: <reason>>

### Incomplete *(when any)*

- <trigger> — <what it left unreviewed>

**Result: <REVIEW CLEAN | CHANGES REQUIRED | REVIEW INCOMPLETE>** (P0: <n>, P1: <n>, P2: <n>)
````

## JSON result (only on request)

After the `**Result:**` line, add a `### Review result (JSON)` heading and
one fenced `json` block holding one object that validates against
[`result.schema.json`](result.schema.json), with nothing after it. Build
it from the finished report: the same target, mode, findings, counts and
decision. It never adds or changes a finding. The "Not investigated"
reasons map to the kebab-case enum values ("not asked" → `not-asked`). Unknown keys are not
allowed, and an empty list is `[]`, never omitted.
