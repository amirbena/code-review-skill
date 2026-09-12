"""Guards the packaging boundary: the tests/reference/*.py reference modules
stay test-only and out of both Skill archives.

Fails if a refactor adds one to a package file list, makes a packaged file
import/invoke one, or lets a module's contract drift out of its packaged
policy. Archive-content checks need zip/unzip and skip explicitly otherwise.

Split (issue #217) into: manifest/path-safety (test_manifest_path_safety),
script parity (test_script_parity), hidden-runtime-dependency + disclaimer
prose (test_hidden_runtime_dependency), local-archive content
(test_local_archive_content), and github-archive content
(test_github_archive_content) — sharing constants and helpers in
_shared.py.
"""
