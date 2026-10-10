"""The one writer for every public surface of the publication CLI (ADR §5.4, F12/F13).

In the `private` phase the workflow's logs are public while the evidence is not, so a value reaches stdout or stderr only
through this module, and only after it is validated against its allowed class immediately before it is written. A value that
is not on the list, or fails validation, is replaced by `WITHHELD`; it is never printed as is, and withholding never changes
an exit status. Under `pre_cutover` the source repository is the evidence store, so the legacy output is kept unchanged.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any, Mapping, TextIO

from runtime_platform.benchmark.publisher.layout import STAGING_REF_PREFIX, run_id_from_ref
from runtime_platform.benchmark.publisher.model import ALREADY_PUBLISHED, FAILED, PUBLISHED, REFUSED, SweepReport, WatchdogReport
from runtime_platform.benchmark.publisher.validation import GATES
from runtime_platform.benchmark.scripts.benchmark_evidence_config import PHASE_PRE_CUTOVER

WITHHELD = "withheld"
STATUS_CODES = frozenset({PUBLISHED, ALREADY_PUBLISHED, REFUSED, FAILED})
GATE_CODES = GATES | {"step"}
# The `aborted` reason text and every `error:` message are replaced by one of these fixed codes.
ABORTED_CODE = "publication-aborted"
ERROR_CODES = frozenset({
    "internal-error", "usage", "invalid-manifest", "invalid-evidence-destination", "app-slug-required",
    "evidence-unavailable", "invalid-sweep-report",
})
_IDENTITY_RE = re.compile(r"^[a-z0-9][a-z0-9-]*\[bot\]$")
_INSTANT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def is_private(manifest: Mapping[str, Any] | None) -> bool:
    """Fail closed: only an explicit `pre_cutover` phase keeps the legacy output; any other phase, or no manifest at all, is allowlisted."""
    return not manifest or (manifest.get("evidence") or {}).get("phase") != PHASE_PRE_CUTOVER


def _count(value: object) -> int | str:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else WITHHELD


def _bool(value: object) -> bool | str:
    return value if isinstance(value, bool) else WITHHELD


def _code(value: object, allowed: frozenset[str]) -> str:
    return value if isinstance(value, str) and value in allowed else WITHHELD


def _ref(value: object) -> str:
    return value if isinstance(value, str) and run_id_from_ref(value) is not None else WITHHELD


def _run_id(value: object) -> str:
    return value if isinstance(value, str) and run_id_from_ref(STAGING_REF_PREFIX + value) is not None else WITHHELD


def _identity(value: object) -> str:
    return value if isinstance(value, str) and _IDENTITY_RE.match(value) else WITHHELD


def _lane(value: object, manifest: Mapping[str, Any]) -> str:
    return value if isinstance(value, str) and value in manifest.get("lanes", {}) else WITHHELD


def _instant(value: object) -> str | None:
    return value if isinstance(value, str) and _INSTANT_RE.match(value) else None


def sweep_view(report: SweepReport, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """The sweep report as the allowlist admits it: codes, refs and counts, never `detail`, `commit`, `actions` or `deferred`."""
    runs = [
        {"ref": _ref(o.ref), "run_id": _run_id(o.run_id), "status": _code(o.status, STATUS_CODES), "gate": _code(o.gate or "step", GATE_CODES)}
        for o in report.outcomes
    ]
    counts: dict[str, int] = {}
    for run in runs:
        counts[run["status"]] = counts.get(run["status"], 0) + 1
    return {
        "identity": _identity(report.identity), "ok": _bool(report.ok), "aborted": ABORTED_CODE if report.aborted else None,
        "scope": _code(report.scope, frozenset({"all", "run-id"})), "dry_run": _bool(report.dry_run), "runs": runs, "counts": counts,
    }


def watchdog_view(report: WatchdogReport, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """The watchdog report as the allowlist admits it: no `action`, `overdue`, issue numbers, counts of issues or timestamps from records."""
    lanes = [{"lane": _lane(row.get("lane"), manifest), "expected_from": _instant(row.get("expected_from"))} for row in report.lanes]
    return {
        "identity": _identity(report.identity), "ok": _bool(report.ok), "aborted": ABORTED_CODE if report.aborted else None,
        "lanes": lanes, "pending_handoffs": _count(report.health.get("pending_handoffs")) if report.health else None,
    }


class PublicLog:
    """Writes the public stdout and stderr; `private` selects the allowlist, `False` keeps the legacy `pre_cutover` output."""

    def __init__(self, manifest: Mapping[str, Any] | None, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> None:
        self.manifest = manifest or {}
        self.private = is_private(manifest)
        self._stdout, self._stderr = stdout, stderr

    @property
    def out(self) -> TextIO:
        return self._stdout or sys.stdout

    @property
    def err(self) -> TextIO:
        return self._stderr or sys.stderr

    def error(self, message: str, code: str) -> None:
        """`error: <message>` under `pre_cutover`; under `private` only a fixed code."""
        text = message if not self.private else _code(code, ERROR_CODES)
        print(f"error: {text}", file=self.err)

    def internal_error(self) -> None:
        print(f"error: {'internal-error'}", file=self.err)

    def note(self, text: str) -> None:
        """A fixed, publisher-authored line (no interpolated value)."""
        print(text, file=self.err)

    def acting_identity(self, identity: str) -> None:
        shown = identity if not self.private else _identity(identity)
        print(f"acting identity: {shown} (GitHub App installation tokens only; no personal identity is used)", file=self.err)

    def sweep(self, report: SweepReport) -> None:
        if not self.private:
            for outcome in report.outcomes:
                if outcome.status in (REFUSED, FAILED):
                    # the workflow log is public: status, ref and gate only, never the refusal detail (it can quote record content)
                    print(f"{outcome.status}: {outcome.ref}: [{outcome.gate or 'step'}]", file=self.err)
            if report.aborted:
                print(f"aborted: {report.aborted}", file=self.err)
            print(json.dumps(report.as_dict(), indent=2, sort_keys=True), file=self.out)
            return
        view = sweep_view(report, self.manifest)
        for run in view["runs"]:
            if run["status"] in (REFUSED, FAILED):
                print(f"{run['status']}: {run['ref']}: [{run['gate']}]", file=self.err)
        if view["aborted"]:
            print(f"aborted: {view['aborted']}", file=self.err)
        print(json.dumps(view, indent=2, sort_keys=True), file=self.out)

    def watchdog(self, report: WatchdogReport) -> None:
        if not self.private:
            if report.aborted:
                print(f"aborted: {report.aborted}", file=self.err)
            print(json.dumps(report.as_dict(), indent=2, sort_keys=True), file=self.out)
            return
        view = watchdog_view(report, self.manifest)
        if view["aborted"]:
            print(f"aborted: {view['aborted']}", file=self.err)
        print(json.dumps(view, indent=2, sort_keys=True), file=self.out)
