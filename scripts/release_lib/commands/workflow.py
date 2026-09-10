"""Handlers that back the Release worthiness workflow's shell steps.

These two subcommands replace multi-line ``run: |`` blocks in
``.github/workflows/release-worthiness.yml`` so the reusable decisions are
unit-tested here and the YAML only wires inputs to outputs:

* ``resolve-base-ref`` — the diff base the ``assess`` job classifies
  against (the PR base commit, or the previous ``v*`` tag on a push).
* ``resolve-app-identity`` — the Git identity for the release commit,
  resolved from the minted release App's own slug via the GitHub API,
  failing closed rather than guessing.

Both are CI-only (Linux GitHub Actions runners); release automation never
runs on Windows, so there is no PowerShell counterpart.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

from release_lib import gitgh
from release_lib.commands.shared import emit_output

_NUMERIC_RE = re.compile(r"^[0-9]+$")


def cmd_resolve_base_ref(args: argparse.Namespace) -> int:
    """Emit ``ref=`` — what the ``assess`` job diffs HEAD against.

    On ``pull_request`` the base is the PR base commit and must be
    present. On any other event (push / manual dispatch) it is the
    previous ``v*`` tag, or empty when there is no prior release — the
    downstream classifier treats an empty base as "whole tree in scope".
    """
    repo_root = Path(args.repo_root).resolve()

    if args.event_name == "pull_request":
        ref = (args.pr_base_sha or "").strip()
        if not ref:
            print("::error::pull_request event with no pull_request.base.sha to diff against")
            return 1
    else:
        ref = gitgh.previous_release_tag(repo_root) or ""

    print(f"Base ref: {ref or '(none — whole tree in scope)'}")
    emit_output(args.github_output, ref=ref)
    return 0


def cmd_resolve_app_identity(args: argparse.Namespace) -> int:
    """Emit ``login=`` / ``email=`` for the release commit author.

    The identity is the GitHub App that authenticated the protected push,
    keyed by the ``app-slug`` that ``actions/create-github-app-token``
    returned. The bot login is always ``<slug>[bot]``; its numeric user id
    comes straight from the API. An unresolved slug or a non-numeric id
    aborts the release rather than falling back to a guessed identity.
    """
    repo_root = Path(args.repo_root).resolve()

    slug = (args.app_slug or "").strip()
    if not slug:
        print("::error::actions/create-github-app-token returned no app-slug; cannot resolve the release App bot identity.")
        return 1

    bot_login = f"{slug}[bot]"
    try:
        raw_id = gitgh._gh(["api", f"/users/{bot_login}", "--jq", ".id"], repo_root)
    except subprocess.CalledProcessError as exc:
        print(f"::error::GitHub API lookup for {bot_login} failed: {exc}")
        return 1

    bot_id = raw_id.strip()
    if not _NUMERIC_RE.match(bot_id):
        print(
            f"::error::Could not resolve a numeric user id for {bot_login} from the GitHub API; "
            "refusing to attribute the release commit to a fallback identity."
        )
        return 1

    bot_email = f"{bot_id}+{bot_login}@users.noreply.github.com"
    print(f"Release commits will be attributed to {bot_login} <{bot_email}>")
    emit_output(args.github_output, login=bot_login, email=bot_email)
    return 0
