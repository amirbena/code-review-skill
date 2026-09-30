#!/usr/bin/env python3
"""Test-only reference fixtures for the human reasoning checkpoint corpus
(Issue #567, Epic #564; depends on #565 and on the delivered #566:
shared/policies/reasoning-checkpoint.md, the `Reasoning check` section of
shared/templates/review-summary.md, and both delivery templates).

The checkpoint is not representable in `benchmark-case/v2`
(runtime_platform/benchmark/fixture-format.md): that schema's `expected`
block is a patch plus expected review findings, and the checkpoint is by
contract *not* a finding and carries no severity, ID, or Decision effect.
Per the #565 design record (section 11) this module therefore follows the
existing test-only reference-fixture pattern of
`verdict_consistency_fixtures.py` / `reviewer_brief_fixtures.py`: declarative,
metadata-bearing cases over a rendered review, documented in
docs/benchmark/corpus/reasoning-checkpoint/README.md. No second fixture
framework, no new benchmark mechanism.

Each `ReasoningCheckpointCase` carries the *activation evidence* the review
already holds (change kind, signals, finalized findings, coverage), the
expected activation outcome, and -- when active -- the anchored questions the
review would emit. The module provides three small, deterministic,
non-LLM reference pieces the tests exercise:

- `evaluate_activation` -- mirrors the policy's "Activation" section;
- `select_questions` -- mirrors "Shape and bounds" (1-4, investigation first);
- `render_review` -- a surface-shaped renderer mirroring the section's
  placement (after Decision, before metadata; body only, never inline), with
  the checkpoint switchable off so invariance is asserted against the same
  input rendered without it.

Decision derivation reuses `tests/reference/review/decision_semantics.py` --
the single mechanical source of truth -- so the invariance cases compare the
checkpoint's effect against the real derivation, never a second one.

Evaluation style (runtime_platform/benchmark/README.md convention): every
check is a deterministic structural assertion, never an LLM/rubric score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from tests.reference.review import decision_semantics as ds

# ---------------------------------------------------------------------------
# Closed vocabularies (mirroring shared/policies/reasoning-checkpoint.md)
# ---------------------------------------------------------------------------

SECTION_HEADING = "### Reasoning check"
SECTION_LEAD_IN = "Questions for you — not findings; they do not change the decision."
MAX_QUESTIONS = 4
MIN_QUESTIONS = 1

FACET_INVESTIGATION = "investigation"
FACET_DESIGN = "design"

# Anchor kinds: the four rows of the policy's "Derivation: the anchor rule".
ANCHOR_CHAIN_LINK = "unverified-chain-link"
ANCHOR_PLACEMENT_RING = "placement-ring"
ANCHOR_INSPECTED_PEER = "inspected-caller-callee-analogue"
ANCHOR_CONTRADICTION = "evidence-contradiction"
VALID_ANCHORS = frozenset(
    {ANCHOR_CHAIN_LINK, ANCHOR_PLACEMENT_RING, ANCHOR_INSPECTED_PEER, ANCHOR_CONTRADICTION}
)

# Provenance labels: the three rows of "Access and provenance boundary".
PROV_INSPECTED = "reviewer-inspected"
PROV_REPORTED = "engineer-reported"
PROV_UNAVAILABLE = "possible but unavailable"
VALID_PROVENANCE = frozenset({PROV_INSPECTED, PROV_REPORTED, PROV_UNAVAILABLE})

# Investigation-facet signals (strongest first) and non-signals.
SIG_CONTEXT_BUG_OR_INCIDENT = "context-bug-description-or-incident-followup"
SIG_TEXT_OBSERVED_MISBEHAVIOR = "text-states-observed-misbehavior"
SIG_STRONG_CONTENT = "strong-content-signal-regression-test-names-symptom"
SIG_NAMEABLE_UNVERIFIABLE_LINK = "reviewer-can-name-unverifiable-runtime-link"
# Never activate on their own (policy: "is not a signal" / "supporting signal").
NON_SIGNALS = frozenset(
    {"fix-commit-prefix", "bug-shaped-branch-name", "small-guard-in-helper", "tracker-type-bug"}
)

# Design-facet signals.
SIG_PLACEMENT_LIFECYCLE_RING = "placement-trigger-reached-owning-abstraction-or-lifecycle-ring"
SIG_ANALOGUE_DEVIATION = "analogue-deviation-with-concrete-consequence"
SIG_PLACEMENT_INSUFFICIENT_BOUNDARY_MOVE = "placement-insufficient-evidence-on-boundary-move"
SIG_PLACEMENT_DIRECT_CONFIRMED = "placement-stopped-at-direct-caller-confirmed-correct"

# Always-inert change kinds (policy: "Always inert").
INERT_CHANGE_KINDS = frozenset(
    {
        "formatting",
        "rename",
        "dependency-bump-no-behavior",
        "test-only",
        "doc-only",
        "config-value-no-lifecycle-effect",
        "mechanical-refactor-unchanged-behavior",
    }
)
BEHAVIORAL_CHANGE_KINDS = frozenset({"bug-fix", "lifecycle-change", "feature", "ordinary"})

# Categories and required coverage tags (one tag per #567 scope bullet).
CATEGORY_ACTIVATION = "activation"
CATEGORY_INERT = "inert"
CATEGORY_INSUFFICIENT_EVIDENCE = "insufficient_evidence"
CATEGORY_RUNTIME_BOUNDARY = "runtime_boundary"
CATEGORY_FINDINGS_INTERACTION = "findings_interaction"
CATEGORY_NOISE_BOUND = "noise_bound"
VALID_CATEGORIES = frozenset(
    {
        CATEGORY_ACTIVATION,
        CATEGORY_INERT,
        CATEGORY_INSUFFICIENT_EVIDENCE,
        CATEGORY_RUNTIME_BOUNDARY,
        CATEGORY_FINDINGS_INTERACTION,
        CATEGORY_NOISE_BOUND,
    }
)

REQUIRED_COVERAGE_TAGS = frozenset(
    {
        "bug-fix-investigation-activates",
        "architecture-lifecycle-activates",
        "trivial-change-absent",
        "insufficient-evidence-no-invention",
        "runtime-boundary-asks-not-assumes",
        "runtime-provenance-distinct",
        "no-invented-runtime-contents",
        "findings-present-questions-not-findings",
        "clean-review-checkpoint-appears",
        "p2-only-non-blocking-checkpoint",
        "decision-severity-invariance",
        "rendering-local-and-github",
        "question-count-ceiling",
        "ordinary-reviews-no-checkpoint",
        "inert-under-incomplete-or-unresolved",
    }
)

SURFACES = (
    "local",
    "github-passive",
    "github-active",
    "github-withheld",
    "github-self-review",
    "github-fallback",
)

# Readiness phrases forbidden while Condition R holds, and the permitted ones.
FORBIDDEN_READINESS_PHRASES = (
    "ready to push",
    "fully verified",
    "the bug is fixed",
    "the bug is resolved",
    "safe to deploy",
    "verified fixed",
)
PERMITTED_READINESS_PHRASES = (
    "consistent with the evidence reviewed",
    "no blocking issue found in the change",
)
SCOPED_OPENING_ASSESSMENT = (
    "No blocking issue found in the change as reviewed; whether it resolves the "
    "reported problem depends on evidence not established here — see Reasoning check."
)

# Phrases that would claim runtime access or invent runtime contents.
ACCESS_CLAIM_PATTERNS = (
    r"\bi (?:checked|queried|read|inspected|pulled) the (?:logs?|traces?|metrics|dashboards?)\b",
    r"\bthe (?:logs?|traces?|metrics) (?:show|confirm|indicate|prove)\b",
    r"\b(?:logs?|traces?) (?:contain|contained|reveal|revealed)\b",
    r"\bverified in production\b",
)
# Questions true of any change: prevented by construction.
GENERIC_QUESTION_PATTERNS = (
    r"^did you test",
    r"^have you tested",
    r"^are you sure",
    r"^is this (?:correct|ok|okay)\b",
    r"^does this (?:work|look good)\b",
)
PLACEHOLDER_PHRASES = (
    "insufficient context",
    "no questions",
    "no further questions",
    "n/a",
)

_SEVERITY_LABEL = re.compile(r"\bP[0-2]\b")
_FINDING_ID = re.compile(r"\b(?:F|finding[- ]?)\d+\b", re.IGNORECASE)
_DECISION_TOKEN = re.compile(r"REVIEW CLEAN|CHANGES REQUIRED|REVIEW INCOMPLETE")


class ReasoningCheckpointFixtureError(ValueError):
    """A reasoning-checkpoint benchmark fixture is malformed."""


# ---------------------------------------------------------------------------
# Case shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Question:
    """One anchored question a reviewing run would emit."""

    text: str
    facet: str
    anchor_kind: str
    anchor_ref: str
    # Set only when the question mentions an evidence item.
    provenance: Optional[str] = None
    # Whether the question merely restates a reported finding (must be dropped).
    restates_finding: bool = False


@dataclass(frozen=True)
class EvidenceItem:
    """A runtime/evidence item a question may mention, with its true status."""

    name: str
    status: str  # one of VALID_PROVENANCE


@dataclass(frozen=True)
class ReasoningCheckpointCase:
    case_id: str
    category: str
    covers: frozenset[str]
    description: str
    change_kind: str
    findings: tuple[ds.Finding, ...] = ()
    signals: frozenset[str] = frozenset()
    coverage_incomplete: bool = False
    jira_unresolved: bool = False
    expected_active: bool = False
    # Condition R: investigation facet active and the unverified link is
    # runtime (class 4) / unknown (class 5) with no repository backing.
    runtime_dependent: bool = False
    # Candidate questions in emission order before bounding (may exceed 4).
    candidates: tuple[Question, ...] = ()
    evidence_items: tuple[EvidenceItem, ...] = ()
    # What the review reads as "What changed" (prose, never a readiness claim).
    what_changed: str = "Updates the reviewed change."
    notes: str = ""

    @property
    def decision(self) -> ds.Decision:
        return ds.derive_decision(self.findings)


# ---------------------------------------------------------------------------
# Reference model 1: activation (mirrors the policy's "Activation")
# ---------------------------------------------------------------------------


def investigation_facet_active(case: ReasoningCheckpointCase) -> bool:
    if case.change_kind != "bug-fix":
        return False
    signals = case.signals - NON_SIGNALS
    if SIG_CONTEXT_BUG_OR_INCIDENT in signals or SIG_TEXT_OBSERVED_MISBEHAVIOR in signals:
        return True
    # A strong content signal activates the facet only when the reviewer can
    # also name the runtime-dependent link it cannot verify.
    return SIG_STRONG_CONTENT in signals and SIG_NAMEABLE_UNVERIFIABLE_LINK in signals


def design_facet_active(case: ReasoningCheckpointCase) -> bool:
    if case.change_kind not in BEHAVIORAL_CHANGE_KINDS:
        return False
    signals = case.signals
    return bool(
        SIG_PLACEMENT_LIFECYCLE_RING in signals
        or SIG_ANALOGUE_DEVIATION in signals
        or SIG_PLACEMENT_INSUFFICIENT_BOUNDARY_MOVE in signals
    )


def evaluate_activation(case: ReasoningCheckpointCase) -> bool:
    """Whether the checkpoint activates. Evaluated once, after findings are
    final, from evidence the review already holds. Fails closed: no
    anchorable question means no section."""
    if case.change_kind in INERT_CHANGE_KINDS:
        return False
    if case.coverage_incomplete or case.jira_unresolved:
        return False
    if not (investigation_facet_active(case) or design_facet_active(case)):
        return False
    return bool(select_questions(case.candidates))


# ---------------------------------------------------------------------------
# Reference model 2: shape and bounds (mirrors "Shape and bounds")
# ---------------------------------------------------------------------------


def select_questions(candidates: tuple[Question, ...]) -> tuple[Question, ...]:
    """Drop restated findings and unanchored questions, put investigation
    questions first (stable within a facet), cap at MAX_QUESTIONS."""
    anchored = [
        q
        for q in candidates
        if not q.restates_finding and q.anchor_kind in VALID_ANCHORS and q.anchor_ref.strip()
    ]
    anchored.sort(key=lambda q: 0 if q.facet == FACET_INVESTIGATION else 1)
    return tuple(anchored[:MAX_QUESTIONS])


def emitted_questions(case: ReasoningCheckpointCase) -> tuple[Question, ...]:
    return select_questions(case.candidates) if evaluate_activation(case) else ()


# ---------------------------------------------------------------------------
# Reference model 3: rendering (mirrors template placement)
# ---------------------------------------------------------------------------

_DISCLOSURE = "_Self-review: formal approval is unavailable; this is an informational comment._"
_METADATA = "### Review Metadata\n\n- mode: {mode}"


@dataclass(frozen=True)
class RenderedReview:
    surface: str
    human_review_output: bool
    body: str
    inline_comments: tuple[str, ...]


def _heading(surface: str) -> str:
    return "## Code Review" if surface == "local" else "## Review Summary"


def _opening_assessment(case: ReasoningCheckpointCase, checkpoint: bool) -> str:
    if checkpoint and case.runtime_dependent and evaluate_activation(case):
        return SCOPED_OPENING_ASSESSMENT
    if case.decision is ds.Decision.CLEAN:
        return "No blocking issue found in the change as reviewed."
    return "Blocking issues were found; see Findings."


def _findings_block(case: ReasoningCheckpointCase, surface: str) -> tuple[str, tuple[str, ...]]:
    if not case.findings:
        return "", ()
    lines = ["### Findings"]
    inline: list[str] = []
    for finding in case.findings:
        title = f"**{finding.severity.value} — {finding.id}**"
        lines.append(title)
        if surface in ("github-active", "github-withheld", "github-passive"):
            inline.append(f"{title} inline comment")
            lines.append(f"See inline comment for {finding.id}.")
    return "\n".join(lines), tuple(inline)


def render_review(
    case: ReasoningCheckpointCase,
    surface: str,
    *,
    human_review_output: bool = False,
    checkpoint: bool = True,
) -> RenderedReview:
    """Render one review body. `checkpoint=False` renders the same input with
    the capability suppressed -- the baseline every invariance case compares
    against."""
    if surface not in SURFACES:
        raise ReasoningCheckpointFixtureError(f"unknown surface {surface!r}")
    decision = case.decision
    parts = [
        _heading(surface),
        f"**Result: {ds.render_result_label(decision)}**",
        _opening_assessment(case, checkpoint),
    ]
    if human_review_output:
        parts.append(f"{case.what_changed}")
    else:
        parts.append(f"### What changed\n{case.what_changed}")
    findings_block, inline = _findings_block(case, surface)
    if findings_block:
        parts.append(findings_block)
    parts.append(f"### Decision\n**{decision.value}**")
    if surface == "github-self-review":
        parts.append(_DISCLOSURE)
    questions = emitted_questions(case) if checkpoint else ()
    if questions:
        numbered = "\n".join(f"{i}. {q.text}" for i, q in enumerate(questions, 1))
        parts.append(f"{SECTION_HEADING}\n{SECTION_LEAD_IN}\n{numbered}")
    parts.append(_METADATA.format(mode=surface))
    return RenderedReview(
        surface=surface,
        human_review_output=human_review_output,
        body="\n\n".join(p for p in parts if p),
        inline_comments=inline,
    )


def render_structured_result(case: ReasoningCheckpointCase) -> dict:
    """The closed-schema machine projection: findings, coverage, Decision.
    It has no reasoning-check key by construction and does not depend on the
    checkpoint."""
    return {
        "findings": [{"id": f.id, "severity": f.severity.value} for f in case.findings],
        "coverage": "incomplete" if case.coverage_incomplete else "complete",
        "decision": case.decision.value,
        "summary": case.what_changed,
    }


def extract_section(body: str) -> Optional[tuple[str, ...]]:
    """The numbered questions of the `Reasoning check` section, or None when
    the section is absent."""
    if SECTION_HEADING not in body:
        return None
    tail = body.split(SECTION_HEADING, 1)[1]
    tail = tail.split("\n### ", 1)[0]
    return tuple(
        re.sub(r"^\d+\.\s*", "", line).strip()
        for line in tail.splitlines()
        if re.match(r"^\d+\.\s", line)
    )


def strip_section(body: str) -> str:
    """The body with the whole `Reasoning check` block removed."""
    return re.sub(
        rf"\n\n{re.escape(SECTION_HEADING)}\n.*?(?=\n\n### |\Z)", "", body, flags=re.DOTALL
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def question_violations(question: Question, case: ReasoningCheckpointCase) -> list[str]:
    """Structural contract violations of one emitted question; empty when
    sound. Each violation names the policy rule it breaks."""
    problems: list[str] = []
    text = question.text.strip()
    lowered = text.lower()
    if not text.endswith("?") or text.count("?") != 1:
        problems.append("not one sentence ending in '?'")
    if _SEVERITY_LABEL.search(text):
        problems.append("contains a P0/P1/P2 label")
    if _DECISION_TOKEN.search(text):
        problems.append("contains a Decision/Result token")
    if _FINDING_ID.search(text):
        problems.append("contains a finding ID")
    if any(re.search(p, lowered) for p in GENERIC_QUESTION_PATTERNS):
        problems.append("generic question true of any change")
    if any(phrase in lowered for phrase in PLACEHOLDER_PHRASES):
        problems.append("placeholder text")
    if any(re.search(p, lowered) for p in ACCESS_CLAIM_PATTERNS):
        problems.append("claims runtime access or contents")
    if question.anchor_kind not in VALID_ANCHORS or not question.anchor_ref.strip():
        problems.append("no anchor")
    if question.provenance is not None and question.provenance not in VALID_PROVENANCE:
        problems.append("unknown provenance label")
    if question.provenance is not None and question.provenance not in lowered:
        problems.append("provenance tag not present in the question text")
    return problems


def validate_case(case: ReasoningCheckpointCase) -> None:
    """Fail-closed structural validation of one fixture's data."""
    if not case.case_id.strip():
        raise ReasoningCheckpointFixtureError("case_id must be non-empty")
    if case.category not in VALID_CATEGORIES:
        raise ReasoningCheckpointFixtureError(f"{case.case_id}: bad category {case.category!r}")
    if not case.description.strip():
        raise ReasoningCheckpointFixtureError(f"{case.case_id}: empty description")
    unknown_kind = case.change_kind not in (INERT_CHANGE_KINDS | BEHAVIORAL_CHANGE_KINDS)
    if unknown_kind:
        raise ReasoningCheckpointFixtureError(f"{case.case_id}: bad change_kind {case.change_kind!r}")
    for question in case.candidates:
        if question.facet not in (FACET_INVESTIGATION, FACET_DESIGN):
            raise ReasoningCheckpointFixtureError(f"{case.case_id}: bad facet {question.facet!r}")
    for item in case.evidence_items:
        if item.status not in VALID_PROVENANCE:
            raise ReasoningCheckpointFixtureError(f"{case.case_id}: bad evidence status")
    if case.runtime_dependent and not case.expected_active:
        raise ReasoningCheckpointFixtureError(
            f"{case.case_id}: Condition R requires an active investigation facet"
        )


