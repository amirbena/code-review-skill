#!/usr/bin/env python3
"""Finding-identity regression suite (Issue #61).

A dedicated, data-driven regression corpus for the stable finding identity
derivation. Where ``test_finding_identity.py`` is the focused #60 acceptance
set, this module encodes the *full* identity requirement scenario set:

- ``docs/findings/finding-identity-requirements.md`` §2 (must-survive) and §3
  (must-change);
- ``docs/findings/finding-stable-identity.md`` §6.4 (the #59 -> #60 hand-off,
  the only matching touch-point asserted here) and §7 (fail-closed);
- the adversarial permutations `finding-matching-strategy.md` §7 ("#61 —
  regression tests") calls for: wording changes, location movement,
  anchor/context changes, semantic discriminators, negation, literal/operator
  changes, duplicated anchors, path case, and weak/degenerate descriptors.

Matching, lifecycle, and review-delta behavior stay out of scope: the corpus
only reaches the already-defined #59 hand-off boundary via
``effective_identity``.

Every scenario is a pure predicate over an ``Impl`` (the four reference
callables), so the same corpus drives two things:

1. ``FindingIdentityRegressionTests`` — the real reference model must satisfy
   every scenario;
2. ``InducedRegressionTests`` — each representative identity bug (a mutated
   ``Impl``) must be caught by at least one scenario, proving the suite has
   teeth.

The reference model (``tests/reference/finding_identity.py``) is consumed as
the single identity algorithm; this module never defines a second one. It is
test-only and not packaged.

Larger labeled-corpus / retrieval-cutoff benchmark work is #40's, not here.
"""

from __future__ import annotations

import dataclasses
import hashlib
import unittest
from collections import namedtuple
from typing import Callable

from tests.reference import finding_identity as fi

# ---------------------------------------------------------------------------
# The identity algorithm under test, as four swappable callables.
# ---------------------------------------------------------------------------

Impl = namedtuple("Impl", "build mint effective is_matchable")

REAL = Impl(
    build=fi.build_descriptor,
    mint=fi.mint_identity,
    effective=fi.effective_identity,
    is_matchable=fi.is_matchable,
)

_PRIOR = "fid_v1_" + "e" * 32  # a plausible established prior identity


def _base(**overrides: object) -> dict:
    """Kwargs for one fully-populated, source-backed, matchable finding."""
    kw = dict(
        repository="github.com/acme/widgets",
        location="src/pay/retry.py:88",
        behavioral_claim_text=(
            "the row is re-enqueued before the commit so a retry "
            "processes the payment twice"
        ),
        anchor_fragment="queue.put(job)",
        mechanism_fragment="queue.put(job)",
        defect_kind_text="lost update",
        symbol="pay.retry.RetryHandler.run",
        construct="call",
        sibling_source="row.status = 'pending'\nqueue.put(job)\nlog.info('queued')",
        predecessor_source="row.status = 'pending'",
        successor_source="log.info('queued')",
    )
    kw.update(overrides)
    return kw


# ---------------------------------------------------------------------------
# Predicate combinators. Each returns Callable[[Impl], bool].
# ---------------------------------------------------------------------------

Predicate = Callable[[Impl], bool]


def same(a: dict, b: dict) -> Predicate:
    return lambda im: im.mint(im.build(**a)) == im.mint(im.build(**b))


def distinct(a: dict, b: dict) -> Predicate:
    return lambda im: im.mint(im.build(**a)) != im.mint(im.build(**b))


def non_matchable(a: dict) -> Predicate:
    return lambda im: not im.is_matchable(im.build(**a))


def matchable(a: dict) -> Predicate:
    return lambda im: im.is_matchable(im.build(**a))


def minted_shape(a: dict) -> Predicate:
    def check(im: Impl) -> bool:
        value = im.mint(im.build(**a))
        return (
            isinstance(value, str)
            and value.startswith("fid_v1_")
            and len(value) == len("fid_v1_") + 32
            and value == value.lower()
        )

    return check


def propagates_prior(a: dict, prior: str = _PRIOR) -> Predicate:
    return lambda im: im.effective(im.build(**a), matched_prior_identity=prior) == prior


def mints_fresh_despite_prior(a: dict, prior: str = _PRIOR) -> Predicate:
    return lambda im: (
        im.effective(im.build(**a), matched_prior_identity=prior)
        == im.mint(im.build(**a))
    )


