"""Required-check setup/removal against a stateful mocked boundary transport."""

from __future__ import annotations

import copy
import json
import unittest

from scripts.github_integration import boundary as b
from scripts.github_integration import required_check_setup as s

CTX = "code-review/github-pr-review"
AUTH = b.GovernanceAuthorization(True, "set up the code-review status as a required check")


def make_ruleset(*contexts, rid=7):
    return {
        "id": rid,
        "name": "main protection",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}],
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [
            {"type": "deletion"},
            {"type": "pull_request", "parameters": {"required_approving_review_count": 2,
                                                    "dismiss_stale_reviews_on_push": True}},
            {"type": "required_status_checks",
             "parameters": {"strict_required_status_checks_policy": True,
                            "required_status_checks": [{"context": c} for c in contexts]}},
        ],
        "node_id": "x", "updated_at": "now",
    }


def make_protection(*contexts):
    return {
        "url": "u",
        "required_pull_request_reviews": {"required_approving_review_count": 2},
        "enforce_admins": {"enabled": True},
        "required_status_checks": {
            "strict": True,
            "checks": [{"context": c, "app_id": -1} for c in contexts],
            "contexts": list(contexts),
        },
    }


class FakeGitHub:
    """Stateful transport: PUT/POST/DELETE mutate the held configuration."""

    def __init__(self, rulesets=(), protection=None, perm_fail_write=False, readback_drift=False,
                 write_status=None, fail_reads_after_write=False, concurrent_edit=False,
                 classic_drift=False, org_source=False):
        self.write_status, self.fail_reads_after_write = write_status, fail_reads_after_write
        self.concurrent_edit, self.classic_drift, self.org_source = (
            concurrent_edit, classic_drift, org_source)
        self.wrote = False
        self.rulesets = {r["id"]: copy.deepcopy(r) for r in rulesets}
        self.protection = copy.deepcopy(protection)
        self.perm_fail_write, self.readback_drift = perm_fail_write, readback_drift
        self.calls = []

    def writes(self):
        return [c for c in self.calls if c[0] != "GET"]

    def __call__(self, args, env, stdin):
        method, endpoint = args[1], args[2]
        body = json.loads(stdin) if stdin else None
        self.calls.append((method, endpoint, body))
        ok = lambda data: b.RawResponse(200, json.dumps(data))
        if method == "GET" and self.wrote and self.fail_reads_after_write:
            return b.RawResponse(500, "boom")
        if method != "GET" and self.write_status:
            self.wrote = True
            return b.RawResponse(self.write_status, "boom")
        if method != "GET":
            self.wrote = True
        if method != "GET" and self.perm_fail_write:
            return b.RawResponse(403, '{"message": "Resource not accessible by integration"}')
        if "/rules/branches/" in endpoint:
            rules = []
            for r in self.rulesets.values():
                if r["enforcement"] != "active":
                    continue
                for rule in r["rules"]:
                    source = "Organization" if self.org_source else "Repository"
                    rules.append({**rule, "ruleset_id": r["id"], "ruleset_source_type": source})
            return ok(rules)
        if "/rulesets/" in endpoint:
            rid = int(endpoint.rsplit("/", 1)[1])
            if method == "GET" and self.concurrent_edit and not self.wrote:
                self.concurrent_edit = False
                self.rulesets[rid]["bypass_actors"] = []
                return ok(make_ruleset("test"))
            if method == "PUT":
                self.rulesets[rid] = {**self.rulesets[rid], **body}
                if self.readback_drift:
                    self.rulesets[rid]["enforcement"] = "disabled"
            return ok(self.rulesets[rid])
        if endpoint.endswith("/required_status_checks"):
            if self.protection is None:
                return b.RawResponse(404, '{"message": "Branch not protected"}')
            return ok(self.protection["required_status_checks"])
        if endpoint.endswith("/required_status_checks/contexts"):
            rsc = self.protection["required_status_checks"]
            ctxs = [c["context"] for c in rsc["checks"]]
            ctxs = ctxs + body if method == "POST" else [c for c in ctxs if c not in body]
            rsc["checks"] = [{"context": c, "app_id": -1} for c in ctxs]
            rsc["contexts"] = ctxs
            if self.classic_drift:
                self.protection["enforce_admins"] = {"enabled": False}
            return ok(ctxs)
        if endpoint.endswith("/protection"):
            return ok(self.protection)
        return b.RawResponse(404, '{"message": "Not Found"}')


