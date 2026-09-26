"""Shared GitHub call and authentication boundary."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

READ_METHODS = frozenset({"GET", "HEAD"})
WRITE_METHODS = frozenset({"POST", "PATCH", "PUT"})
GOVERNANCE_METHODS = WRITE_METHODS | {"DELETE"}
TOKEN_ENV_VARS = ("GH_TOKEN", "GITHUB_TOKEN")
SCOPES_HEADER = "x-oauth-scopes"
NON_GOVERNANCE_WRITE_RE = re.compile(
    r"^repos/[^/]+/[^/]+/(statuses/[0-9a-f]{7,40}"
    r"|issues/\d+/comments(/\d+)?"
    r"|pulls/\d+/(reviews|comments)(/\d+)?)$"
)

Transport = Callable[[Sequence[str], Mapping[str, str], "str | None"], "RawResponse"]


class GitHubBoundaryError(Exception):
    """Base error carrying an actionable, token-free message."""


class AuthenticationError(GitHubBoundaryError):
    pass


class GitHubPermissionError(GitHubBoundaryError):
    pass


class AuthorizationRequiredError(GitHubBoundaryError):
    pass


class GitHubCallError(GitHubBoundaryError):
    pass


@dataclass(frozen=True)
class RawResponse:
    status: int
    body: str = ""
    headers: Mapping[str, str] | None = None


@dataclass(frozen=True)
class GovernanceAuthorization:
    """Explicit user request naming the governance change being authorized."""

    requested_by_user: bool
    description: str

    def is_valid(self) -> bool:
        return self.requested_by_user is True and bool(self.description.strip())


def _redact(text: str, token: str | None) -> str:
    return text.replace(token, "***") if token else text


def _gh_transport(args: Sequence[str], env: Mapping[str, str], stdin: str | None) -> RawResponse:
    try:
        proc = subprocess.run(
            ["gh", "api", "--include", *args],
            input=stdin.encode() if stdin is not None else None,
            capture_output=True,
            env={**os.environ, **env},
            check=False,
        )
    except OSError as exc:
        return RawResponse(0, f"gh CLI not runnable ({exc}); install it or add it to PATH")
    stdout = proc.stdout.decode("utf-8", "replace")
    stderr = proc.stderr.decode("utf-8", "replace")
    head, _, body = stdout.partition("\r\n\r\n")
    lines = head.splitlines()
    status = int(lines[0].split()[1]) if lines and lines[0].startswith("HTTP") else 0
    headers = {
        k.strip().lower(): v.strip()
        for k, _, v in (ln.partition(":") for ln in lines[1:])
    }
    if status == 0:
        return RawResponse(0, stderr, headers)
    return RawResponse(status, body, headers)


class GitHubClient:
    """Single seam for GitHub reads and governance-mutating writes."""

    def __init__(self, transport: Transport | None = None, env: Mapping[str, str] | None = None):
        self._transport = transport or _gh_transport
        self._env = os.environ if env is None else env

    def _token(self) -> str | None:
        return next((self._env[v] for v in TOKEN_ENV_VARS if self._env.get(v)), None)

    def _auth_env(self) -> dict[str, str]:
        token = self._token()
        return {"GH_TOKEN": token} if token else {}

    def _call(self, method: str, endpoint: str, payload: Mapping[str, Any] | None) -> Any:
        token = self._token()
        args = ["-X", method, endpoint] + (["--input", "-"] if payload is not None else [])
        body = json.dumps(payload) if payload is not None else None
        resp = self._transport(args, self._auth_env(), body)
        return self._interpret(method, endpoint, resp, token)

    def _interpret(self, method: str, endpoint: str, resp: RawResponse, token: str | None) -> Any:
        if resp.status in (200, 201, 202, 204):
            try:
                return json.loads(resp.body) if resp.body.strip() else None
            except ValueError as exc:
                raise GitHubCallError(f"{method} {endpoint}: non-JSON response body") from exc
        detail = _redact(resp.body, token)[:300]
        where = f"{method} {endpoint}"
        if resp.status == 0:
            raise GitHubCallError(f"{where}: gh unavailable or unreachable: {detail}")
        if resp.status == 401:
            raise AuthenticationError(
                f"{where}: not authenticated. Run `gh auth login` or set GH_TOKEN."
            )
        if resp.status in (403, 404):
            needed = (resp.headers or {}).get("x-accepted-oauth-scopes", "").strip()
            hint = f" Token needs: {needed}." if needed else ""
            raise GitHubPermissionError(
                f"{where}: HTTP {resp.status}; token lacks access or resource not visible."
                f"{hint} {detail}".strip()
            )
        raise GitHubCallError(f"{where}: HTTP {resp.status}: {detail}")

    def preflight(self, required_scopes: Sequence[str] = ()) -> None:
        """Verify authentication and, for classic tokens, required scopes."""
        resp = self._transport(["-X", "GET", "user"], self._auth_env(), None)
        self._interpret("GET", "user", resp, self._token())
        header = (resp.headers or {}).get(SCOPES_HEADER)
        if header is None or not required_scopes:
            return
        have = {s.strip() for s in header.split(",") if s.strip()}
        missing = [s for s in required_scopes if s not in have]
        if missing:
            raise GitHubPermissionError(
                f"Token missing scopes: {', '.join(missing)}. Re-authenticate with them."
            )

    def read(self, endpoint: str) -> Any:
        return self._call("GET", endpoint, None)

    def write(self, method: str, endpoint: str, payload: Mapping[str, Any] | None = None) -> Any:
        """Write to an allowlisted non-governance endpoint; anything else is refused."""
        method = method.upper()
        if method in READ_METHODS:
            raise GitHubBoundaryError("Use read() for read-only calls.")
        if method not in WRITE_METHODS:
            raise GitHubBoundaryError(f"Unsupported write method: {method!r}.")
        if not NON_GOVERNANCE_WRITE_RE.fullmatch(endpoint):
            raise AuthorizationRequiredError(
                f"Refusing {method} {endpoint}: not an allowlisted non-governance write; "
                "use mutate_governance()."
            )
        return self._call(method, endpoint, payload)

    def mutate_governance(
        self,
        method: str,
        endpoint: str,
        payload: Mapping[str, Any] | None,
        *,
        authorization: GovernanceAuthorization | None,
    ) -> Any:
        """Governance write; refused unless the user explicitly authorized it."""
        method = method.upper()
        if method in READ_METHODS:
            raise GitHubBoundaryError("Use read() for read-only calls.")
        if method not in GOVERNANCE_METHODS:
            raise GitHubBoundaryError(f"Unsupported governance method: {method!r}.")
        if authorization is None or not authorization.is_valid():
            raise AuthorizationRequiredError(
                f"Refusing {method} {endpoint}: governance mutation needs an explicit "
                "user request (GovernanceAuthorization)."
            )
        return self._call(method, endpoint, payload)