def mints_fresh_on_no_match(a: dict) -> Predicate:
    return lambda im: im.effective(im.build(**a)) == im.mint(im.build(**a))


def all_of(*predicates: Predicate) -> Predicate:
    return lambda im: all(p(im) for p in predicates)


# ---------------------------------------------------------------------------
# Scenario corpus.
# ---------------------------------------------------------------------------

Scenario = namedtuple("Scenario", "id group requirement predicate")


def _scenarios() -> list[Scenario]:
    S: list[Scenario] = []

    def add(id_: str, group: str, requirement: str, predicate: Predicate) -> None:
        S.append(Scenario(id_, group, requirement, predicate))

    # -- Stability: identity survives (requirements §2) ----------------------

    add(
        "stable/line-number-movement",
        "stability",
        "req §2.1 — code above shifted the line number only",
        same(_base(location="src/pay/retry.py:88"), _base(location="src/pay/retry.py:412")),
    )
    add(
        "stable/nearby-unrelated-edits",
        "stability",
        "req §2.2 — sibling statements / neighbors changed, defect did not",
        same(
            _base(),
            _base(
                sibling_source="audit.record(row)\nqueue.put(job)\nmetrics.bump()",
                predecessor_source="audit.record(row)",
                successor_source="metrics.bump()",
            ),
        ),
    )
    add(
        "stable/reformatting",
        "stability",
        "req §2.3 — whitespace / wrapping / trailing comma / comment reflow",
        same(
            _base(anchor_fragment="queue.put(job)", mechanism_fragment="queue.put(job)"),
            _base(
                anchor_fragment="queue . put(\n    job,\n)   # re-enqueue the row\n",
                mechanism_fragment="queue.put(  job  )",
            ),
        ),
    )
    add(
        "stable/surrounding-lines-inserted-removed",
        "stability",
        "req §2.4 — a guard clause added earlier in the same function",
        same(
            _base(predecessor_source="row.status = 'pending'"),
            _base(
                predecessor_source="if not row:\n    return\nrow.status = 'pending'",
                successor_source="log.info('queued')\nreturn job",
            ),
        ),
    )
    add(
        "stable/file-local-movement-of-defect",
        "stability",
        "req §2.5 — defect block moved within the file, same logical role",
        same(
            _base(location="src/pay/retry.py:88"),
            _base(
                location="src/pay/retry.py:206",
                sibling_source="x = prepare(row)\nqueue.put(job)\ny = finish(row)",
                predecessor_source="x = prepare(row)",
                successor_source="y = finish(row)",
            ),
        ),
    )
    add(
        "stable/reviewer-wording-trivial",
        "stability",
        "req §2.6 — case / whitespace / punctuation / dropped commas only",
        same(
            _base(
                behavioral_claim_text=(
                    "the row is re-enqueued before the commit so a retry "
                    "processes the payment twice"
                )
            ),
            _base(
                behavioral_claim_text=(
                    "  The row is re-enqueued, before the commit,  SO a retry "
                    "processes the payment twice.  "
                )
            ),
        ),
    )
    add(
        "stable/severity-reclassification",
        "stability",
        "req §2.7 — P2 -> P1 re-rating of the same defect",
        same(_base(severity="P2"), _base(severity="P1")),
    )
    add(
        "stable/cross-skill-portability",
        "stability",
        "req §2.8 / §5.5 — local-review annotation + PR HEAD SHA must not shift identity",
        same(
            _base(repository_state_annotation="unstaged", head_sha="c0ffee", pr_number=7),
            _base(),
        ),
    )
    add(
        "stable/rebase-textually-identical",
        "stability",
        "req §2.9 — commit SHAs / review base changed, defect text unchanged",
        same(_base(head_sha="1111111", base_sha="aaaaaaa"), _base(head_sha="2222222", base_sha="bbbbbbb")),
    )
    add(
        "stable/parser-refinement-is-diagnostic-only",
        "stability",
        "stable-identity §5 — diagnostic_symbol / diagnostic_construct are never hashed",
        same(
            _base(diagnostic_symbol=None, diagnostic_construct=None),
            _base(
                diagnostic_symbol="pay.retry.RetryHandler.run#L88",
                diagnostic_construct="await_call",
            ),
        ),
    )
    add(
        "stable/equivalent-mechanism-fragment",
        "stability",
        "req §2 — an equivalent finding whose mechanism fragment is formatted differently",
        same(
            _base(mechanism_fragment="queue.put(job)"),
            _base(mechanism_fragment="queue.put(\n  job,\n)"),
        ),
    )
    add(
        "stable/deterministic-across-repeats",
        "stability",
        "req §5.1 — a fixed finding + fixed state mints one value every run",
        lambda im: len({im.mint(im.build(**_base())) for _ in range(30)}) == 1,
    )
    add(
        "stable/order-independent",
        "stability",
        "req §5.2 — identity does not depend on how many other findings exist",
        _order_independent_predicate(),
    )

    # -- Separation: a new identity is required (requirements §3) -----------

    add(
        "distinct/different-defect-same-location",
        "separation",
        "req §3.1 — different faulty behavior / root cause at the same site",
        distinct(
            _base(),
            _base(
                behavioral_claim_text="the amount is read as a float so rounding drifts on large sums",
                anchor_fragment="total = float(amount)",
                mechanism_fragment="total = float(amount)",
                defect_kind_text="precision loss",
            ),
        ),
    )
    add(
        "distinct/same-pattern-different-program-element",
        "separation",
        "req §3.2 — the same missing-guard pattern in a different symbol",
        distinct(
            _base(symbol="pay.retry.RetryHandler.run"),
            _base(symbol="pay.refund.RefundHandler.run"),
        ),
    )
    add(
        "distinct/old-defect-fixed-distinct-defect-nearby",
        "separation",
        "req §3.3 — a different problem now occupies the same file/symbol",
        distinct(
            _base(),
            _base(
                behavioral_claim_text="the lock is released early so two workers enter the section",
                anchor_fragment="lock.release()",
                mechanism_fragment="lock.release()",
                defect_kind_text="race condition",
            ),
        ),
    )
    add(
        "distinct/similar-wording-different-problem",
        "separation",
        "req §3.4 — near-identical claim text, unrelated defect",
        distinct(
            _base(
                behavioral_claim_text="the guard is missing so the request is not validated",
                anchor_fragment="handler.dispatch(req)",
                mechanism_fragment="handler.dispatch(req)",
            ),
            _base(
                behavioral_claim_text="the guard is missing so the request is not validated",
                anchor_fragment="worker.enqueue(req)",
                mechanism_fragment="worker.enqueue(req)",
            ),
        ),
    )
    add(
        "distinct/same-message-text-different-path",
        "separation",
        "req §3.5 — re-used phrasing at a new path does not carry identity",
        distinct(
            _base(location="src/pay/retry.py:88"),
            _base(location="src/pay/refund.py:88"),
        ),
    )
    add(
        "distinct/location-intent-changed",
        "separation",
        "req §3.6 — a file-level finding and a line-level finding are different",
        distinct(
            _base(location="src/pay/retry.py:88"),
            _base(location="file", path="src/pay/retry.py"),
        ),
    )
    add(
        "distinct/cross-file-vs-line-intent",
        "separation",
        "req §3.6 — a repository-scoped finding is not a line finding",
        distinct(
            _base(location="src/pay/retry.py:88"),
            _base(location="repository", path=None, anchor_fragment="queue.put(job)"),
        ),
    )
    add(
        "distinct/semantic-discriminator-same-site-and-snippet",
        "separation",
        "stable-identity §6.1 — SQLi vs cross-tenant leak on one db.execute line; "
        "cause_key / behavior_key are the only difference and MUST split, "
        "and both stay matchable",
        all_of(
            distinct(
                _base(
                    behavioral_claim_text="q is built by string interpolation so untrusted input reaches sql",
                    anchor_fragment="row = db.execute(q)",
                    mechanism_fragment="row = db.execute(q)",
                ),
                _base(
                    behavioral_claim_text="the tenant filter is missing so another tenant's rows are returned",
                    anchor_fragment="row = db.execute(q)",
                    mechanism_fragment="row = db.execute(q)",
                ),
            ),
            matchable(
                _base(
                    behavioral_claim_text="q is built by string interpolation so untrusted input reaches sql",
                    anchor_fragment="row = db.execute(q)",
                    mechanism_fragment="row = db.execute(q)",
                )
            ),
        ),
    )

    # -- Adversarial permutations (matching-strategy §7) -------------------

    add(
        "adversarial/anchor-token-order-significant",
        "adversarial",
        "matching-strategy §2 — operand order carries meaning",
        distinct(_base(anchor_fragment="a and not b"), _base(anchor_fragment="b and not a")),
    )
    add(
        "adversarial/operator-change-in-anchor",
        "adversarial",
        "req §3.1 — a changed operator is a different defect",
        distinct(
            _base(anchor_fragment="pages = total // size", mechanism_fragment="pages = total // size"),
            _base(anchor_fragment="pages = total / size", mechanism_fragment="pages = total / size"),
        ),
    )
    add(
        "adversarial/literal-change-in-string",
        "adversarial",
        "tokenizer §3.1 — quoted literals are preserved verbatim",
        distinct(
            _base(anchor_fragment='http.get("https://host/admin")', mechanism_fragment='http.get("https://host/admin")'),
            _base(anchor_fragment='http.get("https://host/guest")', mechanism_fragment='http.get("https://host/guest")'),
        ),
    )
    add(
        "adversarial/leading-negation-preserved",
        "adversarial",
        "stable-identity §3.2 — a clause-leading `!` is negation, not trimmed",
        distinct(
            _base(behavioral_claim_text="the guard runs so !authorized paths execute"),
            _base(behavioral_claim_text="the guard runs so authorized paths execute"),
        ),
    )
    add(
        "adversarial/comment-outside-string-ignored",
        "adversarial",
        "tokenizer §3.1 — a trailing `#` comment outside a string does not discriminate",
        same(
            _base(anchor_fragment="x = compute(y)  # first note", mechanism_fragment="x = compute(y)"),
            _base(anchor_fragment="x = compute(y)  # a different note", mechanism_fragment="x = compute(y)"),
        ),
    )
    add(
        "adversarial/hash-inside-string-kept",
        "adversarial",
        "tokenizer §3.1 — `#` inside a quoted literal is content, not a comment",
        distinct(
            _base(anchor_fragment='style(color="#fff")', mechanism_fragment='style(color="#fff")'),
            _base(anchor_fragment='style(color="#000")', mechanism_fragment='style(color="#000")'),
        ),
    )
    add(
        "adversarial/trailing-sentence-punctuation-trimmed",
        "adversarial",
        "stable-identity §6.1 — trailing `.`/`!` on a claim clause does not re-mint",
        same(
            _base(behavioral_claim_text="a so the value is dropped"),
            _base(behavioral_claim_text="a so the value is dropped!!"),
        ),
    )
    add(
        "adversarial/defect-kind-wording-not-hashed",
        "adversarial",
        "stable-identity §6.1 — free-form defect_kind slug is not a hash discriminator",
        same(
            _base(defect_kind_text="missing null check"),
            _base(defect_kind_text="no null-check!"),
        ),
    )
    add(
        "adversarial/occurrence-context-change-not-hashed",
        "adversarial",
        "stable-identity §6.1 — context_tokens / neighboring_syntax are excluded",
        same(
            _base(
                sibling_source="row.status = 'pending'\nqueue.put(job)\nlog.info('queued')",
                predecessor_source="row.status = 'pending'",
                successor_source="log.info('queued')",
            ),
            _base(
                sibling_source="t = now()\nqueue.put(job)\nemit(t)",
                predecessor_source="t = now()",
                successor_source="emit(t)",
            ),
        ),
    )
    add(
        "adversarial/path-case-sensitivity",
        "adversarial",
        "stable-identity §3.2 — default path comparison is case-sensitive",
        distinct(
            _base(location="src/pay/retry.py:88"),
            _base(location="src/Pay/Retry.py:88"),
        ),
    )
    add(
        "adversarial/reword-splits-then-match-reunifies",
        "adversarial",
        "stable-identity §6.1 / §9 — a claim reworded enough to change behavior_key "
        "tokens is a visible false split; a definite #59 MATCH re-propagates",
        all_of(
            distinct(
                _base(behavioral_claim_text="the row is re-enqueued before the commit so a retry processes the payment twice"),
                _base(behavioral_claim_text="the row is re-enqueued before the commit so the customer is double-charged on retry"),
            ),
            _reword_reunify_predicate(),
        ),
    )
    add(
        "adversarial/weak-degenerate-descriptor-construct-only",
        "adversarial",
        "stable-identity §7 — a classified `construct` alone is still a weak discriminator",
        non_matchable(
            dict(
                repository="r",
                location="a/b.py:1",
                anchor_fragment="x = 1",
                construct="statement",
            )
        ),
    )

    # -- Ambiguity / fail-closed (stable-identity §7, requirements §6/§7) ---

    add(
        "failclosed/source-less-finding",
        "ambiguity",
        "stable-identity §7 — no anchor and no mechanism fragment",
        all_of(
            non_matchable(
                dict(
                    repository="r",
                    location="repository",
                    behavioral_claim_text="the architecture is unclear",
                    anchor_fragment=None,
                    mechanism_fragment=None,
                )
            ),
            minted_shape(
                dict(
                    repository="r",
                    location="repository",
                    behavioral_claim_text="the architecture is unclear",
                    anchor_fragment=None,
                    mechanism_fragment=None,
                )
            ),
        ),
    )
    add(
        "failclosed/repo-path-anchor-only",
        "ambiguity",
        "stable-identity §7 — discrimination reduces to repository / path / anchor_tokens",
        non_matchable(
            dict(
                repository="github.com/acme/app",
                location="src/api/users.py:120",
                anchor_fragment="row = db.execute(q)",
                behavioral_claim_text="untrusted input reaches sql",  # no cause->behavior connective
            )
        ),
    )
    add(
        "failclosed/unresolvable-repository",
        "ambiguity",
        "stable-identity §7 — repository identity missing",
        non_matchable(_base(repository="")),
    )
    add(
        "failclosed/unclassifiable-location-intent",
        "ambiguity",
        "stable-identity §7 — location matches none of the five intents",
        non_matchable(_base(location="somewhere in the payments area")),
    )
    add(
        "failclosed/still-minted-when-non-matchable",
        "ambiguity",
        "stable-identity §7 — a non-matchable finding still gets a deterministic id",
        minted_shape(
            dict(
                repository="github.com/acme/app",
                location="src/api/users.py:120",
                anchor_fragment="row = db.execute(q)",
            )
        ),
    )
    add(
        "failclosed/two-degenerate-distinct-findings-do-not-merge",
        "ambiguity",
        "requirements §6 — two distinct findings on one snippet with no classified "
        "discriminator are both non-matchable, so neither inherits the other",
        _degenerate_no_merge_predicate(),
    )

    # -- Hand-off with #59 (stable-identity §6.4) -- the only matching edge -

    add(
        "handoff/match-propagates-prior-identity",
        "handoff",
        "stable-identity §6.4 — #59 MATCH -> established prior identity, unchanged",
        propagates_prior(_base(symbol="pay.retry.RetryHandler.retry")),  # moved/renamed symbol
    )
    add(
        "handoff/reopen-reuses-original-identity",
        "handoff",
        "requirements §2 — a regressed (reopened) defect reuses the original identity",
        propagates_prior(_base()),
    )
    add(
        "handoff/no-match-mints-fresh",
        "handoff",
        "stable-identity §6.4 — #59 NO MATCH arrives as matched_prior_identity=None",
        mints_fresh_on_no_match(_base()),
    )
    add(
        "handoff/ambiguous-never-inherits",
        "handoff",
        "requirements §7 / stable-identity §6.4 — AMBIGUOUS is modelled as None and mints fresh",
        lambda im: (
            im.effective(im.build(**_base()))
            == im.mint(im.build(**_base()))
            != _PRIOR
        ),
    )
    add(
        "handoff/fail-closed-cannot-be-bypassed",
        "handoff",
        "stable-identity §6.4 / §7 — a non-matchable descriptor mints fresh even when "
        "a prior identity is offered",
        mints_fresh_despite_prior(
            dict(repository="r", location="a/b.py:1", anchor_fragment="x = 1")
        ),
    )

    return S


