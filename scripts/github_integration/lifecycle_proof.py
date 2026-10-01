"""Manual end-to-end proof of GitHub merge enforcement on a disposable repository.

Operator-run only: it mutates governance on the repository it is pointed at and refuses to
run under CI, against the canonical repository, or against a repository that is not named as
disposable. It adds no behavior; it drives the existing publisher, detector, and setup.
"""

from __future__ import annotations

import argparse
import copy
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.parse import quote

from scripts.github_integration.boundary import (
    GitHubBoundaryError,
    GitHubClient,
    GovernanceAuthorization,
    TOKEN_ENV_VARS,
)
from scripts.github_integration.enforcement import (
    DEFAULT_CONTEXT,
    ENFORCED,
    NOT_ENFORCED,
    detect_enforcement,
)
from scripts.github_integration.required_check_setup import (
    RULE_TYPE,
    RULESET_WRITABLE,
    SetupRequest,
    apply_required_check,
)
from scripts.github_integration.status_publisher import PublishRequest, Reasoning, publish_status

CANONICAL_REPO = "amirbena/code-review-skill"
CI_ENV_VARS = ("CI", "GITHUB_ACTIONS")
UNRELATED_CONTEXT = "proof/unrelated"
DISPOSABLE_RE = re.compile(r"(^|[-_.])(disposable|sandbox|scratch)([-_.]|$)", re.IGNORECASE)
TOKEN_RE = re.compile(r"(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")
SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")
USER_REQUEST = "Set up the code-review status as a required check on the disposable repository."
MECHANISMS = ("ruleset", "classic")


@dataclass(frozen=True)
class Step:
    point: str
    expected: str
    observed: str
    passed: bool


class GuardError(Exception):
    pass


def guard(repo: str, env: Mapping[str, str]) -> None:
    """Refuse CI, the canonical repository, and any repository not named disposable."""
    if any(env.get(v) for v in CI_ENV_VARS):
        raise GuardError("Refused: this proof never runs under CI.")
    if repo.lower() == CANONICAL_REPO:
        raise GuardError("Refused: the canonical repository is never a proof target.")
    name = repo.split("/", 1)[-1]
    if not DISPOSABLE_RE.search(name):
        raise GuardError(
            "Refused: the repository name must contain `disposable`, `sandbox`, or `scratch`."
        )


def sanitize(text: str, env: Mapping[str, str] | None = None, repo: str = "") -> str:
    """Strip tokens, the repository slug, and full SHAs from evidence text."""
    for name in TOKEN_ENV_VARS:
        value = (env or {}).get(name)
        if value:
            text = text.replace(value, "<redacted>")
    text = TOKEN_RE.sub("<redacted>", text)
    if repo:
        text = text.replace(repo, "<disposable-repo>")
    return SHA_RE.sub(lambda m: m.group(0)[:7], text)