def run(fake, **kw):
    req = s.SetupRequest("o/r", "main", CTX, **{"active_mode": True, "reviewer_independent": True,
                                                "authorization": AUTH, **kw})
    return s.apply_required_check(b.GitHubClient(fake, {}), req)


class AuthorizationTests(unittest.TestCase):
    def test_no_authorization_means_no_calls_even_when_enforcement_missing(self):
        for auth in (None, b.GovernanceAuthorization(False, "x"), b.GovernanceAuthorization(True, " ")):
            fake = FakeGitHub([make_ruleset("test")])
            out = run(fake, authorization=auth)
            self.assertEqual(out.action, "refused")
            self.assertEqual(fake.calls, [])

    def test_34_gates_still_apply(self):
        for kw in ({"active_mode": False}, {"reviewer_independent": False}):
            fake = FakeGitHub([make_ruleset("test")])
            self.assertEqual(run(fake, **kw).action, "refused")
            self.assertEqual(fake.calls, [])


class RulesetTests(unittest.TestCase):
    def test_adds_only_the_context_and_preserves_everything_else(self):
        fake = FakeGitHub([make_ruleset("test")])
        before = copy.deepcopy(fake.rulesets[7])
        out = run(fake)
        self.assertEqual((out.action, out.mechanism), ("added", "ruleset"))
        expected = copy.deepcopy(before)
        expected["rules"][2]["parameters"]["required_status_checks"].append({"context": CTX})
        self.assertEqual(fake.rulesets[7], expected)
        self.assertEqual([w[0] for w in fake.writes()], ["PUT"])

    def test_rerun_is_noop(self):
        fake = FakeGitHub([make_ruleset("test")])
        run(fake)
        fake.calls.clear()
        self.assertEqual(run(fake).action, "noop")
        self.assertEqual(fake.writes(), [])

    def test_removal_restores_prior_set(self):
        fake = FakeGitHub([make_ruleset("test")])
        before = copy.deepcopy(fake.rulesets[7])
        run(fake)
        out = run(fake, remove=True)
        self.assertEqual(out.action, "removed")
        self.assertEqual(fake.rulesets[7], before)
        self.assertEqual(run(fake, remove=True).action, "noop")

    def test_removal_never_empties_the_rule(self):
        fake = FakeGitHub([make_ruleset(CTX)])
        self.assertEqual(run(fake, remove=True).action, "refused")
        self.assertEqual(fake.writes(), [])

    def test_readback_drift_is_reported_failed(self):
        out = run(FakeGitHub([make_ruleset("test")], readback_drift=True))
        self.assertEqual(out.action, "failed")
        self.assertIsNotNone(out.before)


class ClassicTests(unittest.TestCase):
    def test_additive_contexts_call_preserves_protection(self):
        fake = FakeGitHub(protection=make_protection("test"))
        before = copy.deepcopy(fake.protection)
        out = run(fake)
        self.assertEqual((out.action, out.mechanism), ("added", "classic"))
        self.assertEqual(fake.writes()[0][:3], ("POST", "repos/o/r/branches/main/protection/required_status_checks/contexts", [CTX]))
        self.assertEqual(len(fake.writes()), 1)
        fake.protection["required_status_checks"]["checks"].pop()
        fake.protection["required_status_checks"]["contexts"].pop()
        self.assertEqual(fake.protection, before)

    def test_rerun_noop_and_removal_restores(self):
        fake = FakeGitHub(protection=make_protection("test"))
        before = copy.deepcopy(fake.protection)
        run(fake)
        self.assertEqual(run(fake).action, "noop")
        self.assertEqual(run(fake, remove=True).action, "removed")
        self.assertEqual(fake.protection, before)
        self.assertEqual(run(fake, remove=True).action, "noop")


