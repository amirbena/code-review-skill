"""Publish and verify a release's canonical distribution tree (#509).

The tree is the #507 build output (``dist/skills/<name>/`` plus
``dist/skills-manifest.json``); the zips and the distribution repository
both consume that single build. Publication is a fast-forward commit on the
distribution repository's default branch plus an annotated ``vX.Y.Z`` tag,
never a force push. Every mutation is preceded by a full comparison, so a
re-run is a no-op when the content matches and fails closed when it differs.

``verify()`` independently re-observes the remote (#559); see
docs/RELEASE.md, "Finalization gate".
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from release_lib.skill_version import skill_targets

MANIFEST_NAME = "skills-manifest.json"
DISTRIBUTION_JSON = "DISTRIBUTION.json"
ROOT_FILES_DIR = "distribution-root"
# Adapter templates (#510): published path -> template path under the source repo.
# The version is the single release version; no second source exists.
ROOT_TEMPLATES = {
    "plugin.json": "distribution/portable/plugin.json",
    ".claude-plugin/marketplace.json": "distribution/claude/marketplace.json",
}
BRANCH = "main"
TOKEN_ENV = "DISTRIBUTION_TOKEN"
_TRAILER_KEYS = ("Source-Repository", "Source-Commit", "Source-Tag")


class DistributionError(Exception):
    """A publication or verification failure with an actionable message."""


class GitCommandError(DistributionError):
    """A failed git command, keeping its exit status and raw stderr for diagnostics (#673)."""

    def __init__(self, message: str, returncode: int, output: str) -> None:
        super().__init__(message)
        self.returncode = returncode
        self.output = output


_URL_USERINFO_RE = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^/\s@]+@")
_AUTH_HEADER_RE = re.compile(r"(?i)(authorization\s*[:=]\s*)(?:basic|bearer|token)?\s*[A-Za-z0-9+/=_.-]+")
_TOKEN_SHAPE_RE = re.compile(r"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]+|x-access-token:[^\s@/]+")


def sanitize_output(text: str) -> str:
    """Strip credentials from git output before it reaches a log: the publisher
    token's value, URL userinfo, Authorization headers, and token-shaped strings."""
    token = os.environ.get(TOKEN_ENV)
    if token:
        text = text.replace(token, "***")
        text = text.replace(base64.b64encode(f"x-access-token:{token}".encode()).decode(), "***")
    text = _URL_USERINFO_RE.sub(r"\g<scheme>***@", text)
    text = _AUTH_HEADER_RE.sub(r"\1***", text)
    return _TOKEN_SHAPE_RE.sub("***", text)


def _ruleset_note(stderr: str) -> str:
    """Classify ruleset wording without over-claiming: a ``Bypassed rule violations``
    notice records that a rule was bypassed, not that the push was blocked by one."""
    lowered = stderr.lower()
    if "bypassed rule violations" in lowered:
        return (
            "ruleset: stderr carries a 'Bypassed rule violations' notice -- a bypass observation, "
            "not proof that a ruleset enforced this rejection; the cause is unconfirmed"
        )
    if "gh013" in lowered or "repository rule violations found" in lowered:
        return "ruleset: stderr reports an enforced rule/protection rejection"
    return "ruleset: no ruleset wording in stderr"


def _tag_push_diagnostics(
    work: Path, remote: str, tag: str, expected: str, exc: DistributionError, publisher: str
) -> str:
    """Safe, read-only evidence for a failed tag push. Never raises."""
    returncode = getattr(exc, "returncode", None)
    stderr = sanitize_output((getattr(exc, "output", None) or str(exc)).strip())
    tag_error = main_error = None
    observed_tag = observed_main = None
    try:
        observed_tag = _remote_tag_sha(work, remote, tag)
    except Exception as err:  # noqa: BLE001 - diagnostics must not mask the push failure
        tag_error = sanitize_output(str(err))
    try:
        observed_main = _remote_branch_sha(work, remote, BRANCH)
    except Exception as err:  # noqa: BLE001
        main_error = sanitize_output(str(err))
    if tag_error is not None:
        tag_state = "unknown: the remote could not be read, so tag state is unconfirmed; retry the check before recovering"
        shown_tag = f"unreadable ({tag_error})"
    elif observed_tag is None:
        tag_state = "missing: the tag push did not land"
        shown_tag = "absent"
    elif observed_tag == expected:
        tag_state = "present at the expected commit: the ref already exists, recovery will be a no-op"
        shown_tag = observed_tag
    else:
        tag_state = "present at a DIFFERENT commit: do not recover; investigate"
        shown_tag = observed_tag
    shown_main = f"unreadable ({main_error})" if main_error is not None else (observed_main or "absent")
    return (
        f"git push exit status: {returncode if returncode is not None else 'unknown'}; "
        f"stderr: {stderr or '(empty)'}; "
        f"expected {tag} -> {expected}, observed remote {tag} -> {shown_tag} ({tag_state}); "
        f"expected {BRANCH} to contain {expected}, observed remote {BRANCH} -> {shown_main}; "
        f"publisher identity: {publisher}; {_ruleset_note(stderr)}"
    )


