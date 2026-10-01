"""Lifecycle proof driver against a stateful fake; never touches the network."""

from __future__ import annotations

import copy
import json
import unittest

from scripts.github_integration import boundary as b
from scripts.github_integration import lifecycle_proof as lp
from tests.unit.github_integration.test_required_check_setup import FakeGitHub

REPO = "someone/review-disposable-proof"
SHA_A, SHA_B = "a" * 40, "b" * 40


class LifecycleFake(FakeGitHub):
    """Adds pulls, commit statuses, and merge-state derived from required contexts."""

    def __init__(self):
        super().__init__()
        self.head = SHA_A
        self.statuses: dict[str, dict[str, str]] = {}
        self.next_id = 1

    def required(self) -> set[str]:
        found = set()
        for r in self.rulesets.values():
            for rule in r["rules"]:
                if rule["type"] == "required_status_checks":
                    found |= {c["context"] for c in rule["parameters"]["required_status_checks"]}
        if self.protection:
            found |= set(self.protection["required_status_checks"]["contexts"])
        return found

    def advance(self, repo, branch):
        self.head = SHA_B
        return SHA_B

    def __call__(self, args, env, stdin):
        method, endpoint = args[1], args[2]
        body = json.loads(stdin) if stdin else None
        ok = lambda data: b.RawResponse(200, json.dumps(data))
        if endpoint.endswith("/pulls/9"):
            clean = all(self.statuses.get(self.head, {}).get(c) == "success" for c in self.required())
            return ok({"base": {"ref": "main"}, "head": {"sha": self.head, "ref": "topic"},
                       "mergeable_state": "clean" if clean else "blocked"})
        if "/statuses/" in endpoint:
            self.statuses.setdefault(endpoint.rsplit("/", 1)[1], {})[body["context"]] = body["state"]
            return ok({})
        if "/commits/" in endpoint and "/status" in endpoint:
            sha = endpoint.split("/commits/")[1].split("/")[0]
            return ok({"statuses": [{"context": c, "state": s}
                                    for c, s in self.statuses.get(sha, {}).items()]})
        if method != "GET" and (endpoint.endswith("/rulesets") or "/statuses/" in endpoint
                                or endpoint.endswith("/protection")):
            self.calls.append((method, endpoint, body))
        if method == "POST" and endpoint.endswith("/rulesets"):
            rid = self.next_id
            self.next_id += 1
            self.rulesets[rid] = {"id": rid, "bypass_actors": [], **copy.deepcopy(body)}
            return ok(self.rulesets[rid])
        if method == "PUT" and endpoint.endswith("/protection"):
            checks = [c["context"] for c in body["required_status_checks"]["checks"]]
            self.protection = {
                **body, "url": "u",
                "required_status_checks": {
                    "strict": False, "contexts": checks,
                    "checks": [{"context": c, "app_id": -1} for c in checks]},
            }
            return ok(self.protection)
        return super().__call__(args, env, stdin)


def run(mechanism, fake=None):
    fake = fake or LifecycleFake()
    client = b.GitHubClient(transport=fake, env={})
    steps = lp.run_lifecycle(client, REPO, 9, mechanism, sleep=lambda s: None,
                             advance_head=fake.advance, env={})
    return fake, steps


class LifecycleTests(unittest.TestCase):
    def test_every_point_passes_for_both_mechanisms(self):
        for mechanism in lp.MECHANISMS:
            with self.subTest(mechanism):
                _, steps = run(mechanism)
                self.assertGreaterEqual(len(steps), 15)
                self.assertEqual([s.point for s in steps if not s.passed], [])

    def test_unauthorized_setup_does_not_mutate(self):
        fake, _ = run("ruleset")
        unauthorized = [c for c in fake.calls if c[0] != "GET" and "/statuses/" not in c[1]]
        # fixture seed POST + authorized add PUT + authorized remove PUT only
        self.assertEqual([c[0] for c in unauthorized], ["POST", "PUT", "PUT"])

    def test_failed_point_is_reported_as_fail(self):
        fake = LifecycleFake()
        original = fake.required
        fake.required = lambda: set()  # merge never blocked -> blocking points must FAIL
        _, steps = run("classic", fake)
        self.assertTrue(any(not s.passed for s in steps))
        fake.required = original


class GuardTests(unittest.TestCase):
    def test_refuses_ci(self):
        for var in lp.CI_ENV_VARS:
            with self.assertRaises(lp.GuardError):
                lp.guard(REPO, {var: "true"})

    def test_refuses_canonical_and_undisposable_repos(self):
        for repo in (lp.CANONICAL_REPO, "someone/real-product"):
            with self.assertRaises(lp.GuardError):
                lp.guard(repo, {})
        lp.guard(REPO, {})

    def test_main_requires_confirmation(self):
        self.assertEqual(lp.main([REPO, "9", "--mechanism", "ruleset"]), 2)


class SanitizeTests(unittest.TestCase):
    def test_strips_tokens_repo_and_full_shas(self):
        token = "ghp_" + "A" * 36
        text = f"{token} abc-secret-value {REPO} {SHA_A}"
        out = lp.sanitize(text, {"GH_TOKEN": "abc-secret-value"}, REPO)
        self.assertNotIn(token, out)
        self.assertNotIn("abc-secret-value", out)
        self.assertNotIn(REPO, out)
        self.assertIn("aaaaaaa", out)
        self.assertNotIn(SHA_A, out)

    def test_render_evidence_is_sanitized(self):
        steps = [lp.Step("p", "x", f"github_pat_{'B' * 30} {SHA_A}", False)]
        out = lp.render_evidence(steps, "ruleset", {}, REPO)
        self.assertNotIn("github_pat_", out)
        self.assertIn("FAIL", out)


if __name__ == "__main__":
    unittest.main()
