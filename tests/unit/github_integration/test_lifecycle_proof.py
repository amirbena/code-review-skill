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
        if method == "DELETE" and (endpoint.endswith("/protection") or "/rulesets/" in endpoint):
            self.calls.append((method, endpoint, body))
            if endpoint.endswith("/protection"):
                self.protection = None
            else:
                self.rulesets.pop(int(endpoint.rsplit("/", 1)[1]))
            return b.RawResponse(204, "")
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
        # fixture seed POST + authorized add PUT + authorized remove PUT + teardown DELETE only
        self.assertEqual([c[0] for c in unauthorized], ["POST", "PUT", "PUT", "DELETE"])

    def test_teardown_leaves_no_governance(self):
        for mechanism in lp.MECHANISMS:
            fake, steps = run(mechanism)
            self.assertFalse(fake.rulesets)
            self.assertIsNone(fake.protection)
            self.assertEqual(steps[-1].point, "Teardown: seeded governance removed")

    def test_new_head_publishes_only_on_its_own_authorized_review(self):
        fake, steps = run("ruleset")
        by_point = {s.point: s for s in steps}
        self.assertTrue(by_point["New HEAD's own authorized review publishes success"].passed)
        self.assertTrue(by_point["New HEAD inherits no authorization (success withheld)"].passed)
        self.assertEqual(fake.statuses[SHA_A][lp.DEFAULT_CONTEXT], "success")
        self.assertTrue(by_point["New HEAD satisfied by its own review"].passed)

    def test_teardown_failure_is_recorded_and_does_not_mask_the_original_error(self):
        fake = LifecycleFake()
        boom = lambda repo, branch: (_ for _ in ()).throw(b.GitHubCallError("push failed", 500))
        steps: list[lp.Step] = []
        client = b.GitHubClient(transport=fake, env={})
        real = lp.teardown_governance
        lp.teardown_governance = lambda *a, **k: (_ for _ in ()).throw(KeyError("base"))
        try:
            with self.assertRaises(b.GitHubCallError):
                lp.run_lifecycle(client, REPO, 9, "ruleset", sleep=lambda s: None,
                                 advance_head=boom, env={}, steps=steps)
        finally:
            lp.teardown_governance = real
        self.assertFalse(steps[-1].passed)
        self.assertIn("remove it by hand", steps[-1].observed)

    def test_failure_midway_keeps_partial_evidence_and_tears_down(self):
        fake = LifecycleFake()
        boom = lambda repo, branch: (_ for _ in ()).throw(b.GitHubCallError("push failed", 500))
        steps: list[lp.Step] = []
        client = b.GitHubClient(transport=fake, env={})
        with self.assertRaises(b.GitHubCallError):
            lp.run_lifecycle(client, REPO, 9, "classic", sleep=lambda s: None,
                             advance_head=boom, env={}, steps=steps)
        self.assertGreater(len(steps), 8)
        self.assertEqual(steps[-1].point, "Teardown: seeded governance removed")
        self.assertIsNone(fake.protection)

    def test_failed_point_is_reported_as_fail(self):
        fake = LifecycleFake()
        fake.required = lambda: set()  # merge never blocked -> blocking points must FAIL
        _, steps = run("classic", fake)
        self.assertTrue(any(not s.passed for s in steps))


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
