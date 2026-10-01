#!/usr/bin/env python3
"""Test-only reference for the relationship capability contract (Issue #603).

Mirrors docs/repository-intelligence/relationship-capability-contract.md: the
closed set of relationship questions, the provenance-carrying answer shape,
how a host-provided answer is consumed (stale data rejected, unverifiable
edges dropped, absence only when attested), the #601 outcome each consumed
answer maps to, and the repository-search fallback for every question.
Not runtime logic, not packaged — the packaged Skills are Markdown/YAML only.

The module models *consumption* of an answer. It never computes a
relationship, names a provider, or persists anything; a host answer is a
claim the reviewer verifies, never a fact it trusts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, FrozenSet, Mapping

from tests.reference.review import repository_intelligence as ri


class Question(Enum):
    CONSUMERS_OF = "consumers_of"
    IMPLEMENTERS_OF = "implementers_of"
    TESTS_EXERCISING = "tests_exercising"
    ANALOGUES_OF = "analogues_of"


class RelationshipClass(Enum):
    """The #601 initial classes, reused verbatim."""

    CALLER_CONSUMER = "caller_consumer"
    IMPLEMENTATION_INTERFACE = "implementation_interface"
    AFFECTED_TEST = "affected_test"


class Outcome(Enum):
    """The #601 outcomes, reused verbatim."""

    RESOLVED_RELEVANT = "resolved_relevant"
    RESOLVED_NONE = "resolved_none"
    UNRESOLVED = "unresolved"


# Question -> the #601 class it answers. Analogue is deliberately absent:
# #601 left it out of scope, so an analogue answer is advisory evidence with
# no outcome and no Context gap.
QUESTION_CLASS: Mapping[Question, RelationshipClass | None] = {
    Question.CONSUMERS_OF: RelationshipClass.CALLER_CONSUMER,
    Question.IMPLEMENTERS_OF: RelationshipClass.IMPLEMENTATION_INTERFACE,
    Question.TESTS_EXERCISING: RelationshipClass.AFFECTED_TEST,
    Question.ANALOGUES_OF: None,
}

# Question -> the relationship kinds an answer may carry. Any other kind in
# an answer is dropped, not trusted.
QUESTION_KINDS: Mapping[Question, FrozenSet[ri.RelationshipKind]] = {
    Question.CONSUMERS_OF: frozenset(
        {
            ri.RelationshipKind.CALLS,
            ri.RelationshipKind.IMPORTS,
            ri.RelationshipKind.REFERENCES,
        }
    ),
    Question.IMPLEMENTERS_OF: frozenset({ri.RelationshipKind.IMPLEMENTS}),
    Question.TESTS_EXERCISING: frozenset({ri.RelationshipKind.TESTED_BY}),
    Question.ANALOGUES_OF: frozenset({ri.RelationshipKind.ANALOGUE_OF}),
}

# Question -> the existing repository-search procedure that answers it with no
# capability present (design record §8). Names, not logic: each procedure is
# already defined by a packaged policy.
FALLBACK_PROCEDURE: Mapping[Question, str] = {
    Question.CONSUMERS_OF: "repository-expansion ring search",
    Question.IMPLEMENTERS_OF: "repository-expansion ring search",
    Question.TESTS_EXERCISING: "affected-test-analysis tracing",
    Question.ANALOGUES_OF: "review-scope analogue and placement search",
}

# Questions whose edges carry a ring, so a ring ceiling is mandatory.
RING_BEARING: FrozenSet[Question] = frozenset(
    {Question.CONSUMERS_OF, Question.IMPLEMENTERS_OF}
)

# Bound on one answer; an answer over it cannot claim to be complete.
MAX_EDGES_PER_ANSWER = 100


class UnresolvedReason(Enum):
    AMBIGUOUS_RESOLUTION = "ambiguous resolution"
    UNSUPPORTED_LANGUAGE = "unsupported language shape"
    CAPABILITY_ABSENT = "capability absent"
    STALE_SNAPSHOT = "stale snapshot"
    UNVERIFIABLE_PROVENANCE = "unverifiable provenance"
    INCOMPLETE_SEARCH = "search not attested complete"
    OVERSIZE_ANSWER = "answer exceeds bound"
    MISMATCHED_ANSWER = "answer is for another question or subject"


@dataclass(frozen=True)
class AmbiguousCandidate:
    """A candidate the capability itself could not resolve. Never an edge."""

    reason: UnresolvedReason = UnresolvedReason.AMBIGUOUS_RESOLUTION


@dataclass(frozen=True)
class CapabilityAnswer:
    """What a host capability returns for one question.

    `complete` is the capability's attestation that it searched a scope able
    to find the relationship inside the authorized ring. Without it an empty
    `edges` tuple says nothing.
    """

    question: Question
    subject: str
    snapshot_id: str
    edges: tuple[ri.Relationship, ...] = ()
    candidates: tuple[AmbiguousCandidate, ...] = ()
    complete: bool = False


@dataclass(frozen=True)
class ConsumedAnswer:
    question: Question
    subject: str
    outcome: Outcome | None  # None: the capability contributed no outcome
    used_edges: tuple[ri.Relationship, ...]
    unresolved: tuple[UnresolvedReason, ...]
    fallback_required: bool

    def has_context_gap(self, fallback_outcome: Outcome | None = None) -> bool:
        """Whether this question must render in Context gaps (#601).

        Judged after the fallback has had its say: a rejected, stale, or
        absent answer is a diagnostic, not a gap, when the fallback resolves
        the question. Ambiguity the capability itself reported beside a
        usable answer stays a gap. An advisory analogue answer has no class
        and therefore no gap.
        """
        if QUESTION_CLASS[self.question] is None:
            return False
        if finalize(self, fallback_outcome) is Outcome.UNRESOLVED:
            return True
        return not self.fallback_required and bool(self.unresolved)


