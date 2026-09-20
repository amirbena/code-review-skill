"""GitHub REST ports over urllib, authenticated only by explicitly supplied App installation tokens."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Iterator, Mapping, Sequence

from runtime_platform.benchmark.publisher.layout import STAGING_REF_PREFIX
from runtime_platform.benchmark.publisher.ports import (
    HANDOFF_FILE,
    HISTORY_BRANCH,
    Comment,
    FatalPublicationError,
    Issue,
    PathExistsError,
    PublicationFailure,
    RefActivity,
    StagingRef,
)

API = "https://api.github.com"
INSTALLATION_TOKEN_PREFIX = "ghs_"
PAGE_SIZE = 100
Opener = Callable[..., Any]


class GitHubError(PublicationFailure):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status


def require_installation_token(name: str, token: str | None) -> str:
    """A personal or user token is refused outright: there is no fallback identity."""
    if not token:
        raise FatalPublicationError(f"{name} is not set; the publisher never falls back to a personal identity")
    if not token.startswith(INSTALLATION_TOKEN_PREFIX):
        raise FatalPublicationError(f"{name} is not a GitHub App installation token")
    return token


class GitHubClient:
    def __init__(self, token: str, *, api: str = API, opener: Opener = urllib.request.urlopen) -> None:
        self._token, self._api, self._opener = token, api, opener

    def call(
        self, method: str, path: str, *, body: Any = None, params: Mapping[str, str] | None = None,
        raw: bool = False, tolerate: Sequence[int] = (), auth_is_fatal: bool = True,
    ) -> tuple[int, Any]:
        """One request; statuses in `tolerate` return (status, None), and 401/403 stop the sweep."""
        url = self._api + path + (f"?{urllib.parse.urlencode(params)}" if params else "")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "benchmark-publication-sweep",
        }
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener(request, timeout=60) as response:
                status, payload = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, payload = exc.code, exc.read()
            exc.close()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GitHubError(0, f"{method} {path}: {exc}") from exc
        if status < 300:
            return status, payload if raw else (json.loads(payload) if payload else None)
        if status in tolerate:
            return status, None
        message = payload.decode("utf-8", "replace")[:200]
        if status in (401, 403) and auth_is_fatal:
            raise FatalPublicationError(f"GitHub refused {method} {path} (HTTP {status}): {message}")
        raise GitHubError(status, f"{method} {path}: {message}")

    def paginate(self, path: str, params: Mapping[str, str] | None = None) -> Iterator[Any]:
        page = 1
        while True:
            _, items = self.call("GET", path, params={**(params or {}), "per_page": str(PAGE_SIZE), "page": str(page)})
            yield from items
            if len(items) < PAGE_SIZE:
                return
            page += 1


def _quote(path: str) -> str:
    return urllib.parse.quote(path, safe="/")


class GitHubHandoffReader:
    def __init__(self, client: GitHubClient, repository: str) -> None:
        self._client, self._repo = client, repository

    def list_staging_refs(self, prefix: str) -> list[StagingRef]:
        items = self._client.paginate(f"/repos/{self._repo}/git/matching-refs/heads/{_quote(prefix)}")
        return [StagingRef(i["ref"][len("refs/heads/"):], i["object"]["sha"]) for i in items]

    def read_handoff(self, ref: StagingRef) -> bytes | None:
        _, data = self._client.call(
            "GET", f"/repos/{self._repo}/contents/{HANDOFF_FILE}", params={"ref": ref.sha}, raw=True, tolerate=(404,)
        )
        return data

    def ref_activities(self, ref_name: str) -> list[RefActivity] | None:
        _, items = self._client.call(
            "GET", f"/repos/{self._repo}/activity", params={"ref": f"refs/heads/{ref_name}", "per_page": str(PAGE_SIZE)},
            tolerate=(400, 403, 404, 422), auth_is_fatal=False,
        )
        if items is None:
            return None
        return [RefActivity(i["activity_type"], i["ref"], (i.get("actor") or {}).get("login", ""), i["after"]) for i in items]


class GitHubHistoryStore:
    def __init__(self, client: GitHubClient, repository: str, branch: str = HISTORY_BRANCH) -> None:
        self._client, self._repo, self._branch = client, repository, branch

    def _head(self) -> str | None:
        _, ref = self._client.call("GET", f"/repos/{self._repo}/git/ref/heads/{self._branch}", tolerate=(404,))
        return ref["object"]["sha"] if ref else None

    def read_file(self, path: str) -> bytes | None:
        _, data = self._client.call(
            "GET", f"/repos/{self._repo}/contents/{_quote(path)}", params={"ref": self._branch}, raw=True, tolerate=(404,)
        )
        return data

    def list_dir(self, path: str) -> list[str]:
        _, items = self._client.call(
            "GET", f"/repos/{self._repo}/contents/{_quote(path)}", params={"ref": self._branch}, tolerate=(404,)
        )
        return [i["name"] for i in items] if isinstance(items, list) else []

    def commit_files(self, files: Mapping[str, bytes], message: str) -> str:
        head = self._head()
        if head is not None:
            for path in files:
                if self.read_file(path) is not None:
                    raise PathExistsError(f"{path} already exists on {self._branch}")
        entries = []
        for path, content in files.items():
            _, blob = self._client.call(
                "POST", f"/repos/{self._repo}/git/blobs",
                body={"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"},
            )
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        tree_body: dict[str, Any] = {"tree": entries}
        parents: list[str] = []
        if head is not None:
            _, parent = self._client.call("GET", f"/repos/{self._repo}/git/commits/{head}")
            tree_body["base_tree"] = parent["tree"]["sha"]
            parents = [head]
        _, tree = self._client.call("POST", f"/repos/{self._repo}/git/trees", body=tree_body)
        _, commit = self._client.call(
            "POST", f"/repos/{self._repo}/git/commits", body={"message": message, "tree": tree["sha"], "parents": parents}
        )
        if head is None:
            self._client.call("POST", f"/repos/{self._repo}/git/refs", body={"ref": f"refs/heads/{self._branch}", "sha": commit["sha"]})
        else:
            self._client.call(
                "PATCH", f"/repos/{self._repo}/git/refs/heads/{self._branch}", body={"sha": commit["sha"], "force": False}
            )
        return commit["sha"]

    def last_commit_for(self, path: str) -> str | None:
        _, commits = self._client.call(
            "GET", f"/repos/{self._repo}/commits", params={"sha": self._branch, "path": path, "per_page": "1"}, tolerate=(404, 409)
        )
        return commits[0]["sha"] if commits else None

    def delete_staging_ref(self, name: str) -> None:
        if not name.startswith(STAGING_REF_PREFIX):
            raise PublicationFailure(f"refusing to delete {name!r}: not a benchmark staging ref")
        self._client.call("DELETE", f"/repos/{self._repo}/git/refs/heads/{_quote(name)}", tolerate=(404, 422))

    def permalink(self, commit: str, path: str) -> str:
        return f"https://github.com/{self._repo}/blob/{commit}/{path}"


def _comment(item: Mapping[str, Any]) -> Comment:
    return Comment(item["id"], item["user"]["login"], item.get("body") or "", item["html_url"])


def _issue(item: Mapping[str, Any]) -> Issue:
    return Issue(
        item["number"], item["user"]["login"], item.get("body") or "",
        tuple(label["name"] for label in item.get("labels", [])), item["state"], item["html_url"],
    )


class GitHubIssueTracker:
    def __init__(self, client: GitHubClient, repository: str) -> None:
        self._client, self._repo = client, repository

    def missing_labels(self, names: Sequence[str]) -> list[str]:
        missing = []
        for name in names:
            _, label = self._client.call("GET", f"/repos/{self._repo}/labels/{urllib.parse.quote(name)}", tolerate=(404,))
            if label is None:
                missing.append(name)
        return missing

    def list_comments(self, issue: int) -> list[Comment]:
        return [_comment(i) for i in self._client.paginate(f"/repos/{self._repo}/issues/{issue}/comments")]

    def create_comment(self, issue: int, body: str) -> Comment:
        _, item = self._client.call("POST", f"/repos/{self._repo}/issues/{issue}/comments", body={"body": body})
        return _comment(item)

    def list_issues(self, label: str, *, state: str, limit: int | None = None) -> list[Issue]:
        rows: list[Issue] = []
        params = {"labels": label, "state": state, "sort": "created", "direction": "desc"}
        for item in self._client.paginate(f"/repos/{self._repo}/issues", params):
            if "pull_request" not in item:
                rows.append(_issue(item))
            if limit is not None and len(rows) >= limit:
                break
        return rows

    def get_issue(self, number: int) -> Issue | None:
        _, item = self._client.call("GET", f"/repos/{self._repo}/issues/{number}", tolerate=(404,))
        return _issue(item) if item else None

    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> Issue:
        _, item = self._client.call("POST", f"/repos/{self._repo}/issues", body={"title": title, "body": body, "labels": list(labels)})
        return _issue(item)

    def close_issue(self, number: int) -> None:
        self._client.call("PATCH", f"/repos/{self._repo}/issues/{number}", body={"state": "closed", "state_reason": "completed"})