class UnverifiedWriteTests(unittest.TestCase):
    def assert_unverified(self, out):
        self.assertEqual(out.action, "failed")
        self.assertNotIn("No change was applied", out.message)
        self.assertIn("could not be verified", out.message)
        self.assertIsNotNone(out.before)

    def test_readback_failure_is_not_reported_as_unchanged(self):
        for kw in ({"rulesets": [make_ruleset("test")]}, {"protection": make_protection("test")}):
            self.assert_unverified(run(FakeGitHub(fail_reads_after_write=True, **kw)))

    def test_ambiguous_write_failure_is_not_reported_as_unchanged(self):
        for kw in ({"rulesets": [make_ruleset("test")]}, {"protection": make_protection("test")}):
            self.assert_unverified(run(FakeGitHub(write_status=502, **kw)))

    def test_rejected_write_is_reported_unchanged(self):
        out = run(FakeGitHub([make_ruleset("test")], write_status=422))
        self.assertEqual(out.action, "failed")
        self.assertIn("No change was applied", out.message)

    def test_classic_readback_drift_is_failed(self):
        out = run(FakeGitHub(protection=make_protection("test"), classic_drift=True))
        self.assertEqual(out.action, "failed")
        self.assertIsNotNone(out.before)

    def test_concurrent_ruleset_change_refuses_before_writing(self):
        fake = FakeGitHub([make_ruleset("test")], concurrent_edit=True)
        self.assertEqual(run(fake).action, "refused")
        self.assertEqual(fake.writes(), [])


class FailSafeTests(unittest.TestCase):
    def test_organization_only_ruleset_refuses(self):
        fake = FakeGitHub([make_ruleset("test")], org_source=True)
        self.assertEqual(run(fake).action, "refused")
        self.assertEqual(fake.writes(), [])

    def test_inactive_ruleset_is_not_edited(self):
        inactive = {**make_ruleset("test"), "enforcement": "disabled"}
        fake = FakeGitHub([inactive])
        self.assertEqual(run(fake).action, "refused")
        self.assertEqual(fake.writes(), [])

    def test_permission_failure_on_write_changes_nothing(self):
        for fake in (FakeGitHub([make_ruleset("test")], perm_fail_write=True),
                     FakeGitHub(protection=make_protection("test"), perm_fail_write=True)):
            before = (copy.deepcopy(fake.rulesets), copy.deepcopy(fake.protection))
            self.assertEqual(run(fake).action, "failed")
            self.assertEqual((fake.rulesets, fake.protection), before)

    def test_unreadable_governance_fails_without_mutation(self):
        class Unreadable(FakeGitHub):
            def __call__(self, args, env, stdin):
                super().__call__(args, env, stdin)
                return b.RawResponse(403, '{"message": "no"}')

        fake = Unreadable([make_ruleset("test")])
        self.assertEqual(run(fake).action, "failed")
        self.assertEqual(fake.writes(), [])

    def test_both_mechanisms_conflict_refuses(self):
        fake = FakeGitHub([make_ruleset("test")], make_protection("test"))
        self.assertEqual(run(fake).action, "refused")
        self.assertEqual(fake.writes(), [])

    def test_two_rulesets_with_checks_refuse(self):
        fake = FakeGitHub([make_ruleset("a", rid=1), make_ruleset("b", rid=2)])
        self.assertEqual(run(fake).action, "refused")
        self.assertEqual(fake.writes(), [])

    def test_never_creates_a_mechanism_unprompted(self):
        fake = FakeGitHub(protection=None)
        self.assertEqual(run(fake).action, "refused")
        self.assertEqual(fake.writes(), [])

    def test_only_governance_writes_are_ruleset_put_or_contexts_call(self):
        for fake in (FakeGitHub([make_ruleset("t")]), FakeGitHub(protection=make_protection("t"))):
            run(fake)
            run(fake, remove=True)
            for method, endpoint, _ in fake.writes():
                self.assertIn(method, {"PUT", "POST", "DELETE"})
                self.assertTrue("/rulesets/7" in endpoint or endpoint.endswith("/contexts"))


if __name__ == "__main__":
    unittest.main()