def _order_independent_predicate() -> Predicate:
    target = _base(symbol="pay.retry.RetryHandler.run", location="src/pay/retry.py:88")
    others = [
        _base(symbol=f"pay.mod{i}.Handler.run", location=f"src/pay/m{i}.py:{i}")
        for i in range(20)
    ]

    def check(im: Impl) -> bool:
        alone = im.mint(im.build(**target))
        crowd_ids = [im.mint(im.build(**o)) for o in others]
        after = im.mint(im.build(**target))
        return alone == after and alone not in crowd_ids

    return check


def _reword_reunify_predicate() -> Predicate:
    a = _base(behavioral_claim_text="the row is re-enqueued before the commit so a retry processes the payment twice")
    b = _base(behavioral_claim_text="the row is re-enqueued before the commit so the customer is double-charged on retry")

    def check(im: Impl) -> bool:
        prior = im.mint(im.build(**a))
        # A definite #59 MATCH re-propagates the prior identity for the reworded finding.
        return im.effective(im.build(**b), matched_prior_identity=prior) == prior

    return check


def _degenerate_no_merge_predicate() -> Predicate:
    common = dict(
        repository="github.com/acme/app",
        location="src/api/users.py:120",
        anchor_fragment="row = db.execute(q)",
    )
    a = dict(common, behavioral_claim_text="reason one")
    b = dict(common, behavioral_claim_text="reason two")

    def check(im: Impl) -> bool:
        da, db_ = im.build(**a), im.build(**b)
        if im.is_matchable(da) or im.is_matchable(db_):
            return False
        # Neither can adopt the other's identity through the hand-off.
        return im.effective(da, matched_prior_identity=im.mint(db_)) == im.mint(da)

    return check