def strip_context(value: Any, context: str) -> Any:
    """Governance with the review context removed, to compare against the pre-setup state."""
    if isinstance(value, dict):
        return {k: strip_context(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [strip_context(v, context) for v in value
                if v != context and not (isinstance(v, dict) and v.get("context") == context)]
    return value


def _canon(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _canon(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return sorted((_canon(v) for v in value), key=repr)
    return value


def snapshot(client: GitHubClient, repo: str, branch: str, mechanism: str, rid: int | None) -> Any:
    if mechanism == "ruleset":
        data = client.read(f"repos/{repo}/rulesets/{rid}")
        return _canon({k: data[k] for k in RULESET_WRITABLE if k in data})
    return _canon(client.read(f"repos/{repo}/branches/{quote(branch, safe='/')}/protection"))


def seed_governance(client, repo, branch, mechanism, auth) -> int | None:
    """Pre-existing unrelated governance: one unrelated required check plus other rules."""
    if mechanism == "ruleset":
        created = client.mutate_governance("POST", f"repos/{repo}/rulesets", {
            "name": "proof-main", "target": "branch", "enforcement": "active",
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "rules": [
                {"type": "deletion"}, {"type": "non_fast_forward"},
                {"type": RULE_TYPE, "parameters": {
                    "strict_required_status_checks_policy": False,
                    "required_status_checks": [{"context": UNRELATED_CONTEXT}]}},
            ],
        }, authorization=auth)
        return created["id"]
    client.mutate_governance(
        "PUT", f"repos/{repo}/branches/{quote(branch, safe='/')}/protection",
        {"required_status_checks": {"strict": False, "checks": [{"context": UNRELATED_CONTEXT}]},
         "enforce_admins": True, "required_pull_request_reviews": None,
         "restrictions": None, "allow_deletions": False},
        authorization=auth,
    )
    return None


def merge_state(client, repo, pr, want: str, sleep, attempts: int = 12) -> str:
    """Poll `mergeable_state` (computed lazily by GitHub) until it equals `want` or time runs out."""
    state = "unknown"
    for _ in range(attempts):
        state = (client.read(f"repos/{repo}/pulls/{pr}") or {}).get("mergeable_state") or "unknown"
        if state == want:
            break
        sleep(2)
    return state


def review_status(client, repo, sha) -> str | None:
    combined = client.read(f"repos/{repo}/commits/{sha}/status?per_page=100") or {}
    for s in combined.get("statuses", []):
        if s.get("context") == DEFAULT_CONTEXT:
            return s.get("state")
    return None


def gh_advance_head(repo: str, branch: str, env: Mapping[str, str]) -> str:
    """Push one new commit to the PR branch through the contents API; return the new HEAD."""
    path = f"proof-{int(time.time())}.txt"
    out = subprocess.run(
        ["gh", "api", "-X", "PUT", f"repos/{repo}/contents/{path}", "-f", "message=advance HEAD",
         "-f", "content=cHJvb2Y=", "-f", f"branch={branch}", "--jq", ".commit.sha"],
        capture_output=True, text=True, env={**os.environ, **env}, check=False,
    )
    if out.returncode != 0:
        raise GuardError("Could not advance the PR HEAD; push a commit manually and re-run.")
    return out.stdout.strip()


def run_lifecycle(
    client: GitHubClient, repo: str, pr: int, mechanism: str, *,
    sleep: Callable[[float], None] = time.sleep,
    advance_head: Callable[[str, str], str] | None = None,
    env: Mapping[str, str] | None = None,
) -> list[Step]:
    env = os.environ if env is None else env
    advance_head = advance_head or (lambda r, b: gh_advance_head(r, b, env))
    pull = client.read(f"repos/{repo}/pulls/{pr}")
    branch, sha_a = pull["base"]["ref"], pull["head"]["sha"]
    head_branch = pull["head"]["ref"]
    auth = GovernanceAuthorization(True, USER_REQUEST)
    steps: list[Step] = []

    def record(point, expected, observed, passed=None):
        steps.append(Step(point, str(expected), str(observed),
                          (str(expected) == str(observed)) if passed is None else passed))

    def setup(**kw):
        return apply_required_check(client, SetupRequest(
            repo, branch, active_mode=True, reviewer_independent=True, **kw))

    def post_unrelated(sha):
        client.write("POST", f"repos/{repo}/statuses/{sha}",
                     {"state": "success", "context": UNRELATED_CONTEXT, "description": "unrelated"})

    def publish(reasoning, sha, **kw):
        return publish_status(client, PublishRequest(
            reasoning, repo, pr, sha, is_aggregator=True, **kw), sleep=sleep)

    rid = seed_governance(client, repo, branch, mechanism, auth)
    base = snapshot(client, repo, branch, mechanism, rid)
    record("Fixture: unrelated governance seeded", UNRELATED_CONTEXT in repr(base), True)
    record("Detection before setup", NOT_ENFORCED,
           detect_enforcement(client, repo, branch).state)

    refused = apply_required_check(client, SetupRequest(
        repo, branch, active_mode=True, reviewer_independent=True, authorization=None))
    record("Setup without explicit authorization refuses", "refused", refused.action)
    record("No mutation without authorization", "unchanged",
           "unchanged" if snapshot(client, repo, branch, mechanism, rid) == base else "CHANGED")

    added = setup(authorization=auth)
    record("Setup with explicit authorization", "added", added.action)
    after = snapshot(client, repo, branch, mechanism, rid)
    record("Detection after setup", ENFORCED, detect_enforcement(client, repo, branch).state)
    record("Unrelated governance intact after setup", "intact",
           "intact" if strip_context(after, DEFAULT_CONTEXT) == strip_context(base, DEFAULT_CONTEXT)
           else "CHANGED")

    post_unrelated(sha_a)
    publish(Reasoning.CHANGES_REQUIRED, sha_a)
    record("failure published on reviewed SHA", "failure", review_status(client, repo, sha_a))
    record("Required check blocks merge on failure", "blocked",
           merge_state(client, repo, pr, "blocked", sleep))

    publish(Reasoning.CLEAN, sha_a, active_mode=True, reviewer_independent=True)
    record("success published on reviewed SHA", "success", review_status(client, repo, sha_a))
    record("Required check satisfied on success", "clean",
           merge_state(client, repo, pr, "clean", sleep))

    sha_b = advance_head(repo, head_branch)
    post_unrelated(sha_b)
    record("New HEAD differs from prior SHA", True, sha_b != sha_a)
    record("New HEAD inherits no status", "None", review_status(client, repo, sha_b))
    record("New HEAD is merge-blocked", "blocked", merge_state(client, repo, pr, "blocked", sleep))
    withheld = publish(Reasoning.CLEAN, sha_b)
    record("New HEAD inherits no authorization (success withheld)", "withheld", withheld.action)
    record("New HEAD still has no status after withheld publish", "None",
           review_status(client, repo, sha_b))

    removed = setup(authorization=auth, remove=True)
    record("Removal with explicit authorization", "removed", removed.action)
    final = snapshot(client, repo, branch, mechanism, rid)
    record("Governance restored after removal", "restored",
           "restored" if final == base else "CHANGED")
    record("Detection after removal", NOT_ENFORCED, detect_enforcement(client, repo, branch).state)
    record("Merge no longer gated by the review context", "clean",
           merge_state(client, repo, pr, "clean", sleep))
    return steps


def render_evidence(steps: list[Step], mechanism: str, env=None, repo: str = "") -> str:
    lines = [f"### {mechanism.capitalize()} run", "",
             "| # | Lifecycle point | Expected | Observed | Result |", "| --- | --- | --- | --- | --- |"]
    for i, s in enumerate(steps, 1):
        lines.append(f"| {i} | {s.point} | `{s.expected}` | `{s.observed}` | "
                     f"{'PASS' if s.passed else 'FAIL'} |")
    return sanitize("\n".join(lines) + "\n", env, repo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="owner/name of the disposable repository")
    parser.add_argument("pr", type=int, help="open PR against the default branch, mergeable")
    parser.add_argument("--mechanism", choices=MECHANISMS, required=True)
    parser.add_argument("--confirm-disposable", action="store_true",
                        help="acknowledge that governance on REPO will be mutated")
    args = parser.parse_args(argv)
    try:
        guard(args.repo, os.environ)
        if not args.confirm_disposable:
            raise GuardError("Refused: pass --confirm-disposable to mutate governance on REPO.")
        steps = run_lifecycle(GitHubClient(), args.repo, args.pr, args.mechanism)
    except (GuardError, GitHubBoundaryError) as exc:
        print(sanitize(str(exc), os.environ, args.repo), file=sys.stderr)
        return 2
    print(render_evidence(steps, args.mechanism, os.environ, args.repo))
    return 0 if all(s.passed for s in steps) else 1


if __name__ == "__main__":
    sys.exit(main())