def validate_corpus(cases: tuple[ReasoningCheckpointCase, ...]) -> None:
    if not cases:
        raise ReasoningCheckpointFixtureError("corpus must not be empty")
    seen: set[str] = set()
    for case in cases:
        validate_case(case)
        if case.case_id in seen:
            raise ReasoningCheckpointFixtureError(f"duplicate case_id {case.case_id!r}")
        seen.add(case.case_id)


# ---------------------------------------------------------------------------
# The corpus
# ---------------------------------------------------------------------------

_P0 = (ds.Finding(id="F1", severity=ds.Severity.P0),)
_P1 = (ds.Finding(id="F1", severity=ds.Severity.P1),)
_P2 = (ds.Finding(id="F1", severity=ds.Severity.P2),)


def _q(
    text: str,
    facet: str,
    anchor_kind: str,
    anchor_ref: str,
    provenance: Optional[str] = None,
    restates_finding: bool = False,
) -> Question:
    return Question(text, facet, anchor_kind, anchor_ref, provenance, restates_finding)


_INV = FACET_INVESTIGATION
_DES = FACET_DESIGN

_Q_NULL_GUARD = _q(
    "The bug description attributes the crash to a null session token; "
    "(engineer-reported) no trace was supplied, so does the added guard in "
    "`auth/session.py` sit on the path that produced the reported crash?",
    _INV,
    ANCHOR_CHAIN_LINK,
    "bug-description: null session token hypothesis",
    PROV_REPORTED,
)
_Q_LIFECYCLE = _q(
    "`CacheWarmer.start()` now runs inside request handling although its "
    "owning abstraction, `AppLifecycle`, was inspected and still owns startup "
    "— is per-request startup the intended lifecycle boundary?",
    _DES,
    ANCHOR_PLACEMENT_RING,
    "CacheWarmer.start / AppLifecycle lifecycle-boundary ring",
)

