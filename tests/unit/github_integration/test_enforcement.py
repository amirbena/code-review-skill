"""Enforcement detection against a mocked boundary transport."""

from __future__ import annotations

import json
import unittest

from scripts.github_integration import boundary as b
from scripts.github_integration import enforcement as e

CTX = "code-review/github-pr-review"
UNPROTECTED = b.RawResponse(404, '{"message": "Branch not protected"}')


def ruleset(*contexts, other=()):
    rules = [{"type": "deletion"}]
    if contexts or other:
        checks = [{"context": c} for c in (*contexts, *other)]
        rules.append(
            {"type": "required_status_checks", "parameters": {"required_status_checks": checks}}
        )
    return b.RawResponse(200, json.dumps(rules))


def classic(*contexts):
    return b.RawResponse(
        200, json.dumps({"checks": [{"context": c, "app_id": -1} for c in contexts]})
    )


class Router:
    """Routes by endpoint and records every transport call."""

    def __init__(self, rules, protection):
        self.rules, self.protection, self.calls = rules, protection, []

    def __call__(self, args, env, stdin):
        self.calls.append((list(args), stdin))
        return self.rules if "/rules/branches/" in args[-1] else self.protection


def detect(rules, protection):
    router = Router(rules, protection)
    client = b.GitHubClient(router, {"GH_TOKEN": "tok-secret-123"})
    return e.detect_enforcement(client, "o/r", "main", CTX), router


class StateTests(unittest.TestCase):
    def test_ruleset_only(self):
        r, _ = detect(ruleset(CTX), UNPROTECTED)
        self.assertEqual((r.state, r.governing), (e.ENFORCED, "ruleset"))
        self.assertEqual(r.classic.state, e.NOT_ENFORCED)

    def test_classic_only(self):
        r, _ = detect(ruleset(), classic(CTX))
        self.assertEqual((r.state, r.governing), (e.ENFORCED, "classic"))
        self.assertEqual(r.ruleset.state, e.NOT_ENFORCED)

    def test_both(self):
        r, _ = detect(ruleset(CTX), classic(CTX))
        self.assertEqual((r.state, r.governing), (e.ENFORCED, "both"))

    def test_neither_readable(self):
        r, _ = detect(ruleset(other=["test"]), classic("test"))
        self.assertEqual((r.state, r.governing), (e.NOT_ENFORCED, "none"))

    def test_legacy_contexts_list(self):
        legacy = b.RawResponse(200, json.dumps({"contexts": [CTX]}))
        r, _ = detect(ruleset(), legacy)
        self.assertEqual(r.state, e.ENFORCED)


class UnknownTests(unittest.TestCase):
    def test_unreadable_ruleset_with_absent_classic_is_unknown(self):
        r, _ = detect(b.RawResponse(403, "no"), UNPROTECTED)
        self.assertEqual((r.state, r.governing), (e.UNKNOWN, "undetermined"))

    def test_unreadable_classic_with_absent_ruleset_is_unknown(self):
        r, _ = detect(ruleset(), b.RawResponse(403, '{"message": "Resource not accessible"}'))
        self.assertEqual(r.state, e.UNKNOWN)

    def test_classic_404_other_than_unprotected_is_unknown(self):
        r, _ = detect(ruleset(), b.RawResponse(404, '{"message": "Not Found"}'))
        self.assertEqual(r.classic.state, e.UNKNOWN)
        self.assertEqual(r.state, e.UNKNOWN)

    def test_protection_without_required_checks_is_not_enforced(self):
        resp = b.RawResponse(404, '{"message": "Required status checks not enabled"}')
        r, _ = detect(ruleset(), resp)
        self.assertEqual((r.classic.state, r.state), (e.NOT_ENFORCED, e.NOT_ENFORCED))

    def test_both_unreadable(self):
        r, _ = detect(b.RawResponse(500, "x"), b.RawResponse(0, "gh missing"))
        self.assertEqual(r.state, e.UNKNOWN)

    def test_unexpected_shapes_are_unknown(self):
        r, _ = detect(b.RawResponse(200, '{"a": 1}'), b.RawResponse(200, "[]"))
        self.assertEqual(r.state, e.UNKNOWN)

    def test_possibly_truncated_rules_page_is_unknown(self):
        page = json.dumps([{"type": "deletion"}] * e.PAGE_SIZE)
        r, _ = detect(b.RawResponse(200, page), UNPROTECTED)
        self.assertEqual(r.ruleset.state, e.UNKNOWN)
        self.assertEqual(r.state, e.UNKNOWN)

    def test_enforced_survives_other_mechanism_unreadable(self):
        r, _ = detect(ruleset(CTX), b.RawResponse(403, "no"))
        self.assertEqual((r.state, r.governing), (e.ENFORCED, "ruleset"))
        self.assertEqual(r.classic.state, e.UNKNOWN)

    def test_published_status_is_never_consulted(self):
        _, router = detect(ruleset(), UNPROTECTED)
        self.assertFalse(any("statuses" in c[0][-1] for c in router.calls))


class ReadOnlyTests(unittest.TestCase):
    SHAPES = [
        (ruleset(CTX), UNPROTECTED),
        (ruleset(), classic(CTX)),
        (ruleset(CTX), classic(CTX)),
        (ruleset(), UNPROTECTED),
        (b.RawResponse(403, "no"), b.RawResponse(500, "x")),
    ]

    def test_only_get_without_payload_in_every_outcome(self):
        for rules, protection in self.SHAPES:
            _, router = detect(rules, protection)
            self.assertTrue(router.calls)
            for args, stdin in router.calls:
                self.assertEqual(args[:2], ["-X", "GET"])
                self.assertNotIn("--input", args)
                self.assertIsNone(stdin)

    def test_missing_enforcement_never_triggers_mutation(self):
        class Spy(b.GitHubClient):
            mutations = 0

            def write(self, *a, **k):
                Spy.mutations += 1

            def mutate_governance(self, *a, **k):
                Spy.mutations += 1

        client = Spy(Router(ruleset(), UNPROTECTED), {})
        self.assertEqual(e.detect_enforcement(client, "o/r", "main", CTX).state, e.NOT_ENFORCED)
        self.assertEqual(Spy.mutations, 0)

    def test_detector_runs_against_a_read_only_object(self):
        class OnlyRead:
            def read(self, endpoint):
                return [] if "/rules/" in endpoint else {"checks": []}

        self.assertEqual(e.detect_enforcement(OnlyRead(), "o/r", "main", CTX).state, e.NOT_ENFORCED)


if __name__ == "__main__":
    unittest.main()