SCENARIOS = _scenarios()


# ---------------------------------------------------------------------------
# 1. The real reference model must satisfy every scenario.
# ---------------------------------------------------------------------------


class FindingIdentityRegressionTests(unittest.TestCase):
    def test_every_scenario_holds_for_the_reference_model(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario.id):
                self.assertTrue(
                    scenario.predicate(REAL),
                    f"{scenario.id} failed ({scenario.requirement})",
                )

    def test_corpus_covers_every_requirement_group(self) -> None:
        groups = {s.group for s in SCENARIOS}
        self.assertEqual(
            groups,
            {"stability", "separation", "adversarial", "ambiguity", "handoff"},
        )

    def test_scenario_ids_are_unique(self) -> None:
        ids = [s.id for s in SCENARIOS]
        self.assertEqual(sorted(ids), sorted(set(ids)))

    def test_corpus_is_substantive(self) -> None:
        # Guard against the corpus being silently gutted.
        self.assertGreaterEqual(len(SCENARIOS), 30)
        for group, floor in (
            ("stability", 8),
            ("separation", 6),
            ("adversarial", 8),
            ("ambiguity", 5),
            ("handoff", 4),
        ):
            self.assertGreaterEqual(
                sum(1 for s in SCENARIOS if s.group == group), floor, group
            )


