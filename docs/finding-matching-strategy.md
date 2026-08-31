# Finding Matching Strategy — Research Recommendation

Repository-development research for GitHub Issue
[#59](https://github.com/amirbena/code-review-skill/issues/59). This document
selects the strategy for deciding whether a finding in a later review is the
same logical finding as one in an earlier reviewed state. It gives
[#60](https://github.com/amirbena/code-review-skill/issues/60) an
implementation-ready decision without implementing stable IDs, lifecycle,
review-delta semantics, or state loading.

The requirements remain canonical in
[`finding-identity-requirements.md`](finding-identity-requirements.md). This
document is the authoritative strategy record until #60 installs the chosen
runtime behavior in a packaged shared policy.

---

## Decision

Use a **precision-first staged hybrid** with a three-valued result:

```text
prior findings + current finding
        ↓
repository/path mapping and structural candidate generation
        ↓
require independent defect continuity + site continuity
        ↓
one uniquely supported pair? ── yes → MATCH
        │
        ├─ plausible evidence, but conflict/multiplicity? → AMBIGUOUS
        └─ otherwise → NO MATCH
```

The authoritative matcher is deterministic. It uses exact normalized
structural and code evidence first, then bounded textual similarity only to
retrieve or rank structurally plausible candidates. It does **not** add fuzzy
scores into a weighted confidence total. An LLM may explain or flag an
ambiguous pair for a human, but its judgment is never sufficient for automatic
identity reuse.

An automatic `MATCH` requires both:

1. **defect continuity** — the same faulty behavior/root cause remains; and
2. **site continuity** — the evidence belongs to the same logical program
   element or a deterministically traceable move of it.

Neither axis can substitute for the other. This prevents identical defects in
different functions from merging, and prevents a new defect at an old address
from inheriting the old identity.

When the evidence does not establish one unique one-to-one match, the matcher
returns `AMBIGUOUS` or `NO MATCH`; #60 mints a new identity. Candidate links may
be retained for diagnostics or future lifecycle handling, but do not transfer
identity.

## 1. Problem and constraints

Finding identity follows a defect, not a line, sentence, severity, review
surface, or commit SHA. It must survive line movement, formatting, nearby
edits, stable code moved within a file, reviewer wording changes, severity
changes, rebases, and local-review/PR-review handoff. It must separate
different defects, independent occurrences, a new defect at an old location,
and findings with different location intent.

The requirements impose an asymmetric error budget: a false split is visible
and recoverable; a false merge can silently suppress a real finding. Automatic
matching therefore optimizes precision before recall.

The reviewed-SHA contract in
[`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md) contributes
an authoritative prior/current revision boundary and an optional reference to
prior findings. It does not embed findings, match them, or validate an
untrusted/ambiguous prior state. If that state cannot seed a safe comparison,
the enclosing re-review falls back to a full review; this matcher must not
invent a predecessor.

### Available inputs and portability boundary

Both Skills can provide repository identity, normalized repository-relative
path (or no-single-file intent), title, evidence, impact, fix, the changed set,
and current file content. Line/range, enclosing symbol, construct type,
surrounding context, rename information, and prior findings are conditional.

The matcher must not require a language server, parser per language, semantic
index, network service, runtime observations, Git history beyond the compared
states, PR-only metadata, local-state annotations, severity, absolute line,
or generated prose to remain word-for-word stable.

### Existing mechanisms are not reused as cross-review identity

- `F1`, `F2`, ... are per-review display ordinals.
- `github-pr-review` suppresses duplicate publication on the **same HEAD**
  using HEAD SHA, exact location, severity, and normalized title/category.
  Those volatile inputs make it intentionally unsuitable across revisions.
- `local-code-review`'s staged-delta SHA-256 fingerprint identifies the exact
  staged content state. It neither identifies individual findings nor covers
  committed, unstaged, or untracked content.

The new matcher may reconcile with same-HEAD evidence, but it must not inherit
these mechanisms' narrower identity definitions.

## 2. Evidence model

#60 should preserve a small matching descriptor for every finding alongside
the human-facing fields. This descriptor is matching evidence, not stable-ID
serialization:

| Facet | Meaning | Normalization |
|---|---|---|
| `location_intent` | line/symbol/file/cross-file/repository scope | closed enum; different intent is disqualifying |
| `path` | repository-relative path, when applicable | `/` separators; repository case rules; no absolute path |
| `symbol` | best available enclosing qualified symbol | lexical qualified name; absent is explicit, not guessed |
| `construct` | statement/declaration/config-key/section kind | conservative language-neutral label; optional parser refinement |
| `anchor_tokens` | smallest source/config fragment that demonstrates the defect | tokenize, remove comments and formatting, preserve literals/operators/order |
| `context_tokens` | bounded tokens around the anchor within its symbol/section | same normalization; diagnostic/candidate evidence |
| `defect_kind` | narrow defect class/invariant violated | controlled shared vocabulary where one exists; otherwise conservative normalized phrase |
| `behavioral_claim` | concise cause → faulty behavior, excluding impact/fix/severity | normalize case/whitespace only; do not erase identifiers, negation, numbers, or operators |

The implementation must derive the descriptor from the actual evidence at the
reviewed revision, not title prose alone. Missing optional facets reduce recall;
they never become wildcards that increase confidence.

### Two independent proof axes

**Defect continuity** is established by one of:

- exact `defect_kind + behavioral_claim` after conservative normalization;
- the same defect-bearing `anchor_tokens` plus compatible `defect_kind`; or
- for a partial fix, explicit current evidence that the prior cause → faulty
  behavior remains, with the same `defect_kind` and no contradictory claim.

Textual resemblance of title, impact, fix, or explanation is not proof.

**Site continuity** is established by one of:

- same normalized path + same qualified symbol + compatible location intent;
- a deterministic Git path rename/copy mapping + same symbol or exact anchor;
- same path + exact distinctive anchor within the same symbol/section;
- exact distinctive anchor moved within the compared changed set, when it has
  exactly one occurrence and surrounding context is compatible; or
- a recorded explicit refactor mapping supplied by the compared delta (for
  example, old symbol to extracted helper), again with exactly one destination.

Line overlap alone, same path alone, same symbol name in different paths, or
fuzzy context alone is not proof. An anchor is **distinctive** only when its
normalized token sequence occurs once among eligible current sites and once
among the relevant prior sites; common fragments such as `return null` are not
distinctive.

### Disqualifiers

Any of these forbids automatic reuse even if other signals are similar:

- different repository identity;
- incompatible location intent;
- contradictory defect kind or behavioral claim;
- evidence that the old defect was removed before the current defect appeared,
  unless later lifecycle evidence explicitly establishes recurrence;
- two or more equally supported prior or current sites;
- a split or collapse (one-to-many or many-to-one);
- only generated-prose similarity, only line overlap, or only category equality;
- stale/untrusted source evidence that cannot be checked at the two reviewed
  states.

## 3. Strategy comparison

The ratings below are against this repository's constraints, not general
claims that one technique is universally superior.

| Strategy | Precision | Recall/refactors | Determinism / explanation | Portability / dependencies | Decision |
|---|---|---|---|---|---|
| Structural only | High when symbol + anchor exist; lower for repeated constructs | Good for shifts/reformatting; weak for rename, extraction, split/merge | High; exact facts are inspectable | Good with lexical fallback; full AST coverage is costly | Keep as authority, but insufficient alone |
| Fuzzy/textual only | Low: similar prose/patterns collide | Handles wording and small edits; weak on root-cause distinctions | Algorithm deterministic, threshold meaning is corpus-sensitive | Stdlib possible; language independent | Reject as authority |
| Semantic/LLM only | Unbounded false-merge risk | Best potential recall on rewrites/refactors | Model/version/prompt dependent and difficult to reproduce | Network/model/cost/latency may be unavailable | Reject as authority |
| Staged hybrid | Highest: independent proofs and uniqueness gate | Better than structural alone; deliberately misses hard rewrites | Deterministic decision trace; explicit ambiguity | Stdlib/Git baseline, optional parser/model enhancements | **Recommend** |

### Structural matching

Paths, symbols, construct kinds, anchors, and bounded context are stable under
line shifts and formatting. Git rename information is useful candidate evidence,
but it is a file-similarity heuristic, not proof that an individual defect
moved. Git exposes configurable rename/copy detection thresholds, reinforcing
that a file move result is one signal rather than semantic identity.

A parser can improve symbol and construct extraction. Incremental concrete
syntax tree tools such as Tree-sitter can track changed ranges, but require a
runtime plus grammars and application-specific mapping. A parser is therefore
an optional evidence provider, not a shipped precondition. The portable
fallback uses diff mapping, lightweight lexical symbol/section discovery when
reliable, and normalized tokens.

Structural-only matching loses recall when a function is renamed and rewritten,
code moves across files without rename evidence, or helper extraction changes
both the anchor and symbol. It also cannot distinguish a newly introduced
defect at an unchanged site unless paired with defect evidence.

### Fuzzy/textual matching

Stable textual inputs are source tokens, narrow evidence anchors, and bounded
source context. Generated title, explanation, impact, details, and fix are
unstable and can use the same wording for independent problems; they are useful
for retrieval and diagnostics only.

Edit distance and sequence similarity overweight order and formatting unless
tokens are normalized. Token-set/Jaccard similarity tolerates movement but
loses order, negation, and multiplicity. SequenceMatcher-style algorithms are
deterministic for fixed inputs, but their ratios are not calibrated
probabilities; Python's documentation also notes order dependence and a
popular-element heuristic. None provides a defensible universal threshold for
"same defect."

Accordingly, fuzzy values may rank candidates **inside a bounded structural
set** and expose a reason such as "anchor token overlap." They cannot turn a
pair into `MATCH`, cannot override a disqualifier, and need no production
threshold for #60. #61 may later calibrate retrieval cutoffs against fixtures;
changing retrieval must not weaken the authoritative gates.

### Semantic matching

An LLM can recognize a high-level defect through rename or substantial rewrite,
but the same flexibility makes it unsafe as an identity authority. Results can
vary with model, version, prompt, context selection, and service availability;
an embedding nearest neighbor supplies proximity, not an explanation that root
cause and program site are identical. It also introduces runtime, network,
latency, privacy, and cost differences that violate the common offline baseline.

Semantic reasoning is optional advisory evidence only:

- run it, if available, after deterministic matching leaves `AMBIGUOUS`;
- show the prior candidates and structural conflicts it is reasoning over;
- let it recommend human inspection or explain why candidates differ;
- never let it change `AMBIGUOUS`/`NO MATCH` to automatic `MATCH` by itself.

## 4. Scenario benchmark

This is a deterministic design benchmark, not a statistical corpus. “Auto”
means the evidence model can prove both axes uniquely. “Ambiguous” means the
relationship may be preserved for inspection, but #60 must not reuse identity.

| # | Scenario | Structural | Fuzzy | Semantic | Recommended hybrid |
|---:|---|---|---|---|---|
| 1 | unrelated lines inserted above | match | likely match | match | **Auto**: same symbol + anchor/claim; ignore lines |
| 2 | finding wording changes | weak if prose-only | likely match | match | **Auto** when source anchor/site and defect kind persist; otherwise ambiguous |
| 3 | same-function formatting | match after token normalization | match | match | **Auto**: normalized anchor + site |
| 4 | nearby code changes, unsafe behavior remains | match | likely match | match | **Auto**: defect anchor/claim + site; context drift is weak |
| 5 | function renamed, defect remains | anchor can match | likely match | match | **Auto** only with unique anchor/refactor mapping + defect continuity |
| 6 | code moves nearby during refactor | anchor can match | likely match | match | **Auto** only for unique mapped/exact anchor + defect continuity |
| 7 | partial fix leaves original defect | anchor may drift | likely match | match | **Auto** only when same site and explicit cause→behavior remains; else ambiguous |
| 8 | identical null dereferences in different functions | separates by symbol | false-merge risk | false-merge risk | **No**: different logical site |
| 9 | same category in two files | separates by path/site | false-merge risk | false-merge risk | **No**: different site |
| 10 | similar descriptions, different causes | needs defect facet | false-merge risk | false-merge risk | **No**: contradictory root cause/claim |
| 11 | original fixed, similar issue elsewhere | separates with history/site | false-merge risk | may merge | **No**: old evidence removed + new site |
| 12 | new defect later on same line | location false positive | may merge | may merge | **No**: defect continuity absent/contradicted |
| 13 | one finding splits into two defects | one-to-many conflict | may choose one | may choose one | **Ambiguous**: no automatic inheritance |
| 14 | two findings collapse into one path | many-to-one conflict | may choose nearest | may choose one | **Ambiguous**: no automatic inheritance |
| 15 | moved and substantially rewritten | low recall | possible | strongest recall | **Ambiguous** unless explicit unique refactor + defect proof exists |
| 16 | helper extraction changes symbol/location | mapping-dependent | possible | likely | **Ambiguous** by default; auto only with explicit unique mapping + proof |
| 17 | prior evidence gone, same high-level concern claimed | no support | prose may match | may match | **No**: current evidence cannot prove continuation |
| 18 | multiple plausible priors for one current | conflict | ranks but cannot decide | may guess | **Ambiguous**: preserve candidate set |

The matrix produces seven conditional automatic matches (1–7), six definite
non-matches (8–12 and 17), and five explicit ambiguities (13–16 and 18; case
16 may promote only with stronger evidence). It deliberately does not claim
perfect recall for wording-only or heavily rewritten cases. That is the
correct trade under the requirements' false-merge asymmetry.

## 5. Algorithm for #60

### Step 0 — validate comparison scope

Require the same repository identity and a trustworthy prior/current reviewed
state. Load only the prior finding set referenced by the authoritative
predecessor state. Repository mismatch or unusable prior state yields no
eligible candidates.

### Step 1 — build descriptors

For every prior and current finding, build the evidence descriptor in §2 from
the corresponding revision. Preserve raw values for diagnostics and normalized
values for comparison. Do not use severity, display ordinal, discovery order,
HEAD SHA, PR number, source-state annotation, or wall clock as match evidence.

### Step 2 — map changed structure

Build deterministic mappings available from the compared states:

1. exact normalized paths;
2. Git rename/copy results as candidate mappings, never sole proof;
3. qualified symbols or conservative lexical sections;
4. exact normalized anchor occurrences and their containing sections;
5. explicit refactor mappings, if a caller can prove them from the delta.

AST/Tree-sitter evidence may refine steps 3–4 but cannot be required for a
match that the portable representation can establish.

### Step 3 — generate a bounded candidate set

A prior finding is eligible only if location intent is compatible and at least
one site-continuity signal exists:

- same path and same symbol/section;
- mapped path and same symbol or exact anchor;
- same path and a unique exact anchor; or
- a unique exact anchor/refactor mapping across the changed set.

Same category, same line, or similar prose alone never creates a candidate.
Fuzzy anchor/context/title comparison may rank already eligible candidates for
diagnostics, but may not widen eligibility beyond the repository's changed set
and structurally plausible sites.

### Step 4 — classify each candidate pair

Evaluate disqualifiers first. For each remaining pair, record a trace:

```text
site proof:   <which exact/mapped structural evidence>
defect proof: <which exact anchor/claim or partial-fix evidence>
weak signals:<optional fuzzy/semantic observations>
conflicts:    <missing, contradictory, or multiplicity evidence>
```

A pair becomes a **high-confidence edge** only when it has at least one valid
site proof and one valid defect proof, with no disqualifier. Weak signals do
not count toward either proof.

This is a conjunctive decision rule, not a weighted sum. It needs no magic
threshold and is explainable as two inspectable facts.

### Step 5 — resolve globally, not greedily

Construct the bipartite graph of prior findings and current findings using
high-confidence edges plus separately retained plausible candidate edges.

- exactly one high-confidence edge incident to both endpoints, and no competing
  plausible edge with unresolved conflict → `MATCH`;
- no eligible or supported edge → `NO MATCH`;
- multiple high-confidence/plausible edges for either endpoint, or a
  one-to-many/many-to-one topology → `AMBIGUOUS` for the whole component;
- conflicting evidence → `AMBIGUOUS` when a relationship remains plausible,
  otherwise `NO MATCH`.

Sort paths, descriptors, and candidate IDs lexically for deterministic output,
but never use sort order to break a tie. Do not run a greedy "best score wins"
assignment.

### Step 6 — identity handoff boundary

For `MATCH`, #60 propagates the established prior stable identity. For
`NO MATCH` and `AMBIGUOUS`, #60 creates a fresh identity for the current
finding. This document does not define the ID's hash, serialization, storage,
or display form.

If supported later, store ambiguity as non-authoritative metadata containing
candidate prior identities and the decision trace. It must never suppress,
resolve, merge, or transfer lifecycle state.

## 6. Why the alternatives were rejected

- **Path + line/range:** fails ordinary line movement and reuses identity for a
  new defect at an old address.
- **Hash of context/source:** exact hashes fail partial edits; loose hashes
  collide on repeated patterns and do not represent root cause.
- **Finding prose fingerprint:** generated wording drifts and identical prose is
  common across independent defects.
- **Single fuzzy threshold:** similarity is not a probability of logical
  identity, varies by tokenization/language/corpus, and hides which requirement
  justified a merge.
- **Weighted hybrid score:** lets several weak correlated signals outvote a
  missing mandatory proof and encourages threshold tuning that raises silent
  false merges.
- **Parser/AST mandatory:** improves structure but creates grammar/runtime
  dependencies, has uneven language coverage, and still cannot establish
  defect semantics alone.
- **LLM/embedding authority:** improves difficult-case recall at the cost of
  reproducibility, portability, explainability, and bounded false-positive
  behavior.
- **Greedy nearest candidate:** silently chooses in split, collapse, repeated
  pattern, and multiple-prior cases; global uniqueness must be checked first.

## 7. Validation and follow-up implications

### #60 — stable finding IDs

Implement the descriptor, deterministic normalizers, two-proof matcher,
decision trace, and global uniqueness gate. Keep identity serialization and
persistence separate from matching. Reconcile same-HEAD duplicate suppression
so an unchanged state cannot split a cross-review identity, while removing
severity and volatile line/HEAD inputs from the cross-review relationship.

### #61 — regression tests

Turn all 18 scenarios into deterministic fixtures. Each fixture should vary
one signal at a time, assert `MATCH`/`NO MATCH`/`AMBIGUOUS`, assert the reason
trace, and permute finding order. Add adversarial repeated-pattern, negation,
literal/operator-change, duplicated-anchor, path-case, rename, cross-Skill,
and one-to-many/many-to-one cases. If fuzzy retrieval cutoffs are introduced,
calibrate them on a larger labeled corpus and test that changing them cannot
bypass the two authoritative proof gates.

### #62 — lifecycle

Define how lifecycle consumes only definite matches. `AMBIGUOUS` must not imply
resolved, reopened, superseded, or no-longer-applicable. The candidate set is
advisory evidence only.

### #64 — review delta semantics

Use matching after the authoritative reviewed-SHA boundary is selected. Delta
classification must distinguish a definite moved/unchanged match from a fresh
finding and from ambiguity; it must not infer resolution merely because no
automatic match was found.

## 8. Known limitations and non-goals

The conservative gates will false-split findings after substantial rewrites,
cross-file moves without a unique anchor/mapping, unavailable prior source,
or generated findings with insufficient structural evidence. Parser-poor
languages and cross-cutting findings will have lower automatic-match recall.
Those are visible limitations, preferable to silently merging distinct defects.

This research does not implement IDs (#60), the regression suite (#61),
lifecycle states or transitions (#62), delta semantics (#64), state loading or
persistence (#65), severity/decision changes, or network/runtime dependencies.

## 9. Sources

- Repository contracts:
  [`finding-identity-requirements.md`](finding-identity-requirements.md),
  [`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md),
  [`../shared/templates/finding.md`](../shared/templates/finding.md),
  [`../shared/policies/review-evidence.md`](../shared/policies/review-evidence.md),
  and
  [`../skills/github-pr-review/policies/pr-scope.md`](../skills/github-pr-review/policies/pr-scope.md).
- [Git diff documentation](https://git-scm.com/docs/git-diff) — rename/copy
  detection, similarity thresholds, and diff mapping behavior.
- [Python `difflib` documentation](https://docs.python.org/3/library/difflib.html)
  — SequenceMatcher behavior, ratio caveats, and popular-element heuristic.
- [Tree-sitter advanced parsing documentation](https://tree-sitter.github.io/tree-sitter/using-parsers/3-advanced-parsing.html)
  — edit-aware syntax trees, changed ranges, included ranges, and the
  application logic required around them.
