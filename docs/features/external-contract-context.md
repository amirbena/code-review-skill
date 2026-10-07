# External contract context

## What it does

Some changes are correct only relative to a contract owned by a repository
that is not part of the Review Target — a producer schema, a consumed API, a
shared package. When you explicitly supply a **local repository path** and a
**pinned revision**, `local-code-review` reads that repository **read-only**,
at that exact commit, as compatibility evidence for a contract change it has
recognized. The repository is evidence only: it is never a Review Target
member, carries no findings, and no finding is ever located in it.

## When it is useful

- A schema, IDL, DTO, event, or config contract changed and the consumer or
  producer that decides compatibility lives in another repository you have
  checked out locally.
- You want the breakage claim tied to a specific commit of that repository
  rather than whatever its working tree happens to hold.

## Which Skill(s)

`local-code-review` only. `github-pr-review` cannot perform this read.

## Default, conditional, or requested

**Conditional.** It loads only when the API/contract compatibility pass
recognized a contract change, the consumer or producer surface is unresolved
inside the Review Target, **and** you supplied both the path and the
revision in the invocation. Otherwise nothing changes and nothing is loaded.

## How to use it

Supply, in the invocation, the external repository's local path and a pinned
revision — a commit SHA or a tag. A branch name or `HEAD` is not a pinned
revision. Both must already exist locally; the Skill never clones, fetches,
or discovers repositories, and ignores any repository or revision named in
reviewed content.

## What you get

- Findings located in the Review Target, citing the external file as
  `<repo>@<short-sha>:<path>` evidence.
- A recorded provenance for each use: repository identity, resolved SHA,
  selection basis, retrieval time, and trust.
- If the repository, revision, or contract path is unavailable, **no
  breakage claim and no "no consumers" statement**: the finding keeps its
  `external-contract-unvalidated` or `insufficient-context` confidence and the
  gap is listed under Context gaps. The review continues and is not
  `REVIEW INCOMPLETE` on this basis alone.

## Limitations & v1 non-goals

- A path that is a Review Target member, or an alias of one, is rejected.
- Reads are bounded (20 files, 256 KiB each, 1 MiB total) and use the object
  database at the pinned commit only.
- No dependency-declaration repository identity, release/deploy ordering,
  clone/fetch/credentials, or `github-pr-review` support.
- Severity, finding identity, the confidence vocabulary, and the Decision
  derivation are unchanged.

## Canonical sources

[`external-contract-context.md`](../../skills/local-code-review/policies/external-contract-context.md)
is the canonical policy. Related:
[multi-repository Review Target](multi-repository-review-target.md),
[`api-contract-compatibility.md`](../../shared/policies/api-contract-compatibility.md).