# ---------------------------------------------------------------------------
# 2. Induced-regression / mutation check: a representative identity bug must
#    make the corpus fail.
# ---------------------------------------------------------------------------


def _mut_mint_drops_semantic_keys(im: Impl) -> Impl:
    """Bug: cause_key / behavior_key are left out of the minted digest — two
    materially distinct defects on one snippet then silently merge."""

    def mint(descriptor: object) -> str:
        return im.mint(
            dataclasses.replace(descriptor, cause_key=fi.ABSENT, behavior_key=fi.ABSENT)
        )

    return im._replace(mint=mint)


def _mut_mint_hashes_occurrence_context(im: Impl) -> Impl:
    """Bug: occurrence context is folded into the digest — identity now breaks
    on line movement and nearby edits."""

    def mint(descriptor: object) -> str:
        extra = (
            fi._encode(descriptor.context_tokens)
            + fi._encode(descriptor.neighboring_syntax[0])
            + fi._encode(descriptor.neighboring_syntax[1])
        )
        blob = fi.canonical_serialization(descriptor) + "\x1e" + extra

        return "fid_v1_" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

    return im._replace(mint=mint)


def _mut_mint_hashes_defect_kind(im: Impl) -> Impl:
    """Bug: the free-form defect_kind slug is hashed — identity churns on
    reviewer phrasing."""

    def mint(descriptor: object) -> str:
        blob = fi.canonical_serialization(descriptor) + "\x1edefect_kind\x1d" + fi._encode(
            descriptor.defect_kind
        )

        return "fid_v1_" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

    return im._replace(mint=mint)


