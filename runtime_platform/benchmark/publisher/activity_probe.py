"""The read-only X3 probe (ADR §12): origin attestation against the private evidence repository, with fixed-code results only."""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

from runtime_platform.benchmark.publisher import github_api
from runtime_platform.benchmark.publisher.ports import RefActivity, StagingRef
from runtime_platform.benchmark.publisher.validation import attest_origin

PROBE_REPOSITORY = "amirbena/code-review-skill-evidence"
# Built in two parts: the X1 ref is deliberately outside every registered evidence namespace.
PROBE_REF = "claude/x1" + "-20261010T152046Z"

ATTRIBUTED, REFUSED, REF_UNREADABLE, ACTIVITY_UNAVAILABLE = "attributed", "refused", "ref-unreadable", "activity-unavailable"
POSITIVE_CODES = frozenset({ATTRIBUTED, REFUSED, REF_UNREADABLE, ACTIVITY_UNAVAILABLE})
REJECTED, ACCEPTED = "rejected", "accepted"
NEGATIVE_CASES = ("wrong-actor", "missing-activity", "wrong-sha")
NEGATIVE_CODES = frozenset({REJECTED, ACCEPTED})
_SYNTHETIC_ACTOR, _SYNTHETIC_SHA, _OTHER_SHA = "x3-probe-synthetic-actor", "a" * 40, "b" * 40


class ProbeReader(Protocol):
    def ref_tip(self, ref_name: str) -> str | None: ...

    def ref_activities(self, ref_name: str) -> list[RefActivity] | None: ...


@dataclass(frozen=True)
class ProbeResult:
    positive: str
    negatives: dict[str, str]

    @property
    def passed(self) -> bool:
        return self.positive == ATTRIBUTED and all(code == REJECTED for code in self.negatives.values()) and set(self.negatives) == set(NEGATIVE_CASES)


class GitHubProbeReader:
    """GET requests only, addressed to `PROBE_REPOSITORY`; any failure is an unavailable answer, never an exception."""

    def __init__(self, token: str, *, opener: github_api.Opener = github_api.DEFAULT_OPENER) -> None:
        client = github_api.GitHubClient(token, opener=opener)
        self._client = client
        self._activity = github_api.GitHubHandoffReader(client, PROBE_REPOSITORY)

    def ref_tip(self, ref_name: str) -> str | None:
        try:
            _, ref = self._client.call(
                "GET", f"/repos/{PROBE_REPOSITORY}/git/ref/heads/{urllib.parse.quote(ref_name, safe='/')}", tolerate=(404,), auth_is_fatal=False
            )
            sha = (ref or {}).get("object", {}).get("sha")
        except Exception:  # noqa: BLE001 - nothing about the failure may reach a public log
            return None
        return sha if isinstance(sha, str) and len(sha) == 40 else None

    def ref_activities(self, ref_name: str) -> list[RefActivity] | None:
        try:
            return self._activity.ref_activities(ref_name)
        except Exception:  # noqa: BLE001
            return None


def _negative(refusal: object) -> str:
    return REJECTED if refusal is not None else ACCEPTED


def negative_cases(allowlist: Sequence[str]) -> dict[str, str]:
    """Synthetic inputs through the real gate, so the rejections hold whatever the live ref shows."""
    ref = StagingRef(PROBE_REF, _SYNTHETIC_SHA)
    wanted = f"refs/heads/{PROBE_REF}"
    wrong_actor = [RefActivity("branch_creation", wanted, _SYNTHETIC_ACTOR, _SYNTHETIC_SHA)]
    wrong_sha = [RefActivity("branch_creation", wanted, allowlist[0], _OTHER_SHA)]
    return {
        "wrong-actor": _negative(attest_origin(ref, wrong_actor, allowlist, accept_unattributed=False)),
        "missing-activity": _negative(attest_origin(ref, [], allowlist, accept_unattributed=False)),
        "wrong-sha": _negative(attest_origin(ref, wrong_sha, allowlist, accept_unattributed=False)),
    }


def run_probe(reader: ProbeReader, allowlist: Sequence[str]) -> ProbeResult:
    tip = reader.ref_tip(PROBE_REF)
    if tip is None:
        positive = REF_UNREADABLE
    else:
        activities = reader.ref_activities(PROBE_REF)
        if activities is None:
            positive = ACTIVITY_UNAVAILABLE
        else:
            refusal = attest_origin(StagingRef(PROBE_REF, tip), activities, allowlist, accept_unattributed=False)
            positive = ATTRIBUTED if refusal is None else REFUSED
    return ProbeResult(positive, negative_cases(allowlist))


ReaderFactory = Callable[[str], ProbeReader]