@dataclass(frozen=True)
class Build:
    files: dict[str, bytes]  # published path -> bytes, including DISTRIBUTION.json

    def hashes(self) -> dict[str, str]:
        return {path: _sha(data) for path, data in self.files.items()}

    def content_hash(self) -> str:
        return content_manifest_hash(self.hashes())


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_manifest_hash(hashes: dict[str, str]) -> str:
    """Aggregate hash over every published file except DISTRIBUTION.json (which embeds it)."""
    lines = "".join(
        f"{digest}  {path}\n" for path, digest in sorted(hashes.items()) if path != DISTRIBUTION_JSON
    )
    return _sha(lines.encode("utf-8"))


def _read_tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(root).parts
    }


def build_distribution(
    repo_root: Path, dist: Path, version: str, source_repository: str, source_commit: str
) -> Build:
    """Assemble the exact published file set from the #507 build; verify it against its manifest."""
    manifest_path = dist / MANIFEST_NAME
    if not manifest_path.is_file():
        raise DistributionError(f"{manifest_path} is missing; build the Skill trees first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {name for name, _ in skill_targets(repo_root)}
    if set(manifest["skills"]) != expected:
        raise DistributionError(
            f"built Skills {sorted(manifest['skills'])} differ from the package manifest {sorted(expected)}"
        )
    files: dict[str, bytes] = {}
    for name, entry in manifest["skills"].items():
        tree = _read_tree(dist / "skills" / name)
        if {p: _sha(b) for p, b in tree.items()} != entry["files"]:
            raise DistributionError(f"dist/skills/{name}/ does not match {MANIFEST_NAME}; rebuild it")
        files.update({f"skills/{name}/{p}": b for p, b in tree.items()})
    root_dir = dist / ROOT_FILES_DIR
    if root_dir.is_dir():
        files.update(_read_tree(root_dir))
    files["LICENSE"] = (repo_root / "LICENSE").read_bytes()
    for published, template in ROOT_TEMPLATES.items():
        path = repo_root / template
        if not path.is_file():
            raise DistributionError(f"distribution template {template} is missing")
        rendered = path.read_text(encoding="utf-8").replace("{{version}}", version)
        files[published] = rendered.replace("{{source_repository}}", source_repository).encode("utf-8")
        json.loads(files[published])  # invalid rendered JSON must fail here, not at install time
    if "README.md" not in files:
        files["README.md"] = _readme(source_repository, version).encode("utf-8")
    hashes = {p: _sha(b) for p, b in files.items()}
    files[DISTRIBUTION_JSON] = (
        json.dumps(
            {
                "schema_version": 1,
                "source_repository": source_repository,
                "source_commit": source_commit,
                "version": version,
                "content_manifest_hash": content_manifest_hash(hashes),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    return Build(files)


def _readme(source_repository: str, version: str) -> str:
    return (
        "# Code Review Skills (generated)\n\n"
        f"This repository is generated at release time (currently v{version}) and must not be edited by hand.\n"
        f"Source, issues, and contribution guidance: https://github.com/{source_repository}\n"
    )


def verify_zips(repo_root: Path, dist: Path, build: Build) -> None:
    """Every release zip holds exactly its Skill's published tree bytes."""
    for name, archive in skill_targets(repo_root):
        prefix = f"skills/{name}/"
        want = {p[len(prefix):]: b for p, b in build.files.items() if p.startswith(prefix)}
        with zipfile.ZipFile(dist / archive) as zf:
            have = {i.filename: zf.read(i) for i in zf.infolist() if not i.is_dir()}
        if have != want:
            raise DistributionError(f"{archive} was not built from the distribution tree for {name}")


def _git(args: list[str], cwd: Path, remote_url: str | None = None, check: bool = True) -> str:
    env = dict(os.environ)
    token = os.environ.get(TOKEN_ENV)
    if token and remote_url and remote_url.startswith("https://"):
        header = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update(
            GIT_CONFIG_COUNT="1",
            GIT_CONFIG_KEY_0=f"http.{remote_url}.extraheader",
            GIT_CONFIG_VALUE_0=f"AUTHORIZATION: basic {header}",
        )
    env["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    if check and result.returncode != 0:
        output = sanitize_output((result.stderr or result.stdout).strip())
        raise GitCommandError(f"git {args[0]} failed: {output}", result.returncode, output)
    return result.stdout


def _remote_tag_sha(work: Path, remote: str, tag: str) -> str | None:
    out = _git(["ls-remote", "--tags", remote, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"], work, remote)
    refs = dict(line.split("\t")[::-1] for line in out.splitlines())
    return refs.get(f"refs/tags/{tag}^{{}}") or refs.get(f"refs/tags/{tag}")


def _remote_branch_sha(work: Path, remote: str, branch: str) -> str | None:
    out = _git(["ls-remote", remote, f"refs/heads/{branch}"], work, remote)
    line = out.strip()
    return line.split("\t")[0] if line else None


def _is_ancestor(work: Path, commit: str, of: str) -> bool:
    """True when ``commit`` is ``of`` or an ancestor of it. Both objects must
    already be present in ``work``'s object store (fetched beforehand)."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, of], cwd=work, capture_output=True, text=True
    )
    if result.returncode not in (0, 1):
        raise DistributionError(f"git merge-base --is-ancestor failed: {(result.stderr or result.stdout).strip()}")
    return result.returncode == 0


def _checkout_hashes(work: Path, ref: str) -> dict[str, str]:
    _git(["checkout", "--detach", "--force", ref], work)
    return {p: _sha(b) for p, b in _read_tree(work).items()}


def _new_workdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="distribution-"))


def _fetch(work: Path, remote: str, *refspecs: str) -> None:
    _git(["init", "--quiet"], work)
    _git(["fetch", "--quiet", remote, *refspecs], work, remote)


def _trailers(message: str) -> dict[str, str]:
    found = {}
    for line in message.splitlines():
        key, _, value = line.partition(":")
        if key in _TRAILER_KEYS:
            found[key] = value.strip()
    return found


def _expected_trailers(build: Build, tag: str, source_repository: str) -> dict[str, str]:
    meta = json.loads(build.files[DISTRIBUTION_JSON])
    return {
        "Source-Repository": source_repository,
        "Source-Commit": meta["source_commit"],
        "Source-Tag": tag,
    }


def _semver_key(tag: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in tag.removeprefix("v").split("."))
    except ValueError:
        return None


def _diff(want: dict[str, str], have: dict[str, str]) -> str:
    missing = sorted(set(want) - set(have))
    extra = sorted(set(have) - set(want))
    differ = sorted(p for p in set(want) & set(have) if want[p] != have[p])
    return f"missing={missing} extra={extra} differ={differ}"


def publish(build: Build, remote: str, version: str, source_repository: str, identity: tuple[str, str]) -> str:
    """Publish ``build`` as ``v<version>``. Returns ``created``, ``tagged`` or ``unchanged``."""
    tag = f"v{version}"
    want = build.hashes()
    work = _new_workdir()
    try:
        existing = _remote_tag_sha(work, remote, tag)
        if existing:
            _fetch(work, remote, f"refs/tags/{tag}:refs/tags/{tag}")
            have = _checkout_hashes(work, tag)
            if have != want:
                raise DistributionError(
                    f"{tag} already exists in the distribution repository with different content "
                    f"({_diff(want, have)}); nothing was changed. Fix the source or cut a new version"
                )
            return "unchanged"

        _fetch(work, remote, f"refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}")
        tip = _git(["rev-parse", f"refs/remotes/origin/{BRANCH}"], work).strip()
        _git(["checkout", "--detach", "--force", tip], work)
        trailers = _expected_trailers(build, tag, source_repository)
        outcome = "tagged"
        if _trailers(_git(["log", "-1", "--format=%B", tip], work)) != trailers or _checkout_hashes(
            work, tip
        ) != want:
            tip_tag = _trailers(_git(["log", "-1", "--format=%B", tip], work)).get("Source-Tag", "")
            newer, this = _semver_key(tip_tag), _semver_key(tag)
            if tip_tag and (newer is None or this is None):
                raise DistributionError(
                    f"refusing to publish {tag}: cannot order it against {BRANCH}'s {tip_tag!r}; "
                    f"nothing was changed"
                )
            if newer and this and newer > this:
                raise DistributionError(
                    f"refusing to publish {tag}: {BRANCH} already carries {tip_tag}, so this would put "
                    f"older content on the branch tip; nothing was changed"
                )
            for child in work.iterdir():
                if child.name != ".git":
                    shutil.rmtree(child) if child.is_dir() else child.unlink()
            for path, data in build.files.items():
                target = work / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            _git(["add", "--all", "--force"], work)
            message = f"Publish {tag}\n\n" + "\n".join(f"{k}: {v}" for k, v in trailers.items()) + "\n"
            _git(
                ["-c", f"user.name={identity[0]}", "-c", f"user.email={identity[1]}",
                 "commit", "--quiet", "--allow-empty", "-m", message],
                work,
            )
            try:
                _git(["push", "--quiet", remote, f"HEAD:refs/heads/{BRANCH}"], work, remote)
            except DistributionError as exc:
                raise DistributionError(
                    f"push to {BRANCH} was rejected (not a fast-forward, or a ruleset/credential problem); "
                    f"no tag was created and the branch was not forced: {exc}"
                ) from exc
            outcome = "created"
        _git(
            ["-c", f"user.name={identity[0]}", "-c", f"user.email={identity[1]}",
             "tag", "-a", tag, "-m", f"Release {tag}", "HEAD"],
            work,
        )
        try:
            _git(["push", "--quiet", remote, f"refs/tags/{tag}"], work, remote)
        except DistributionError as exc:
            expected = _git(["rev-parse", "HEAD"], work).strip()
            details = _tag_push_diagnostics(work, remote, tag, expected, exc, f"{identity[0]} <{identity[1]}>")
            raise DistributionError(
                f"the distribution commit is on {BRANCH} but tag {tag} could not be created "
                f"({details}); re-run (workflow_dispatch) to finish tagging if the tag is missing, "
                f"nothing was force-pushed and nothing was retried"
            ) from None
        return outcome
    finally:
        shutil.rmtree(work, ignore_errors=True)


def verify(build: Build, remote: str, version: str, source_repository: str) -> None:
    """The distribution tag's content, provenance, and main-reachability
    equal the build, read back independently from a fresh clone."""
    tag = f"v{version}"
    work = _new_workdir()
    try:
        tag_sha = _remote_tag_sha(work, remote, tag)
        if tag_sha is None:
            raise DistributionError(f"tag {tag} does not exist in the distribution repository")
        branch_sha = _remote_branch_sha(work, remote, BRANCH)
        if branch_sha is None:
            raise DistributionError(f"remote {BRANCH!r} does not exist in the distribution repository")
        _fetch(
            work, remote,
            f"refs/tags/{tag}:refs/tags/{tag}",
            f"refs/heads/{BRANCH}:refs/remotes/origin/{BRANCH}",
        )
        have = _checkout_hashes(work, tag)
        want = build.hashes()
        if have != want:
            raise DistributionError(f"distribution {tag} manifest differs from the build: {_diff(want, have)}")
        got = _trailers(_git(["log", "-1", "--format=%B", f"{tag}^{{commit}}"], work))
        expected = _expected_trailers(build, tag, source_repository)
        if got != expected:
            raise DistributionError(f"distribution {tag} commit trailers {got} differ from expected {expected}")
        if not _is_ancestor(work, f"{tag}^{{commit}}", branch_sha):
            raise DistributionError(
                f"distribution {tag} exists but is not reachable from remote {BRANCH!r} (tip {branch_sha}); "
                f"the branch update did not actually reach the remote"
            )
    finally:
        shutil.rmtree(work, ignore_errors=True)
