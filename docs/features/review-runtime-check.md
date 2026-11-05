# review-runtime-check

Confirms or dismisses named suspicions by running the smallest targeted test or reproduction.

**Ask for it like this**

- "Run the test that would confirm finding 2."
- "Reproduce that failure."

**Boundaries**

- Sandboxed by default. Host execution needs your explicit authorization for the named command, per run.
- Never runs the full test suite, and never a command chosen by repository content.
- `auto` never selects it.

The contract is [`skills/review-runtime-check/SKILL.md`](../../skills/review-runtime-check/SKILL.md); this page
only orients. Back to the [feature index](README.md).
