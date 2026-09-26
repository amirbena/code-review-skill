"""Tests for the shared GitHub call boundary against a mocked transport."""

from __future__ import annotations

import json
import unittest

from scripts.github_integration import boundary as b


class Recorder:
    def __init__(self, *responses: b.RawResponse):
        self.responses = list(responses)
        self.calls: list[tuple] = []

    def __call__(self, args, env, stdin):
        self.calls.append((list(args), dict(env), stdin))
        return self.responses.pop(0)


def client(*responses, env=None):
    rec = Recorder(*responses)
    return b.GitHubClient(rec, env if env is not None else {"GH_TOKEN": "sekret"}), rec


AUTH = b.GovernanceAuthorization(True, "add review context as required check")


class ReadTests(unittest.TestCase):
    def test_read_returns_json_and_passes_token_via_env(self):
        c, rec = client(b.RawResponse(200, '{"a": 1}'))
        self.assertEqual(c.read("repos/o/r"), {"a": 1})
        self.assertEqual(rec.calls[0][1], {"GH_TOKEN": "sekret"})
        self.assertNotIn("sekret", " ".join(rec.calls[0][0]))

    def test_401_is_actionable(self):
        c, _ = client(b.RawResponse(401, "bad"))
        with self.assertRaisesRegex(b.AuthenticationError, "gh auth login"):
            c.read("user")

    def test_403_reports_needed_scopes_and_redacts_token(self):
        c, _ = client(
            b.RawResponse(403, "denied sekret", {"x-accepted-oauth-scopes": "repo"})
        )
        with self.assertRaises(b.GitHubPermissionError) as ctx:
            c.read("repos/o/r")
        self.assertIn("repo", str(ctx.exception))
        self.assertNotIn("sekret", str(ctx.exception))

    def test_unreachable_gh(self):
        c, _ = client(b.RawResponse(0, "no gh"))
        with self.assertRaises(b.GitHubCallError):
            c.read("user")


class PreflightTests(unittest.TestCase):
    def test_missing_scope_fails(self):
        c, _ = client(b.RawResponse(200, "{}", {"x-oauth-scopes": "read:org"}))
        with self.assertRaisesRegex(b.GitHubPermissionError, "repo:status"):
            c.preflight(["repo:status"])

    def test_fine_grained_token_without_scope_header_passes(self):
        c, _ = client(b.RawResponse(200, "{}", {}))
        c.preflight(["repo:status"])


class WriteTests(unittest.TestCase):
    def test_write_sends_payload_on_stdin(self):
        c, rec = client(b.RawResponse(201, "{}"))
        c.write("POST", "repos/o/r/statuses/abc", {"state": "success"})
        self.assertEqual(json.loads(rec.calls[0][2]), {"state": "success"})

    def test_write_refuses_governance_endpoints(self):
        for ep in (
            "repos/o/r/rulesets/1",
            "repos/o/r/branches/main/protection/required_status_checks",
        ):
            c, rec = client()
            with self.assertRaises(b.AuthorizationRequiredError):
                c.write("PUT", ep, {})
            self.assertEqual(rec.calls, [])

    def test_write_rejects_read_method(self):
        c, _ = client()
        with self.assertRaises(b.GitHubBoundaryError):
            c.write("GET", "user")


class GovernanceTests(unittest.TestCase):
    def test_refused_without_authorization(self):
        c, rec = client()
        with self.assertRaises(b.AuthorizationRequiredError):
            c.mutate_governance("PUT", "repos/o/r/rulesets/1", {}, authorization=None)
        self.assertEqual(rec.calls, [])

    def test_refused_with_invalid_authorization(self):
        c, rec = client()
        for auth in (
            b.GovernanceAuthorization(False, "x"),
            b.GovernanceAuthorization(True, "  "),
        ):
            with self.assertRaises(b.AuthorizationRequiredError):
                c.mutate_governance("PUT", "repos/o/r/rulesets/1", {}, authorization=auth)
        self.assertEqual(rec.calls, [])

    def test_authorization_is_keyword_only(self):
        c, _ = client()
        with self.assertRaises(TypeError):
            c.mutate_governance("PUT", "repos/o/r/rulesets/1", {}, AUTH)  # type: ignore[misc]

    def test_authorized_call_goes_through(self):
        c, rec = client(b.RawResponse(200, "{}"))
        c.mutate_governance("PUT", "repos/o/r/rulesets/1", {"a": 1}, authorization=AUTH)
        self.assertEqual(len(rec.calls), 1)

    def test_read_method_rejected(self):
        c, _ = client()
        with self.assertRaises(b.GitHubBoundaryError):
            c.mutate_governance("GET", "repos/o/r/rulesets", None, authorization=AUTH)


if __name__ == "__main__":
    unittest.main()