def _mut_build_sorts_anchor_tokens(im: Impl) -> Impl:
    """Bug: anchor tokens are sorted before hashing — operand order and
    negation position are lost."""

    def build(**kwargs: object) -> object:
        d = im.build(**kwargs)
        return dataclasses.replace(d, anchor_tokens=tuple(sorted(d.anchor_tokens)))

    return im._replace(build=build)


def _mut_build_strips_leading_negation(im: Impl) -> Impl:
    """Bug: a leading `!` token is stripped from the behavioral keys — a defect
    and its logical opposite collapse to one identity."""

    def _strip(value: object) -> object:
        if isinstance(value, tuple) and value and value[0] == "!":
            return value[1:]
        return value

    def build(**kwargs: object) -> object:
        d = im.build(**kwargs)
        return dataclasses.replace(
            d,
            cause_key=_strip(d.cause_key),
            behavior_key=_strip(d.behavior_key),
        )

    return im._replace(build=build)


def _mut_effective_skips_fail_closed_gate(im: Impl) -> Impl:
    """Bug: the hand-off propagates a prior identity without checking that the
    current descriptor is eligible for automatic matching."""

    def effective(descriptor: object, *, matched_prior_identity: object = None) -> str:
        if matched_prior_identity is not None:
            return matched_prior_identity
        return im.mint(descriptor)

    return im._replace(effective=effective)


