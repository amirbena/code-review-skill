"""Shared structural skeleton for the benchmark design-record doc tests.

Each ``docs``-pinning module under ``tests/policy/benchmark/`` declares one
``BenchmarkDocSpec`` and subclasses ``BenchmarkDocContractMixin`` (the design
record itself) and ``BenchmarkDocNavigationMixin`` (README / ARCHITECTURE /
reference-module wiring) alongside ``unittest.TestCase``. Every module keeps its
own TestCase classes, so a failure names the doc's module and class. Each
doc's canonical-invariant text, section phrases, and doc-specific structural
tests stay in the owning module; only the identical skeleton lives here.

A module that has no counterpart for a navigation check disables it by
assigning ``None`` to the method name on its subclass (``unittest`` only
collects callables), instead of a skipped test.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tests.support.paths import REPO_ROOT

README = REPO_ROOT / "runtime_platform" / "benchmark" / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"


def _norm(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


@dataclass(frozen=True)
class Section:
    """A heading plus the doc-specific phrases pinned inside it."""

    heading: str
    raw: tuple[str, ...] = ()  # literal phrases anywhere in the raw doc
    text: tuple[str, ...] = ()  # whitespace-normalized phrases anywhere in the doc
    body: tuple[str, ...] = ()  # whitespace-normalized phrases after the heading


@dataclass(frozen=True)
class BenchmarkDocSpec:
    doc: Path
    issue_tokens: tuple[str, ...]
    invariant: str
    not_packaged: str = "repository-development doc: not packaged"
    sections: tuple[Section, ...] = ()
    status_heading: str = "## Status and canonical home"
    status_body: tuple[str, ...] = ()
    status_raw: tuple[str, ...] = ()
    # navigation
    readme_link: str = ""
    readme_issue: str = ""
    architecture_name: str = ""
    reference: Path | None = None
    reference_head_chars: int = 700
    unit_test: Path | None = None
    unit_import: str = ""
    unit_phrase: str = ""


class BenchmarkDocContractMixin:
    spec: BenchmarkDocSpec

    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = cls.spec.doc.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_is_repository_development_only_not_packaged(self) -> None:
        self.assertIn(self.spec.not_packaged, self.text)
        self.assertIn("no packaged Skill resource depends on it", self.text)

    def test_names_its_issue_and_its_neighbours(self) -> None:
        for token in self.spec.issue_tokens:
            self.assertIn(token, self.raw)

    def test_canonical_invariant_is_stated_verbatim(self) -> None:
        self.assertIn(self.spec.invariant, self.text)

    def test_declared_sections_pin_their_phrases(self) -> None:
        for section in self.spec.sections:
            with self.subTest(section=section.heading):
                self.assertIn(section.heading, self.raw)
                for phrase in section.raw:
                    self.assertIn(phrase, self.raw)
                for phrase in section.text:
                    self.assertIn(phrase, self.text)
                if section.body:
                    body = " ".join(self.raw.split(section.heading, 1)[1].split())
                    for phrase in section.body:
                        self.assertIn(phrase, body)

    def test_status_defers_to_an_eventual_canonical_home(self) -> None:
        tail = " ".join(self.raw.split(self.spec.status_heading, 1)[1].split())
        for phrase in self.spec.status_body:
            self.assertIn(phrase, tail)
        for phrase in self.spec.status_raw:
            self.assertIn(phrase, self.raw)


class BenchmarkDocNavigationMixin:
    spec: BenchmarkDocSpec

    def test_readme_maps_the_contract(self) -> None:
        raw = README.read_text(encoding="utf-8")
        self.assertIn(self.spec.readme_link, raw)
        self.assertIn(self.spec.readme_issue, raw)

    def test_architecture_mentions_the_contract(self) -> None:
        text = _norm(ARCHITECTURE)
        self.assertIn(self.spec.architecture_name, text)
        self.assertIn("nothing benchmark", text)

    def test_reference_module_is_declared_test_only(self) -> None:
        assert self.spec.reference is not None
        text = self.spec.reference.read_text(encoding="utf-8")
        head = " ".join(text[: self.spec.reference_head_chars].split())
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_unit_test_consumes_the_single_reference_module(self) -> None:
        assert self.spec.unit_test is not None
        raw = " ".join(self.spec.unit_test.read_text(encoding="utf-8").split())
        self.assertIn(self.spec.unit_import, raw)
        if self.spec.unit_phrase:
            self.assertIn(self.spec.unit_phrase, raw)
