#!/usr/bin/env python3
"""Loader and validator for the scheduled-benchmark expected-run manifest.

Contract: runtime_platform/benchmark/schedule-spec.md. Stdlib only; never
touches the network, GitHub, or a model.

Usage::

    python3 runtime_platform/benchmark/scripts/benchmark_schedule_manifest.py validate
    python3 runtime_platform/benchmark/scripts/benchmark_schedule_manifest.py validate --require-provisioned
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "runtime_platform" / "benchmark" / "schedule" / "expected-run-manifest.json"

SCHEMA_VERSION = "benchmark-schedule/v1"
MAX_GAP_CEILING_HOURS = {"sentinel": 96, "comprehensive": 192}
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
LABEL_ROLES = ("drift", "keep-open", "missed-run", "tracking")
STAGING_REF_PREFIX = "claude/benchmark-result-"

_TOP_KEYS = {
    "schema", "repository", "entrypoint", "lanes", "health_issue",
    "confirmation", "publication", "watchdog", "labels",
}
_LANE_KEYS = {
    "mode", "intended_cadence", "intended_start", "target_completion_local",
    "max_gap_hours", "tracking_issue",
}
_START_KEYS = {"weekday", "local_time", "timezone"}
_CONFIRMATION_KEYS = {"reruns", "threshold", "max_cases"}
_PUBLICATION_KEYS = {"staging_ref_pattern", "pusher_allowlist", "max_new_issues_per_run"}
_WATCHDOG_KEYS = {"missed_run_comment_interval_hours"}
_LABEL_KEYS = {"role", "name", "color", "description"}

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_COLOR_RE = re.compile(r"^[0-9a-f]{6}$")
_LABEL_DESCRIPTION_MAX = 100


class ManifestError(RuntimeError):
    """The manifest could not be loaded or is not usable."""


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"manifest {path} is not a JSON object")
    return data


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _closed_object(value: object, keys: set[str], where: str, errors: list[str]) -> dict | None:
    if not isinstance(value, dict):
        errors.append(f"{where}: must be an object")
        return None
    for key in sorted(keys - value.keys()):
        errors.append(f"{where}: missing field {key!r}")
    for key in sorted(value.keys() - keys):
        errors.append(f"{where}: unknown field {key!r}")
    return value


def _positive_int(value: object, where: str, errors: list[str]) -> bool:
    if not _is_int(value) or value < 1:
        errors.append(f"{where}: must be a positive integer")
        return False
    return True


def _issue_number(value: object, where: str, require_provisioned: bool, errors: list[str]) -> None:
    if value is None:
        if require_provisioned:
            errors.append(f"{where}: not provisioned (null)")
        return
    _positive_int(value, where, errors)


def _validate_lane(name: str, lane: object, require_provisioned: bool, errors: list[str]) -> None:
    where = f"lanes.{name}"
    lane = _closed_object(lane, _LANE_KEYS, where, errors)
    if lane is None:
        return
    if lane.get("mode") != name:
        errors.append(f"{where}.mode: must equal the lane name {name!r}")
    cadence = lane.get("intended_cadence")
    if not isinstance(cadence, str) or not cadence.strip():
        errors.append(f"{where}.intended_cadence: must be non-empty text")
    _validate_start(name, lane.get("intended_start"), where, errors)
    if not isinstance(lane.get("target_completion_local"), str) or not _TIME_RE.match(lane["target_completion_local"]):
        errors.append(f"{where}.target_completion_local: must be HH:MM")
    gap = lane.get("max_gap_hours")
    if _positive_int(gap, f"{where}.max_gap_hours", errors) and gap > MAX_GAP_CEILING_HOURS[name]:
        errors.append(f"{where}.max_gap_hours: must be <= {MAX_GAP_CEILING_HOURS[name]}")
    _issue_number(lane.get("tracking_issue"), f"{where}.tracking_issue", require_provisioned, errors)


def _validate_start(name: str, start: object, lane_where: str, errors: list[str]) -> None:
    where = f"{lane_where}.intended_start"
    start = _closed_object(start, _START_KEYS, where, errors)
    if start is None:
        return
    weekday = start.get("weekday")
    if name == "comprehensive":
        if weekday not in WEEKDAYS:
            errors.append(f"{where}.weekday: comprehensive lane must name one of {', '.join(WEEKDAYS)}")
    elif weekday is not None:
        errors.append(f"{where}.weekday: only the comprehensive lane is weekday-anchored (use null)")
    if not isinstance(start.get("local_time"), str) or not _TIME_RE.match(start["local_time"]):
        errors.append(f"{where}.local_time: must be HH:MM")
    timezone = start.get("timezone")
    if not isinstance(timezone, str) or not timezone.strip():
        errors.append(f"{where}.timezone: must be a non-empty zone name")


def _validate_confirmation(section: object, errors: list[str]) -> None:
    section = _closed_object(section, _CONFIRMATION_KEYS, "confirmation", errors)
    if section is None:
        return
    reruns_ok = _positive_int(section.get("reruns"), "confirmation.reruns", errors)
    _positive_int(section.get("max_cases"), "confirmation.max_cases", errors)
    threshold = section.get("threshold")
    if not _is_int(threshold) or threshold < 2:
        errors.append("confirmation.threshold: must be an integer >= 2 (1 would not confirm anything)")
    elif reruns_ok and threshold > section["reruns"] + 1:
        errors.append("confirmation.threshold: cannot exceed 1 + reruns observations")


def _validate_publication(section: object, errors: list[str]) -> None:
    section = _closed_object(section, _PUBLICATION_KEYS, "publication", errors)
    if section is None:
        return
    pattern = section.get("staging_ref_pattern")
    if not isinstance(pattern, str) or not pattern.startswith(STAGING_REF_PREFIX):
        errors.append(f"publication.staging_ref_pattern: must start with {STAGING_REF_PREFIX!r}")
    allowlist = section.get("pusher_allowlist")
    if not isinstance(allowlist, list) or not allowlist:
        errors.append("publication.pusher_allowlist: must be a non-empty list")
    else:
        for login in allowlist:
            if not isinstance(login, str) or not _LOGIN_RE.match(login):
                errors.append(f"publication.pusher_allowlist: invalid GitHub login {login!r}")
        if len(set(allowlist)) != len(allowlist):
            errors.append("publication.pusher_allowlist: duplicate entries")
    _positive_int(section.get("max_new_issues_per_run"), "publication.max_new_issues_per_run", errors)


def _validate_labels(labels: object, errors: list[str]) -> None:
    if not isinstance(labels, list):
        errors.append("labels: must be a list")
        return
    roles: list[object] = []
    names: list[object] = []
    for index, label in enumerate(labels):
        where = f"labels[{index}]"
        label = _closed_object(label, _LABEL_KEYS, where, errors)
        if label is None:
            continue
        roles.append(label.get("role"))
        names.append(label.get("name"))
        if not isinstance(label.get("name"), str) or not label["name"].strip():
            errors.append(f"{where}.name: must be non-empty text")
        if not isinstance(label.get("color"), str) or not _COLOR_RE.match(label["color"]):
            errors.append(f"{where}.color: must be six lowercase hex digits without '#'")
        description = label.get("description")
        if not isinstance(description, str) or not description.strip() or len(description) > _LABEL_DESCRIPTION_MAX:
            errors.append(f"{where}.description: must be 1-{_LABEL_DESCRIPTION_MAX} characters")
    if sorted(map(str, roles)) != sorted(LABEL_ROLES):
        errors.append(f"labels: must define exactly one label per role {', '.join(LABEL_ROLES)}")
    if len(set(map(str, names))) != len(names):
        errors.append("labels: duplicate label names")


def validate_manifest(manifest: object, *, require_provisioned: bool = False) -> list[str]:
    """Return every problem found; an empty list means the manifest is valid.

    `require_provisioned` additionally rejects unset tracking/health issues,
    for consumers that must fail closed before any GitHub write.
    """
    errors: list[str] = []
    top = _closed_object(manifest, _TOP_KEYS, "manifest", errors)
    if top is None:
        return errors
    if top.get("schema") != SCHEMA_VERSION:
        errors.append(f"schema: must be {SCHEMA_VERSION!r}")
    if not isinstance(top.get("repository"), str) or not _REPO_RE.match(top["repository"]):
        errors.append("repository: must be 'owner/name'")
    entrypoint = top.get("entrypoint")
    if not isinstance(entrypoint, str) or not entrypoint.endswith(".py") or entrypoint.startswith("/") or ".." in entrypoint.split("/"):
        errors.append("entrypoint: must be a repository-relative .py path")

    lanes = top.get("lanes")
    if not isinstance(lanes, dict) or set(lanes) != set(MAX_GAP_CEILING_HOURS):
        errors.append(f"lanes: must define exactly {', '.join(MAX_GAP_CEILING_HOURS)}")
    else:
        for name in MAX_GAP_CEILING_HOURS:
            _validate_lane(name, lanes[name], require_provisioned, errors)

    _issue_number(top.get("health_issue"), "health_issue", require_provisioned, errors)
    _validate_confirmation(top.get("confirmation"), errors)
    _validate_publication(top.get("publication"), errors)
    watchdog = _closed_object(top.get("watchdog"), _WATCHDOG_KEYS, "watchdog", errors)
    if watchdog is not None:
        _positive_int(watchdog.get("missed_run_comment_interval_hours"), "watchdog.missed_run_comment_interval_hours", errors)
    _validate_labels(top.get("labels"), errors)
    errors.extend(_duplicate_issue_numbers(top))
    return errors


def _duplicate_issue_numbers(manifest: dict) -> list[str]:
    lanes = manifest.get("lanes")
    if not isinstance(lanes, dict):
        return []
    numbers = [manifest.get("health_issue")] + [
        lane.get("tracking_issue") for lane in lanes.values() if isinstance(lane, dict)
    ]
    set_numbers = [n for n in numbers if _is_int(n)]
    if len(set(set_numbers)) != len(set_numbers):
        return ["tracking/health issue numbers must be distinct"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate the manifest; exit 1 on any problem")
    validate.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    validate.add_argument("--require-provisioned", action="store_true")
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    errors = validate_manifest(manifest, require_provisioned=args.require_provisioned)
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"{args.manifest}: valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