MUTANTS = {
    "mint-drops-semantic-keys": _mut_mint_drops_semantic_keys,
    "mint-hashes-occurrence-context": _mut_mint_hashes_occurrence_context,
    "mint-hashes-defect-kind": _mut_mint_hashes_defect_kind,
    "build-sorts-anchor-tokens": _mut_build_sorts_anchor_tokens,
    "build-strips-leading-negation": _mut_build_strips_leading_negation,
    "effective-skips-fail-closed-gate": _mut_effective_skips_fail_closed_gate,
}


class InducedRegressionTests(unittest.TestCase):
    """Every representative identity bug must be caught by >= 1 scenario."""

    def test_each_mutant_is_caught_by_the_corpus(self) -> None:
        for name, mutate in MUTANTS.items():
            with self.subTest(mutant=name):
                mutant_impl = mutate(REAL)
                failing = [
                    s.id
                    for s in SCENARIOS
                    if not _safe_predicate(s.predicate, mutant_impl)
                ]
                self.assertTrue(
                    failing,
                    f"mutant {name!r} slipped past the entire regression corpus",
                )

    def test_each_mutant_actually_perturbs_an_identity_value(self) -> None:
        # Guards the check above from being vacuous: a mutant that changed no
        # observable identity/eligibility value could never be "caught". Each
        # mutant must move a real output on at least one probe finding.
        probes = [
            _base(),
            _base(anchor_fragment="a and not b"),
            _base(behavioral_claim_text="the guard runs so !authorized paths execute"),
            _base(defect_kind_text="no null-check!"),
            dict(repository="r", location="a/b.py:1", anchor_fragment="x = 1"),
        ]
        for name, mutate in MUTANTS.items():
            with self.subTest(mutant=name):
                mi = mutate(REAL)
                moved = False
                for kw in probes:
                    real_d, mut_d = REAL.build(**kw), mi.build(**kw)
                    if REAL.mint(real_d) != mi.mint(mut_d):
                        moved = True
                    if REAL.is_matchable(real_d) != mi.is_matchable(mut_d):
                        moved = True
                    if REAL.effective(real_d, matched_prior_identity=_PRIOR) != mi.effective(
                        mut_d, matched_prior_identity=_PRIOR
                    ):
                        moved = True
                self.assertTrue(moved, f"mutant {name!r} is a no-op — the catch is vacuous")

    def test_real_impl_is_not_reported_as_regressed(self) -> None:
        failing = [s.id for s in SCENARIOS if not _safe_predicate(s.predicate, REAL)]
        self.assertEqual(failing, [])


def _safe_predicate(predicate: Predicate, impl: Impl) -> bool:
    """A mutant may raise instead of returning False (e.g. a shape change). A
    raised exception is still the corpus catching the regression."""
    try:
        return bool(predicate(impl))
    except Exception:
        return False


if __name__ == "__main__":
    unittest.main()
