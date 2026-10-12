"""The temporary P7 probe (provisioning runbook P7; issue #719): the App's comment lifecycle on private tracking issue #1.

Public Actions logs show fixed codes only. Nothing that came back from GitHub (an id, a login, a body, an error) is ever
formatted into output, and every failure is mapped to a code here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from runtime_platform.benchmark.publisher import github_api

PROBE_REPOSITORY = "amirbena/code-review-skill-evidence"
PROBE_ISSUE = 1
CREATED_BODY = "p7-probe (#719): temporary comment, created. Safe to delete."
EDITED_BODY = "p7-probe (#719): temporary comment, edited. Safe to delete."

OK, FAIL, SKIPPED = "ok", "fail", "skipped"
STEP_CODES = frozenset({OK, FAIL, SKIPPED})
STEPS = ("post", "read-back", "patch", "patch-read-back", "delete", "deleted")
NOT_NEEDED, CLEANED, CLEANUP_FAILED = "not-needed", "ok", "failed"
CLEANUP_CODES = frozenset({NOT_NEEDED, CLEANED, CLEANUP_FAILED})

_COMMENTS = f"/repos/{PROBE_REPOSITORY}/issues/{PROBE_ISSUE}/comments"
_ISSUE_URL_SUFFIX = f"/repos/{PROBE_REPOSITORY}/issues/{PROBE_ISSUE}"


@dataclass
class ProbeResult:
    steps: dict[str, str] = field(default_factory=lambda: {name: SKIPPED for name in STEPS})
    cleanup: str = NOT_NEEDED

    @property
    def passed(self) -> bool:
        return all(code == OK for code in self.steps.values()) and self.cleanup == NOT_NEEDED


def _comment_path(comment_id: int) -> str:
    return f"/repos/{PROBE_REPOSITORY}/issues/comments/{comment_id}"


def _is_bot(item: Any, bot_login: str) -> bool:
    user = item.get("user") or {}
    return user.get("login") == bot_login and user.get("type") == "Bot"


def _read_back(client: github_api.GitHubClient, comment_id: int, bot_login: str, body: str) -> bool:
    _, item = client.call("GET", _comment_path(comment_id), auth_is_fatal=False)
    return bool(
        isinstance(item, dict)
        and item.get("id") == comment_id
        and str(item.get("issue_url", "")).endswith(_ISSUE_URL_SUFFIX)
        and _is_bot(item, bot_login)
        and item.get("body") == body
    )


def _guarded(step: Callable[[], bool]) -> bool:
    try:
        return step()
    except Exception:  # noqa: BLE001 - nothing about the failure may reach a public log
        return False


def run_probe(client: github_api.GitHubClient, app_slug: str) -> ProbeResult:
    """POST, read back, PATCH, read back, DELETE, confirm gone, on one comment this call created; clean it up on failure."""
    bot_login = f"{app_slug}[bot]"
    result = ProbeResult()
    created: dict[str, int] = {}

    def post() -> bool:
        _, item = client.call("POST", _COMMENTS, body={"body": CREATED_BODY}, auth_is_fatal=False)
        comment_id = item.get("id") if isinstance(item, dict) else None
        if isinstance(comment_id, int):
            created["id"] = comment_id
        return isinstance(comment_id, int)

    def patch() -> bool:
        _, item = client.call("PATCH", _comment_path(created["id"]), body={"body": EDITED_BODY}, auth_is_fatal=False)
        return isinstance(item, dict) and item.get("id") == created["id"]

    def delete() -> bool:
        client.call("DELETE", _comment_path(created["id"]), auth_is_fatal=False)
        return True

    def deleted() -> bool:
        status, _ = client.call("GET", _comment_path(created["id"]), tolerate=(404,), auth_is_fatal=False)
        return status == 404

    plan: tuple[tuple[str, Callable[[], bool]], ...] = (
        ("post", post),
        ("read-back", lambda: _read_back(client, created["id"], bot_login, CREATED_BODY)),
        ("patch", patch),
        ("patch-read-back", lambda: _read_back(client, created["id"], bot_login, EDITED_BODY)),
        ("delete", delete),
        ("deleted", deleted),
    )
    for name, step in plan:
        if _guarded(step):
            result.steps[name] = OK
            continue
        result.steps[name] = FAIL
        break
    if "id" in created and result.steps["deleted"] != OK:
        # The comment may exist: delete the one this run created; a 404 means it is already gone.
        cleaned = _guarded(lambda: client.call("DELETE", _comment_path(created["id"]), tolerate=(404,), auth_is_fatal=False) is not None)
        result.cleanup = CLEANED if cleaned else CLEANUP_FAILED
    return result
