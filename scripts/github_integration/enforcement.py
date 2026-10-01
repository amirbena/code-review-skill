"""Read-only detection of whether a status context is a required merge check."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any, Protocol
from urllib.parse import quote

from scripts.github_integration.boundary import (
    GitHubBoundaryError,
    GitHubClient,
    GitHubPermissionError,
)

DEFAULT_CONTEXT = "code-review/github-pr-review"
ENFORCED = "ENFORCED"
NOT_ENFORCED = "NOT ENFORCED"
UNKNOWN = "UNKNOWN"
PAGE_SIZE = 100
# GitHub's English 404 messages for readable-but-absent classic required checks. Coupled to
# the message text: if GitHub rewords them, detection degrades to UNKNOWN, never to a guess.
CLASSIC_ABSENT_MESSAGES = ("branch not protected", "required status checks not enabled")


class Reader(Protocol):
    """The only boundary surface detection may touch."""

    def read(self, endpoint: str) -> Any: ...


@dataclass(frozen=True)
class MechanismReading:
    state: str
    reason: str


@dataclass(frozen=True)
class EnforcementResult:
    state: str
    governing: str
    ruleset: MechanismReading
    classic: MechanismReading

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_rulesets(reader: Reader, repo: str, branch: str, context: str) -> MechanismReading:
    endpoint = f"repos/{repo}/rules/branches/{quote(branch, safe='/')}?per_page={PAGE_SIZE}"
    try:
        rules = reader.read(endpoint)
    except GitHubBoundaryError as exc:
        return MechanismReading(UNKNOWN, f"rules-for-branch unreadable: {exc}")
    if not isinstance(rules, list):
        return MechanismReading(UNKNOWN, "rules-for-branch returned an unexpected shape")
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("type") != "required_status_checks":
            continue
        params = rule.get("parameters")
        if not isinstance(params, dict):
            return MechanismReading(UNKNOWN, "required_status_checks rule has no parameters")
        for check in params.get("required_status_checks") or []:
            if isinstance(check, dict) and check.get("context") == context:
                return MechanismReading(ENFORCED, "listed by an active ruleset rule")
    if len(rules) >= PAGE_SIZE:
        return MechanismReading(UNKNOWN, "rules-for-branch may be truncated; not paginated")
    return MechanismReading(NOT_ENFORCED, "no active ruleset rule lists the context")


def _read_classic(reader: Reader, repo: str, branch: str, context: str) -> MechanismReading:
    endpoint = f"repos/{repo}/branches/{quote(branch, safe='/')}/protection/required_status_checks"
    try:
        data = reader.read(endpoint)
    except GitHubPermissionError as exc:
        # GitHub answers 404 "Branch not protected" for readable-but-absent protection;
        # any other 403/404 is an unreadable configuration, never an absence.
        if exc.status == 404 and any(m in exc.detail.lower() for m in CLASSIC_ABSENT_MESSAGES):
            return MechanismReading(NOT_ENFORCED, "branch has no classic required status checks")
        return MechanismReading(UNKNOWN, f"classic protection unreadable: {exc}")
    except GitHubBoundaryError as exc:
        return MechanismReading(UNKNOWN, f"classic protection unreadable: {exc}")
    if not isinstance(data, dict):
        return MechanismReading(UNKNOWN, "classic protection returned an unexpected shape")
    listed = [c.get("context") for c in data.get("checks") or [] if isinstance(c, dict)]
    listed += [c for c in data.get("contexts") or [] if isinstance(c, str)]
    if context in listed:
        return MechanismReading(ENFORCED, "listed by classic branch protection")
    return MechanismReading(NOT_ENFORCED, "classic required checks do not list the context")


def detect_enforcement(
    reader: Reader, repo: str, branch: str, context: str = DEFAULT_CONTEXT
) -> EnforcementResult:
    """Return the enforcement state of `context` on `branch`; reads only.

    Matching is by context name only; `integration_id` / `app_id` source pinning is ignored,
    so a check pinned to a different app still reports ENFORCED.
    """
    ruleset = _read_rulesets(reader, repo, branch, context)
    classic = _read_classic(reader, repo, branch, context)
    on = [n for n, r in (("ruleset", ruleset), ("classic", classic)) if r.state == ENFORCED]
    if on:
        state, governing = ENFORCED, "both" if len(on) == 2 else on[0]
    elif ruleset.state == classic.state == NOT_ENFORCED:
        state, governing = NOT_ENFORCED, "none"
    else:
        state, governing = UNKNOWN, "undetermined"
    return EnforcementResult(state, governing, ruleset, classic)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="owner/name")
    parser.add_argument("branch", help="the PR's base branch")
    parser.add_argument("--context", default=DEFAULT_CONTEXT)
    args = parser.parse_args(argv)
    result = detect_enforcement(GitHubClient(), args.repo, args.branch, args.context)
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
