# Root-Cause Investigation — the Missed Maven BOM Regression

Repository-development design record for **[#723](https://github.com/amirbena/code-review-skill/issues/723)**,
"Root-cause confirmation". Not packaged; explanatory. The Epic's
hypothesis ([#722](https://github.com/amirbena/code-review-skill/issues/722))
was that the existing dependency deepening reasons only over manifest and
lockfile diff text, does not resolve dependencies, and that Maven has no
lockfile, so a BOM bump carries no in-diff transitive evidence. This record
tests that hypothesis rather than assuming it.

## 1. Method and its limits

**What was done: a static policy-trace replay.** A faithful synthetic
equivalent of the incident (the diff in §2) was traced step by step through
the packaged review pipeline's *written* contracts, asking at each step what
the pipeline is required to see, decide, and emit.

**What was not done: a live-model replay.** Running the Skills over the
synthetic repository was not performed because: (a) `local-code-review` is
never invoked automatically and needs fresh explicit user approval, and an
implementing agent never reviews its own change; (b) a model run is
non-deterministic, so a single run proves little either way; (c) the
original review transcript and repository are not available to this record.
A live replay is the right instrument for the questions §4 leaves open, and
§5 specifies it.

## 2. The synthetic equivalent

The diff the reviewer is given is one line in `pom.xml`: an imported BOM,
`jsk-bom`, from `2.16.29` to `2.16.39`. There is no lockfile (Maven has
none), no changed Java source, and no changed `<dependency>` entry. The
resolved-tree consequence — non-FIPS BouncyCastle artifacts
(`bcprov-jdk18on`, `bcpkix-jdk18on`, `bcutil-jdk18on`) arriving through
`spring-cloud-starter-bootstrap 3.1.8 → spring-cloud-starter 3.1.8 → spring-security-rsa 1.0.12` (the Epic abbreviates the middle hop)
alongside the repository's existing `bc-fips 1.0.2.4` / `bcpkix-fips 1.0.7`
— exists only in the resolved graph. Public-POM resolution shows that every `spring-cloud-starter-bootstrap` from 3.0.0 on pulls non-FIPS BouncyCastle, so the Epic's "brought in" must be checked against the real Base before it is treated as fact ([`fidelity-study.md`](fidelity-study.md) §4). Details of the graphs are in
[`dependency-graph-regression-model.md`](dependency-graph-regression-model.md)
§3.

## 3. The trace

| Step | Contract consulted | What the pipeline does for this diff |
| --- | --- | --- |
| 1. Scope | `review-scope.md`, "What is examined" | Examines the one-line manifest change. Resolved dependencies are outside the examined material. |
| 2. Dimension | `review-scope.md`, "Semantic change-implication reasoning" | `pom.xml` changing implicates the Infrastructure / deployment dimension, whose depth owner is the dependency deepening. The signal is recognized: `pom.xml` is in its named inputs. |
| 3. Concern areas | `review-scope.md`, "Dependency / supply-chain deepening review" | Each area needs its own diff evidence. Major-version: `2.16.29 → 2.16.39` is a patch-level change — an explicit "do not flag". Runtime/platform: no. Dependency expansion: defined over a **lockfile diff**; none exists. Provenance: no. Build/runtime: no. No concern area is reachable. |
| 4. The pass's own worked example | `dependency-supply-chain-model.md`, §3 | A patch-level bump with an unchanged lockfile "implicates none of the five concern areas: this pass performs no deepening and raises no finding." For this diff shape that is the prescribed outcome, not a lapse. |
| 5. Resolution | The same section, and `runtime-validation.md`, `repository-checkout.md` | The pass "does not resolve or install dependencies"; execution and network are denied. The transitive graph cannot be obtained inside the pipeline. |
| 6. Expansion | `repository-expansion.md` | The fixed trigger catalog (call-site, interface/contract, migration/schema, config-consumer) does not fire on a BOM version. "Relevant dependency" is explicitly out of scope. |
| 7. Evidence bar | `evidence.md` | A finding requires concrete repository evidence. None exists for a conflict that is visible only after resolution; a model's recollection of what a BOM pulls in is speculation the bar excludes. |
| 8. Severity | `severity.md` | Never reached: no candidate finding survives step 7. |

## 4. Classification

| Hypothesized cause | Verdict | Basis |
| --- | --- | --- |
| **Missing graph evidence** | **Confirmed as sufficient cause.** | Steps 3–5: the pipeline has no admitted way to obtain the resolved graph and the diff carries no in-diff transitive evidence. This is determinable by the contract alone. |
| **Activation** (the deepening never engaged) | **Not the cause.** | Step 2: the signal is recognized and the pass is in scope. It is engaged but inert, because no concern area can be reached from the diff. |
| **Reasoning** (evidence present, not concluded on) | **Not determinable here.** | With no graph evidence there was nothing present to conclude on. Whether a live model additionally *had* the relevant knowledge and declined to act on it cannot be told from the contract; it needs the original transcript or a live replay. |
| **Severity suppression** | **Not determinable here; unlikely to be the cause.** | Step 8: severity is reached only by a surviving candidate. A candidate dropped *before* severity (at the evidence bar) is not severity suppression. Whether the original run formed and then down-ranked a candidate is not observable from the contract. |

**Conclusion.** The Epic's hypothesis is **confirmed in part**: missing
graph evidence is established as a sufficient cause by static trace, and the
current pass's own worked example prescribes silence for exactly this diff
shape. The activation hypothesis is rejected. Reasoning and severity
suppression are recorded as **not determinable** from the contract. This is
a real limit, not a hedge: the contract-level finding is firm, and the
residual question is empirical.

This also shows why the fix cannot be "reason harder over the diff": no
amount of reasoning over a one-line BOM bump produces evidence that is not
in it.

## 5. The live replay to run (owned by #725, before #724 lands)

So that the open rows are settled rather than left as folklore:

1. Build the synthetic repository from §2 with a real Maven project whose
   resolved Head tree reproduces the BouncyCastle shape (the harness, not
   this record, resolves it once, offline, and checks it in as fixture data).
2. Run the **current**, unmodified pipeline in both adapters, at least the
   number of trials #725 pre-registers, recording for each run: whether the
   diff-text deepening engaged, any candidate formed, any candidate dropped
   and at which step, and any question in the Reasoning check.
3. Classify each run against the table in §4. The baseline is the "before"
   number the #725 gate is measured against.

Until that is done, no claim in this record or the Epic should state that
the model "reasoned incorrectly" or "suppressed" the issue.