def _is_repo_relative(path: str) -> bool:
    if not path or path.startswith(("/", "\\")) or ":" in path.split("/")[0]:
        return False
    return ".." not in path.replace("\\", "/").split("/")


def _provenance_ok(
    edge: ri.Relationship, verify: Callable[[ri.Provenance], bool]
) -> bool:
    prov = edge.provenance
    return (
        _is_repo_relative(prov.path)
        and prov.line >= 1
        and _is_repo_relative(edge.source.path)
        and _is_repo_relative(edge.target.path)
        and verify(prov)
    )


def consume(
    answer: CapabilityAnswer | None,
    *,
    question: Question,
    subject: str,
    reviewed_snapshot_id: str,
    ring_ceiling: int | None,
    verify: Callable[[ri.Provenance], bool],
) -> ConsumedAnswer:
    """Turn a host answer into a #601 outcome, or a fallback requirement.

    - A ring-bearing question requires a ring ceiling (ValueError otherwise).
    - No answer: capability absent, so the repository-search fallback runs.
    - Snapshot mismatch: the whole answer is rejected (never warned about,
      never partially used) and the fallback runs.
    - An answer to a different question or subject is rejected the same way.
    - Edges with a kind outside the question's set, a ring above the ceiling,
      a non-repo-relative or unverified `path:line` are dropped.
    - Surviving edges: `resolved_relevant`; candidates the capability could
      not resolve stay unresolved alongside them, never promoted to edges.
    - No surviving edge: `resolved_none` only when the answer attests a
      complete search and nothing was dropped or ambiguous; otherwise
      `unresolved` and the fallback runs.
    """
    if question in RING_BEARING and ring_ceiling is None:
        raise ValueError(f"{question.value} requires a ring ceiling")
    if answer is None:
        return ConsumedAnswer(
            question, subject, None, (), (UnresolvedReason.CAPABILITY_ABSENT,), True
        )
    if answer.snapshot_id != reviewed_snapshot_id:
        return ConsumedAnswer(
            question, subject, None, (), (UnresolvedReason.STALE_SNAPSHOT,), True
        )
    if answer.question is not question or answer.subject != subject:
        return ConsumedAnswer(
            question, subject, None, (), (UnresolvedReason.MISMATCHED_ANSWER,), True
        )
    if len(answer.edges) > MAX_EDGES_PER_ANSWER:
        return ConsumedAnswer(
            question, subject, None, (), (UnresolvedReason.OVERSIZE_ANSWER,), True
        )

    allowed = QUESTION_KINDS[question]
    kept: list[ri.Relationship] = []
    dropped = False
    for edge in answer.edges:
        in_ring = edge.ring is None or (
            ring_ceiling is not None and edge.ring <= ring_ceiling
        )
        if edge.kind in allowed and in_ring and _provenance_ok(edge, verify):
            kept.append(edge)
        else:
            dropped = True

    unresolved = tuple(c.reason for c in answer.candidates)
    if kept:
        return ConsumedAnswer(
            question, subject, Outcome.RESOLVED_RELEVANT, tuple(kept), unresolved, False
        )

    if unresolved:
        return ConsumedAnswer(question, subject, Outcome.UNRESOLVED, (), unresolved, True)
    if dropped:
        return ConsumedAnswer(
            question,
            subject,
            Outcome.UNRESOLVED,
            (),
            (UnresolvedReason.UNVERIFIABLE_PROVENANCE,),
            True,
        )
    if answer.complete:
        return ConsumedAnswer(question, subject, Outcome.RESOLVED_NONE, (), (), False)
    return ConsumedAnswer(
        question,
        subject,
        Outcome.UNRESOLVED,
        (),
        (UnresolvedReason.INCOMPLETE_SEARCH,),
        True,
    )


def finalize(
    consumed: ConsumedAnswer, fallback_outcome: Outcome | None
) -> Outcome | None:
    """The question's final outcome after the fallback has had its say.

    When the capability decided, its outcome stands. When it required the
    fallback, the existing search's own outcome applies; a fallback that was
    not run, or could not answer, leaves the question `unresolved`. An
    advisory analogue question has no outcome at all.
    """
    if QUESTION_CLASS[consumed.question] is None:
        return None
    if not consumed.fallback_required:
        return consumed.outcome
    return fallback_outcome if fallback_outcome is not None else Outcome.UNRESOLVED


# --- Capability declaration (design record §9) ---------------------------

DECLARATION: Mapping[str, object] = {
    "capability": "relationship-query",
    "summary": "Optional host-provided answers to relationship questions, "
    "consumed as verifiable claims.",
    "loads": "on-activation",
    "activation": [
        "the host declares the relationship-query capability for the session",
        "a relationship question is open for a fired trigger or a signal-triggered pass",
    ],
    "adapters": ["local", "github"],
    "files": [],
    "requires": [],
    "never": [
        "be required for a review to complete",
        "answer from a snapshot other than the reviewed one",
        "mutate the repository, the host, or any external system",
        "persist relationship data across reviews",
        "widen the Review Target or reach another repository",
        "supply a severity, a decision, or a finding",
    ],
    "benchmark": "benchmark/corpus/relationship-recall",
}

PROHIBITED_CAPABILITY_NAME_FRAGMENTS: FrozenSet[str] = frozenset(
    {
        "persist",
        "publish",
        "submit",
        "approve",
        "request_changes",
        "merge",
        "delete",
        "push",
        "commit",
        "auto_approve",
        "background_index",
        "daemon",
        "invent_relationship",
        "assume_resolved",
        "trust_answer",
    }
)


def public_callables() -> tuple[str, ...]:
    return ("consume", "finalize", "has_context_gap")
