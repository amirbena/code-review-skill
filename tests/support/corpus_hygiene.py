"""Shared corpus-hygiene checks for ``benchmark/corpus/*`` sub-corpora.

Every small fixture sub-corpus repeats the same generic shape checks: the
directory and README exist, the corpus stays small, every fixture parses and
validates through the single reference validator, ids match filenames and are
unique, each case records a rationale and tags and pins a consistent
decision, patch anchors occur in the diff/base, severities stay in P0/P1/P2,
and the README links every fixture and states its selection principle.

A corpus test module subclasses ``CorpusHygieneMixin`` alongside
``unittest.TestCase`` and sets the class attributes below. Each module keeps
its own ``TestCase`` subclass, so a failure names the owning module and
class; corpus-specific semantic assertions stay in that module.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from runtime_platform.benchmark.reference import benchmark_fixture as bf

_SEVERITIES = {"P0", "P1", "P2"}
_VALIDATOR_LINK = "](../../../runtime_platform/benchmark/reference/benchmark_fixture.py)"


def corpus_files(corpus_dir: Path) -> list[Path]:
    return sorted(corpus_dir.glob("*.yaml"))


def load_fixture(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _finding_specs(case):
    for finding in case.findings:
        yield from finding.members if finding.is_any_of else [finding]


class CorpusHygieneMixin:
    """Generic-shape checks parametrized by class attributes.

    Required: ``corpus_dir``, ``min_cases``, ``max_cases``, ``readme_refs``.
    Optional: ``readme_phrases`` (extra README substrings),
    ``validator_phrase`` (README disclaimer; ``None`` checks only the link),
    ``size_hint`` (appended to the size-ceiling failure message).
    """

    corpus_dir: Path
    min_cases: int
    max_cases: int
    readme_refs: tuple[str, ...]
    readme_phrases: tuple[str, ...] = ()
    validator_phrase: str | None = "never a second one"
    size_hint: str = ""

    def _files(self) -> list[Path]:
        return corpus_files(self.corpus_dir)

    def _cases(self) -> list[tuple[Path, object]]:
        return [(p, bf.parse_case(load_fixture(p))) for p in self._files()]

    def _readme(self) -> str:
        return (self.corpus_dir / "README.md").read_text(encoding="utf-8")

    def test_directory_exists_with_a_readme(self) -> None:
        self.assertTrue(self.corpus_dir.is_dir(), f"missing {self.corpus_dir}")
        self.assertTrue((self.corpus_dir / "README.md").is_file())

    def test_sub_corpus_is_small(self) -> None:
        n = len(self._files())
        self.assertGreaterEqual(
            n, self.min_cases, f"{n} fixtures; expected at least {self.min_cases}"
        )
        self.assertLessEqual(
            n,
            self.max_cases,
            f"{n} fixtures; expected at most {self.max_cases} {self.size_hint}".strip(),
        )

    def test_every_file_parses_and_validates(self) -> None:
        self.assertTrue(self._files(), f"no fixtures found in {self.corpus_dir}")
        for path in self._files():
            with self.subTest(case=path.name):
                self.assertEqual(
                    bf.parse_case(load_fixture(path)).format, "benchmark-case/v2"
                )

    def test_filename_stem_matches_case_id(self) -> None:
        for path, case in self._cases():
            with self.subTest(case=path.name):
                self.assertEqual(case.id, path.stem)

    def test_case_ids_are_unique(self) -> None:
        ids = [case.id for _, case in self._cases()]
        self.assertEqual(len(ids), len(set(ids)), "duplicate case id in sub-corpus")

    def test_every_case_records_a_rationale_and_tags(self) -> None:
        for path, case in self._cases():
            with self.subTest(case=path.name):
                rationale = case.metadata.get("rationale", "")
                self.assertTrue(
                    isinstance(rationale, str) and rationale.strip(),
                    "case-selection rationale must be recorded in metadata",
                )
                self.assertTrue(
                    case.metadata.get("tags"), "case must carry >=1 category tag"
                )

    def test_every_case_pins_an_explicit_consistent_decision(self) -> None:
        for path, case in self._cases():
            with self.subTest(case=path.name):
                self.assertIsNotNone(
                    case.decision, "cases state `decision` as a cross-check"
                )
                self.assertEqual(case.decision, case.derived_decision)

    def test_patch_case_anchors_occur_in_the_diff_or_base(self) -> None:
        for path, case in self._cases():
            if case.input_kind != "patch":
                continue
            patch = case.input["patch"]
            base_text = "\n".join((case.input.get("base") or {}).values())
            for spec in _finding_specs(case):
                locs = [spec.location, *(a.get("location") for a in spec.alternatives)]
                for loc in locs:
                    anchor = (loc or {}).get("anchor")
                    if anchor:
                        with self.subTest(case=path.name, anchor=anchor):
                            self.assertIn(anchor, patch + base_text)

    def test_no_finding_carries_a_severity_outside_p0_p1_p2(self) -> None:
        for path, case in self._cases():
            for spec in _finding_specs(case):
                for severity in spec.severities:
                    with self.subTest(case=path.name, severity=severity):
                        self.assertIn(severity, _SEVERITIES)

    def test_readme_links_every_fixture(self) -> None:
        raw = self._readme()
        for path in self._files():
            self.assertIn(f"]({path.name})", raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_scope(self) -> None:
        text = " ".join(self._readme().split())
        for needle in ("Selection principle", *self.readme_refs, *self.readme_phrases, "not** packaged"):
            self.assertIn(needle, text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        raw = self._readme()
        self.assertIn(_VALIDATOR_LINK, raw)
        if self.validator_phrase:
            self.assertIn(self.validator_phrase, " ".join(raw.split()))
