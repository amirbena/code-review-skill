"""Explicit opt-in setup and removal of the review status as a required merge check."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from scripts.github_integration.boundary import (
    GitHubBoundaryError,
    GitHubCallError,
    GitHubClient,
    GovernanceAuthorization,
)
from scripts.github_integration.enforcement import (
    CLASSIC_ABSENT_MESSAGES,
    DEFAULT_CONTEXT,
    ENFORCED,
    NOT_ENFORCED,
    PAGE_SIZE,
    detect_enforcement,
)
from scripts.github_integration.status_publisher import REPO_RE

RULE_TYPE = "required_status_checks"
RULESET_WRITABLE = ("name", "target", "enforcement", "bypass_actors", "conditions", "rules")
REPOSITORY_SOURCE = "Repository"


@dataclass(frozen=True)
class SetupRequest:
    """Resolved facts; authorization comes only from an explicit user request."""

    repo: str
    branch: str
    context: str = DEFAULT_CONTEXT
    remove: bool = False
    active_mode: bool = False
    reviewer_independent: bool = False
    authorization: GovernanceAuthorization | None = None


@dataclass(frozen=True)
class SetupOutcome:
    action: str  # "added" | "removed" | "noop" | "refused" | "failed"
    mechanism: str
    message: str
    before: Any = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        return self.action in ("added", "removed", "noop")


class _Refuse(Exception):
    def __init__(self, message: str, action: str = "refused"):
        super().__init__(message)
        self.action = action


def _canon(value: Any) -> Any:
    """Order-insensitive form: GitHub may reorder lists on read-back."""
    if isinstance(value, dict):
        return {k: _canon(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return sorted((_canon(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    return value


def _unverified(mechanism: str, before: Any, why: str) -> SetupOutcome:
    return SetupOutcome(
        "failed", mechanism,
        f"The write may have been applied but could not be verified ({why}). Inspect the "
        "governance configuration; the pre-change configuration is attached.",
        before,
    )


def _write(client: GitHubClient, req: SetupRequest, mechanism: str, before: Any,
           method: str, endpoint: str, payload: Any) -> SetupOutcome | None:
    """Issue the governance write; return an outcome only when its result is unknown."""
    try:
        client.mutate_governance(method, endpoint, payload, authorization=req.authorization)
    except GitHubCallError as exc:
        if exc.status == 0 or (exc.status or 0) >= 500:
            return _unverified(mechanism, before, str(exc))
        raise
    return None


def _gates(req: SetupRequest) -> None:
    if not REPO_RE.fullmatch(req.repo) or ".." in req.repo:
        raise ValueError(f"invalid repository: {req.repo!r}")
    if req.authorization is None or not req.authorization.is_valid():
        raise _Refuse(
            "Refused: changing required checks needs an explicit user request to set up "
            "(or remove) the code-review status as a required check. Nothing was changed."
        )
    if not (req.active_mode and req.reviewer_independent):
        raise _Refuse(
            "Refused: setup needs ACTIVE publication mode and reviewer independence "
            "(issue #34). Nothing was changed."
        )


def _check_contexts(checks: Any) -> list[str]:
    return [c["context"] for c in checks or [] if isinstance(c, dict) and "context" in c]


def _ruleset_lists(rule: dict, context: str) -> bool:
    params = rule.get("parameters") or {}
    return context in _check_contexts(params.get("required_status_checks"))


@dataclass
class _Survey:
    repo_rulesets: dict[int, bool]  # ruleset id -> lists context
    other_source: bool  # a required-checks rule from a non-repository (org) ruleset
    classic_present: bool
    classic_lists: bool


def _survey(client: GitHubClient, req: SetupRequest) -> _Survey:
    rules = client.read(
        f"repos/{req.repo}/rules/branches/{quote(req.branch, safe='/')}?per_page={PAGE_SIZE}"
    )
    if not isinstance(rules, list) or len(rules) >= PAGE_SIZE:
        raise _Refuse("Refused: branch rules are unreadable or possibly truncated.", "failed")
    repo_rulesets: dict[int, bool] = {}
    other = False
    for rule in rules:
        if not isinstance(rule, dict) or rule.get("type") != RULE_TYPE:
            continue
        if rule.get("ruleset_source_type") != REPOSITORY_SOURCE:
            other = True
            continue
        rid = rule.get("ruleset_id")
        if not isinstance(rid, int):
            raise _Refuse("Refused: a required-checks rule has no ruleset id.", "failed")
        repo_rulesets[rid] = repo_rulesets.get(rid, False) or _ruleset_lists(rule, req.context)
    present, lists = _read_classic(client, req)
    return _Survey(repo_rulesets, other, present, lists)


def _read_classic(client: GitHubClient, req: SetupRequest) -> tuple[bool, bool]:
    endpoint = f"repos/{req.repo}/branches/{quote(req.branch, safe='/')}/protection"
    try:
        data = client.read(f"{endpoint}/required_status_checks")
    except GitHubBoundaryError as exc:
        status = getattr(exc, "status", None)
        detail = getattr(exc, "detail", "").lower()
        if status == 404 and any(m in detail for m in CLASSIC_ABSENT_MESSAGES):
            return False, False
        raise
    if not isinstance(data, dict):
        raise _Refuse("Refused: classic required checks returned an unexpected shape.", "failed")
    listed = _check_contexts(data.get("checks")) + [
        c for c in data.get("contexts") or [] if isinstance(c, str)
    ]
    return True, req.context in listed


def _pick_target(survey: _Survey, req: SetupRequest) -> tuple[str, int | None]:
    """Choose the one mechanism to edit; ambiguity or absence refuses."""
    if req.remove:
        rulesets = [i for i, listed in survey.repo_rulesets.items() if listed]
        classic = survey.classic_lists
    else:
        rulesets = list(survey.repo_rulesets)
        classic = survey.classic_present
    count = len(rulesets) + int(classic)
    if count > 1:
        raise _Refuse(
            "Refused: more than one mechanism or ruleset carries required checks for this "
            "branch; conflicting governance is not edited automatically."
        )
    if count == 0:
        if survey.other_source:
            raise _Refuse(
                "Refused: only an organization-level ruleset requires checks here; it cannot "
                "be edited from this repository."
            )
        raise _Refuse(
            "Refused: no existing required-checks configuration to extend. Creating a "
            "Ruleset or branch protection is not done unprompted."
        )
    return ("classic", None) if classic else ("ruleset", rulesets[0])


def _edit_ruleset(client, req: SetupRequest, rid: int) -> SetupOutcome:
    endpoint = f"repos/{req.repo}/rulesets/{rid}"
    before = client.read(endpoint)
    if not isinstance(before, dict) or not isinstance(before.get("rules"), list):
        raise _Refuse("Refused: ruleset has an unexpected shape.", "failed")
    current = {k: before[k] for k in RULESET_WRITABLE if k in before}
    targets = [r for r in current["rules"] if isinstance(r, dict) and r.get("type") == RULE_TYPE]
    if len(targets) != 1:
        raise _Refuse("Refused: ruleset does not have exactly one required-checks rule.")
    desired = copy.deepcopy(current)
    rule = next(r for r in desired["rules"] if r.get("type") == RULE_TYPE)
    checks = rule.setdefault("parameters", {}).setdefault("required_status_checks", [])
    if req.remove:
        kept = [c for c in checks if not (isinstance(c, dict) and c.get("context") == req.context)]
        if not kept:
            raise _Refuse("Refused: removal would leave the ruleset with no required checks.")
        rule["parameters"]["required_status_checks"] = kept
    else:
        checks.append({"context": req.context})
    fresh = client.read(endpoint)
    writable = lambda r: _canon({k: r[k] for k in RULESET_WRITABLE if k in r})
    if not isinstance(fresh, dict) or writable(fresh) != writable(current):
        raise _Refuse("Refused: the ruleset changed while it was being edited; re-run to retry.")
    unknown = _write(client, req, "ruleset", current, "PUT", endpoint, desired)
    if unknown:
        return unknown
    try:
        after = client.read(endpoint)
    except GitHubBoundaryError as exc:
        return _unverified("ruleset", current, f"read-back failed: {exc}")
    if not isinstance(after, dict) or writable(after) != writable(desired):
        return SetupOutcome(
            "failed", "ruleset",
            f"Read-back of ruleset {rid} differs from the intended change; inspect it. "
            "The pre-change configuration is attached.",
            current,
        )
    verb = "removed from" if req.remove else "added to"
    return SetupOutcome("removed" if req.remove else "added", "ruleset",
                        f"{req.context} {verb} ruleset {rid}; read-back verified.", current)


def _edit_classic(client, req: SetupRequest) -> SetupOutcome:
    base = f"repos/{req.repo}/branches/{quote(req.branch, safe='/')}/protection"
    before = client.read(base)
    if not isinstance(before, dict) or not isinstance(before.get("required_status_checks"), dict):
        raise _Refuse("Refused: branch protection has an unexpected shape.", "failed")
    unknown = _write(client, req, "classic", before, "DELETE" if req.remove else "POST",
                     f"{base}/required_status_checks/contexts", [req.context])
    if unknown:
        return unknown
    try:
        after = client.read(base)
    except GitHubBoundaryError as exc:
        return _unverified("classic", before, f"read-back failed: {exc}")
    if not isinstance(after, dict):
        return _unverified("classic", before, "read-back returned an unexpected shape")
    rest = lambda p: _canon({k: v for k, v in p.items() if k != "required_status_checks"})
    old, new = before["required_status_checks"], after.get("required_status_checks") or {}
    listed = lambda r: set(_check_contexts(r.get("checks"))) | set(r.get("contexts") or [])
    expected = listed(old) - {req.context} if req.remove else listed(old) | {req.context}
    other = lambda r: _canon({k: v for k, v in r.items() if k not in ("checks", "contexts")})
    if rest(before) != rest(after) or other(old) != other(new) or listed(new) != expected:
        return SetupOutcome(
            "failed", "classic",
            "Read-back of branch protection differs from the intended change; inspect it. "
            "The pre-change configuration is attached.",
            before,
        )
    verb = "removed from" if req.remove else "added to"
    return SetupOutcome("removed" if req.remove else "added", "classic",
                        f"{req.context} {verb} classic required checks; read-back verified.",
                        before)


def apply_required_check(client: GitHubClient, req: SetupRequest) -> SetupOutcome:
    """Add (or remove) the one context on the governing mechanism, or change nothing."""
    try:
        _gates(req)
        if not req.remove:
            state = detect_enforcement(client, req.repo, req.branch, req.context)
            if state.state == ENFORCED:
                return SetupOutcome("noop", state.governing, "Already required; no change.")
            if state.state != NOT_ENFORCED:
                raise _Refuse(
                    "Refused: enforcement state is UNKNOWN (a configuration could not be "
                    f"read: ruleset: {state.ruleset.reason}; classic: {state.classic.reason}).",
                    "failed",
                )
        survey = _survey(client, req)
        if req.remove and not any(survey.repo_rulesets.values()) and not survey.classic_lists:
            if survey.other_source:
                raise _Refuse(
                    "Refused: a non-repository ruleset requires checks here; "
                    "it is not editable from this repository."
                )
            return SetupOutcome("noop", "none", "Context is not required; no change.")
        mechanism, rid = _pick_target(survey, req)
        if mechanism == "ruleset":
            return _edit_ruleset(client, req, rid)
        return _edit_classic(client, req)
    except _Refuse as exc:
        return SetupOutcome(exc.action, "none", str(exc))
    except GitHubBoundaryError as exc:
        return SetupOutcome("failed", "none", f"{exc} No change was applied.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="owner/name")
    parser.add_argument("branch", help="the PR's base branch")
    parser.add_argument("--context", default=DEFAULT_CONTEXT)
    parser.add_argument("--remove", action="store_true", help="remove the context instead")
    parser.add_argument("--user-request", default="", help="the user's explicit request, verbatim")
    parser.add_argument("--active-mode", action="store_true")
    parser.add_argument("--reviewer-independent", action="store_true")
    args = parser.parse_args(argv)
    authorization = (
        GovernanceAuthorization(True, args.user_request) if args.user_request.strip() else None
    )
    req = SetupRequest(
        args.repo, args.branch, args.context, args.remove,
        args.active_mode, args.reviewer_independent, authorization,
    )
    outcome = apply_required_check(GitHubClient(), req)
    print(json.dumps({"action": outcome.action, "mechanism": outcome.mechanism,
                      "message": outcome.message, "before": outcome.before}, indent=2))
    return 0 if outcome.ok else 1


if __name__ == "__main__":
    sys.exit(main())
