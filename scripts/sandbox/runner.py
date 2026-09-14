"""Sandbox runner: the single entry point for executing one admitted command.

reviewer -> runtime-validation request -> SandboxRunner.run() -> bounded evidence

Never falls back to unsandboxed host execution: if no isolation primitive is
available, or the run cannot be verified safe, the result is `unavailable`.
Contract: shared/policies/runtime-validation.md.
"""

from __future__ import annotations

from scripts.sandbox import capability, docker_runner, linux_bwrap, macos_seatbelt
from scripts.sandbox.boundary import Outcome, SandboxRequest, SandboxResult
from scripts.sandbox.process_exec import BoundedRunResult
from scripts.sandbox.workspace import prepare_workspace, verify_source_unchanged

_DISPATCH = {
    capability.Primitive.DOCKER: docker_runner.run,
    capability.Primitive.MACOS_SEATBELT: macos_seatbelt.run,
    capability.Primitive.LINUX_BWRAP: linux_bwrap.run,
}


def _to_sandbox_result(
    bounded: BoundedRunResult, primitive: str, source_verified: bool
) -> SandboxResult:
    if not source_verified:
        return SandboxResult(
            outcome=Outcome.FAILED,
            reason="reviewed source integrity check failed after execution",
            primitive=primitive,
            duration_seconds=bounded.duration_seconds,
        )
    if bounded.timed_out:
        return SandboxResult(
            outcome=Outcome.FAILED,
            reason="budget exceeded: wall-clock timeout",
            primitive=primitive,
            duration_seconds=bounded.duration_seconds,
        )
    if bounded.output_truncated:
        return SandboxResult(
            outcome=Outcome.FAILED,
            reason="budget exceeded: output limit",
            primitive=primitive,
            stdout=bounded.stdout,
            stderr=bounded.stderr,
            duration_seconds=bounded.duration_seconds,
            output_truncated=True,
        )
    if bounded.filesystem_growth_exceeded:
        return SandboxResult(
            outcome=Outcome.FAILED,
            reason="budget exceeded: filesystem growth limit",
            primitive=primitive,
            duration_seconds=bounded.duration_seconds,
        )
    outcome = Outcome.EXECUTED if bounded.exit_code == 0 else Outcome.FAILED
    return SandboxResult(
        outcome=outcome,
        exit_code=bounded.exit_code,
        stdout=bounded.stdout,
        stderr=bounded.stderr,
        primitive=primitive,
        duration_seconds=bounded.duration_seconds,
        source_integrity_verified=True,
    )


_AUTO_DETECT = object()


class SandboxRunner:
    """Executes exactly one admitted command inside a disposable boundary."""

    def __init__(self, primitive: capability.Primitive | None = _AUTO_DETECT) -> None:
        self._primitive = (
            capability.detect_primitive() if primitive is _AUTO_DETECT else primitive
        )

    @property
    def primitive(self) -> capability.Primitive | None:
        return self._primitive

    def run(self, request: SandboxRequest) -> SandboxResult:
        if self._primitive is None:
            return SandboxResult(
                outcome=Outcome.UNAVAILABLE,
                reason="no isolation primitive available on this host",
            )
        run_fn = _DISPATCH[self._primitive]

        workspace = prepare_workspace(request.source_dir)
        try:
            bounded = run_fn(request, workspace)
            verified = verify_source_unchanged(request.source_dir, workspace.source_fingerprint)
            return _to_sandbox_result(bounded, self._primitive.value, verified)
        except FileNotFoundError as exc:
            return SandboxResult(
                outcome=Outcome.UNAVAILABLE,
                reason=f"required sandbox executable missing: {exc}",
                primitive=self._primitive.value,
            )
        finally:
            workspace.teardown()