ALL_CASES: tuple[ReasoningCheckpointCase, ...] = (
    # --- activation: bug fix ------------------------------------------------
    ReasoningCheckpointCase(
        case_id="bug-fix-bug-description-runtime-dependent",
        category=CATEGORY_ACTIVATION,
        covers=frozenset(
            {
                "bug-fix-investigation-activates",
                "clean-review-checkpoint-appears",
                "decision-severity-invariance",
                "rendering-local-and-github",
            }
        ),
        description="Bug fix with supplied bug-description context; the root-cause link is runtime evidence nobody supplied. Clean review, checkpoint legitimately appears, readiness scoped.",
        change_kind="bug-fix",
        signals=frozenset({SIG_CONTEXT_BUG_OR_INCIDENT}),
        expected_active=True,
        runtime_dependent=True,
        candidates=(_Q_NULL_GUARD,),
        what_changed="Adds a null guard before the session token is dereferenced.",
    ),
    ReasoningCheckpointCase(
        case_id="bug-fix-incident-followup-logs-unavailable",
        category=CATEGORY_RUNTIME_BOUNDARY,
        covers=frozenset(
            {
                "bug-fix-investigation-activates",
                "runtime-boundary-asks-not-assumes",
                "runtime-provenance-distinct",
                "no-invented-runtime-contents",
                "decision-severity-invariance",
            }
        ),
        description="Incident follow-up whose supplied context names dashboards/logs the reviewer cannot reach: the question asks whether they were inspected, and claims nothing about their contents.",
        change_kind="bug-fix",
        signals=frozenset({SIG_CONTEXT_BUG_OR_INCIDENT}),
        expected_active=True,
        runtime_dependent=True,
        candidates=(
            _q(
                "The incident ticket references a latency dashboard "
                "(possible but unavailable to this review), so did it show the "
                "retry storm starting before the change to `client/retry.py`?",
                _INV,
                ANCHOR_CHAIN_LINK,
                "incident-followup: latency dashboard / retry storm timing",
                PROV_UNAVAILABLE,
            ),
        ),
        evidence_items=(EvidenceItem("latency dashboard", PROV_UNAVAILABLE),),
        what_changed="Caps retry attempts in the HTTP client.",
    ),
    ReasoningCheckpointCase(
        case_id="bug-fix-three-provenance-classes-distinct",
        category=CATEGORY_RUNTIME_BOUNDARY,
        covers=frozenset(
            {
                "bug-fix-investigation-activates",
                "runtime-provenance-distinct",
                "runtime-boundary-asks-not-assumes",
                "no-invented-runtime-contents",
            }
        ),
        description="Three evidence items in one review -- a supplied stack trace read in-session, an engineer-stated repro, and an unreachable metrics system -- each carries its own distinct provenance label.",
        change_kind="bug-fix",
        signals=frozenset({SIG_CONTEXT_BUG_OR_INCIDENT}),
        expected_active=True,
        runtime_dependent=True,
        candidates=(
            _q(
                "The supplied stack trace (reviewer-inspected) ends in "
                "`parse_header`, so does the new length check cover the "
                "`parse_header` branch it names?",
                _INV,
                ANCHOR_CHAIN_LINK,
                "supplied stack trace / parse_header",
                PROV_INSPECTED,
            ),
            _q(
                "You stated the crash reproduces only on large uploads "
                "(engineer-reported), so what observation would show the fix "
                "holds on a large upload?",
                _INV,
                ANCHOR_CHAIN_LINK,
                "engineer-stated reproduction: large uploads",
                PROV_REPORTED,
            ),
            _q(
                "Upload metrics exist for this service (possible but "
                "unavailable here), so were they checked for the error rate "
                "after the fix?",
                _INV,
                ANCHOR_CHAIN_LINK,
                "upload metrics post-deploy verification",
                PROV_UNAVAILABLE,
            ),
        ),
        evidence_items=(
            EvidenceItem("supplied stack trace", PROV_INSPECTED),
            EvidenceItem("engineer-stated reproduction", PROV_REPORTED),
            EvidenceItem("upload metrics", PROV_UNAVAILABLE),
        ),
        what_changed="Adds a length check to the upload header parser.",
    ),
    ReasoningCheckpointCase(
        case_id="bug-fix-context-contradicts-repository-evidence",
        category=CATEGORY_ACTIVATION,
        covers=frozenset({"bug-fix-investigation-activates", "decision-severity-invariance"}),
        description="Supplied misbehavior text contradicts repository evidence; one question quotes both sides with class tags. Not runtime-dependent, so readiness language is unscoped.",
        change_kind="bug-fix",
        signals=frozenset({SIG_TEXT_OBSERVED_MISBEHAVIOR}),
        expected_active=True,
        runtime_dependent=False,
        candidates=(
            _q(
                "The PR text says orders are dropped on retry "
                "(engineer-reported), but `orders/queue.py` already "
                "re-enqueues on retry (reviewer-inspected), so which path "
                "actually drops them?",
                _INV,
                ANCHOR_CONTRADICTION,
                "PR text vs orders/queue.py retry path",
                PROV_REPORTED,
            ),
        ),
        what_changed="Changes retry ordering in the order queue.",
    ),
    ReasoningCheckpointCase(
        case_id="bug-fix-strong-content-signal-with-runtime-link",
        category=CATEGORY_ACTIVATION,
        covers=frozenset({"bug-fix-investigation-activates"}),
        description="A regression test naming the symptom plus a nameable runtime-dependent link activates the investigation facet with no tracker context.",
        change_kind="bug-fix",
        signals=frozenset({SIG_STRONG_CONTENT, SIG_NAMEABLE_UNVERIFIABLE_LINK}),
        expected_active=True,
        runtime_dependent=True,
        candidates=(
            _q(
                "`test_retry_does_not_duplicate_charge` (engineer-reported "
                "symptom) asserts the duplicate charge is gone, so does the "
                "production payment provider behave as this test's stub does?",
                _INV,
                ANCHOR_CHAIN_LINK,
                "regression test symptom vs provider behavior",
                PROV_REPORTED,
            ),
        ),
        what_changed="Makes charge retry idempotent and adds a regression test.",
    ),
    # --- activation: architecture/lifecycle --------------------------------
    ReasoningCheckpointCase(
        case_id="lifecycle-change-owning-ring-reached",
        category=CATEGORY_ACTIVATION,
        covers=frozenset(
            {
                "architecture-lifecycle-activates",
                "findings-present-questions-not-findings",
                "decision-severity-invariance",
                "rendering-local-and-github",
            }
        ),
        description="Lifecycle change where bounded placement expansion reached the lifecycle-boundary ring: the design question reuses that placement evidence, alongside a genuine P1 finding the questions never restate.",
        change_kind="lifecycle-change",
        findings=_P1,
        signals=frozenset({SIG_PLACEMENT_LIFECYCLE_RING}),
        expected_active=True,
        candidates=(_Q_LIFECYCLE,),
        what_changed="Moves cache warm-up into request handling.",
    ),
    ReasoningCheckpointCase(
        case_id="analogue-deviation-concrete-consequence",
        category=CATEGORY_ACTIVATION,
        covers=frozenset({"architecture-lifecycle-activates", "p2-only-non-blocking-checkpoint"}),
        description="Analogue-based trigger found a deviation with a concrete consequence; P2-only review stays clean and non-blocking while the question appears.",
        change_kind="feature",
        findings=_P2,
        signals=frozenset({SIG_ANALOGUE_DEVIATION}),
        expected_active=True,
        candidates=(
            _q(
                "Sibling handlers `refund.py` and `void.py` (inspected) emit "
                "an audit event on this transition but the new `chargeback.py` "
                "does not, so is the missing audit event deliberate?",
                _DES,
                ANCHOR_INSPECTED_PEER,
                "refund.py / void.py analogues vs chargeback.py",
            ),
        ),
        what_changed="Adds a chargeback handler.",
    ),
    ReasoningCheckpointCase(
        case_id="insufficient-evidence-boundary-move-no-invented-architecture",
        category=CATEGORY_INSUFFICIENT_EVIDENCE,
        covers=frozenset(
            {"architecture-lifecycle-activates", "insufficient-evidence-no-invention"}
        ),
        description="Placement ended at insufficient evidence on a change moving a responsibility across a boundary: the question asks about the boundary without inventing an owning abstraction.",
        change_kind="lifecycle-change",
        signals=frozenset({SIG_PLACEMENT_INSUFFICIENT_BOUNDARY_MOVE}),
        expected_active=True,
        candidates=(
            _q(
                "Session expiry handling moved from `middleware.py` into "
                "`handlers/login.py` and no owning abstraction could be "
                "established from the repository, so is `login.py` the "
                "intended owner of expiry?",
                _DES,
                ANCHOR_PLACEMENT_RING,
                "session expiry move; placement ended at insufficient evidence",
            ),
        ),
        what_changed="Relocates session expiry handling.",
    ),
    ReasoningCheckpointCase(
        case_id="unverifiable-hypothesis-single-question",
        category=CATEGORY_INSUFFICIENT_EVIDENCE,
        covers=frozenset(
            {
                "insufficient-evidence-no-invention",
                "bug-fix-investigation-activates",
                "no-invented-runtime-contents",
            }
        ),
        description="A stated hypothesis with no supporting evidence yields exactly one question saying it cannot be validated from available evidence; the code may still be correct and no root cause is invented.",
        change_kind="bug-fix",
        signals=frozenset({SIG_CONTEXT_BUG_OR_INCIDENT}),
        expected_active=True,
        runtime_dependent=True,
        candidates=(
            _q(
                "The ticket asserts a race in the cache refill "
                "(engineer-reported) with no trace or reproduction attached, "
                "so this cannot be validated from the available evidence: can "
                "you share a reproduction or trace for it?",
                _INV,
                ANCHOR_CHAIN_LINK,
                "ticket hypothesis: race in cache refill, no evidence supplied",
                PROV_REPORTED,
            ),
        ),
        what_changed="Adds a lock around the cache refill.",
    ),
    # --- inert: trivial / weak signal / generic-only ------------------------
    *(
        ReasoningCheckpointCase(
            case_id=f"trivial-{kind}-inert",
            category=CATEGORY_INERT,
            covers=frozenset(
                {"trivial-change-absent", "ordinary-reviews-no-checkpoint", "rendering-local-and-github"}
            ),
            description=f"Trivial change ({kind}) never activates, even with a bug-shaped commit prefix and branch name.",
            change_kind=kind,
            signals=frozenset({"fix-commit-prefix", "bug-shaped-branch-name"}),
            candidates=(
                _q(
                    "Did you test this change?",
                    _INV,
                    ANCHOR_CHAIN_LINK,
                    "",
                ),
            ),
            what_changed=f"A {kind} change.",
        )
        for kind in sorted(INERT_CHANGE_KINDS)
    ),
    ReasoningCheckpointCase(
        case_id="weak-signals-only-small-guard-inert",
        category=CATEGORY_INERT,
        covers=frozenset({"trivial-change-absent", "ordinary-reviews-no-checkpoint"}),
        description="A bare fix: prefix, bug-shaped branch, tracker type Bug, and a small helper guard are not signals; the checkpoint stays absent.",
        change_kind="bug-fix",
        signals=frozenset(NON_SIGNALS),
        candidates=(_Q_NULL_GUARD,),
        what_changed="Adds a guard to a string helper.",
    ),
    ReasoningCheckpointCase(
        case_id="strong-content-signal-without-nameable-link-inert",
        category=CATEGORY_INERT,
        covers=frozenset({"trivial-change-absent", "ordinary-reviews-no-checkpoint"}),
        description="A regression test names the symptom but the reviewer cannot name any runtime-dependent link it cannot verify: the content signal alone does not activate.",
        change_kind="bug-fix",
        signals=frozenset({SIG_STRONG_CONTENT}),
        candidates=(_Q_NULL_GUARD,),
        what_changed="Fixes a pure-function off-by-one and adds a regression test.",
    ),
    ReasoningCheckpointCase(
        case_id="placement-direct-caller-confirmed-inert",
        category=CATEGORY_INERT,
        covers=frozenset({"trivial-change-absent", "ordinary-reviews-no-checkpoint"}),
        description="A placement trigger that stopped at the direct caller with placement confirmed correct is inert.",
        change_kind="ordinary",
        signals=frozenset({SIG_PLACEMENT_DIRECT_CONFIRMED}),
        candidates=(_Q_LIFECYCLE,),
        what_changed="Adds a helper next to its only caller.",
    ),
    ReasoningCheckpointCase(
        case_id="no-anchorable-question-fails-closed",
        category=CATEGORY_INSUFFICIENT_EVIDENCE,
        covers=frozenset(
            {"insufficient-evidence-no-invention", "trivial-change-absent", "ordinary-reviews-no-checkpoint"}
        ),
        description="Activation evidence exists but no question can be anchored to something the review gathered: no section and no 'insufficient context' placeholder.",
        change_kind="bug-fix",
        signals=frozenset({SIG_CONTEXT_BUG_OR_INCIDENT}),
        candidates=(
            _q("Is the root cause what you expect?", _INV, ANCHOR_CHAIN_LINK, ""),
        ),
        what_changed="Adjusts error handling.",
    ),
    ReasoningCheckpointCase(
        case_id="candidate-restating-a-finding-is-dropped",
        category=CATEGORY_FINDINGS_INTERACTION,
        covers=frozenset(
            {"findings-present-questions-not-findings", "insufficient-evidence-no-invention"}
        ),
        description="The only candidate restates an already-reported P0 finding; it is dropped, so the section is absent and the finding stands alone.",
        change_kind="bug-fix",
        findings=_P0,
        signals=frozenset({SIG_CONTEXT_BUG_OR_INCIDENT}),
        candidates=(
            _q(
                "Does the unparameterized query in `db/lookup.py` allow injection?",
                _INV,
                ANCHOR_CHAIN_LINK,
                "db/lookup.py query",
                restates_finding=True,
            ),
        ),
        what_changed="Changes a lookup query.",
    ),
    ReasoningCheckpointCase(
        case_id="findings-p0-with-checkpoint-stays-changes-required",
        category=CATEGORY_FINDINGS_INTERACTION,
        covers=frozenset(
            {
                "findings-present-questions-not-findings",
                "decision-severity-invariance",
                "bug-fix-investigation-activates",
                "rendering-local-and-github",
            }
        ),
        description="Genuine P0 present and checkpoint active: questions carry no severity or ID, and the Decision stays CHANGES REQUIRED with the checkpoint on or off.",
        change_kind="bug-fix",
        findings=_P0,
        signals=frozenset({SIG_CONTEXT_BUG_OR_INCIDENT}),
        expected_active=True,
        runtime_dependent=True,
        candidates=(_Q_NULL_GUARD,),
        what_changed="Adds a null guard before token use and rewrites token lookup.",
    ),
    # --- inert under incomplete / unresolved --------------------------------
    ReasoningCheckpointCase(
        case_id="review-incomplete-coverage-inert",
        category=CATEGORY_INERT,
        covers=frozenset({"inert-under-incomplete-or-unresolved", "trivial-change-absent"}),
        description="Coverage incomplete (REVIEW INCOMPLETE already says do not trust): the checkpoint is inert even with full activation evidence.",
        change_kind="bug-fix",
        signals=frozenset({SIG_CONTEXT_BUG_OR_INCIDENT}),
        coverage_incomplete=True,
        candidates=(_Q_NULL_GUARD,),
        what_changed="Adds a null guard.",
    ),
    ReasoningCheckpointCase(
        case_id="jira-context-unresolved-inert",
        category=CATEGORY_INERT,
        covers=frozenset({"inert-under-incomplete-or-unresolved", "trivial-change-absent"}),
        description="An unresolved supplied Jira reference leaves the report ungraded; the checkpoint stays inert.",
        change_kind="bug-fix",
        signals=frozenset({SIG_CONTEXT_BUG_OR_INCIDENT}),
        jira_unresolved=True,
        candidates=(_Q_NULL_GUARD,),
        what_changed="Adds a null guard.",
    ),
    # --- bound --------------------------------------------------------------
    ReasoningCheckpointCase(
        case_id="question-ceiling-six-candidates-capped-at-four",
        category=CATEGORY_NOISE_BOUND,
        covers=frozenset({"question-count-ceiling", "architecture-lifecycle-activates"}),
        description="Six anchored candidates (design ones listed first) reduce to four, investigation questions ordered first.",
        change_kind="bug-fix",
        signals=frozenset({SIG_CONTEXT_BUG_OR_INCIDENT, SIG_PLACEMENT_LIFECYCLE_RING}),
        expected_active=True,
        runtime_dependent=True,
        candidates=(
            _q("Is `A.start()` the intended owner of warm-up?", _DES, ANCHOR_PLACEMENT_RING, "A.start ring"),
            _q("Is `B.stop()` the intended owner of drain?", _DES, ANCHOR_PLACEMENT_RING, "B.stop ring"),
            _q(
                "The ticket blames a stale cache (engineer-reported), so does the new invalidation cover that path?",
                _INV, ANCHOR_CHAIN_LINK, "ticket: stale cache", PROV_REPORTED,
            ),
            _q(
                "The ticket names a slow query (engineer-reported), so was its plan checked?",
                _INV, ANCHOR_CHAIN_LINK, "ticket: slow query", PROV_REPORTED,
            ),
            _q(
                "The repro steps (engineer-reported) omit the retry case, so does the fix hold on retry?",
                _INV, ANCHOR_CHAIN_LINK, "repro steps: retry", PROV_REPORTED,
            ),
            _q("Is `C.reset()` the intended owner of cleanup?", _DES, ANCHOR_PLACEMENT_RING, "C.reset ring"),
        ),
        what_changed="Reworks lifecycle hooks and cache invalidation.",
    ),
    *(
        ReasoningCheckpointCase(
            case_id=f"ordinary-review-{name}-no-checkpoint",
            category=CATEGORY_NOISE_BOUND,
            covers=frozenset({"ordinary-reviews-no-checkpoint", "rendering-local-and-github"}),
            description=f"Ordinary review ({name}) carries no activation evidence; no checkpoint, findings and Decision untouched.",
            change_kind="ordinary",
            findings=findings,
            what_changed=f"An ordinary {name} change.",
        )
        for name, findings in (
            ("clean", ()),
            ("p2-only", _P2),
            ("p1", _P1),
            ("p0", _P0),
        )
    ),
)


def cases_covering(tag: str) -> tuple[ReasoningCheckpointCase, ...]:
    return tuple(case for case in ALL_CASES if tag in case.covers)


def cases_in_category(category: str) -> tuple[ReasoningCheckpointCase, ...]:
    return tuple(case for case in ALL_CASES if case.category == category)


validate_corpus(ALL_CASES)
