#!/usr/bin/env python3
"""Documentation-contract checks for the repository-intelligence model
(Issue #129).

Pins docs/repository-intelligence/repository-intelligence-model.md, its
navigational README, the reference-only (named, not linked) mentions in
the packaged repository-expansion.md and evidence.md, and the wiring into
the architecture map. Structural prose checks in the same style as
test_context_evidence_docs.py — semantic structure and whitespace-
normalized prose, not brittle exact whitespace.

Run with:
    python3 -m unittest tests.policy.test_repository_intelligence_docs
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

DOCDIR = REPO_ROOT / "docs" / "repository-intelligence"
MODEL = DOCDIR / "repository-intelligence-model.md"
DIR_README = DOCDIR / "README.md"
SHARED_EXPANSION = REPO_ROOT / "shared" / "policies" / "repository-expansion.md"
SHARED_EVIDENCE = REPO_ROOT / "shared" / "policies" / "evidence.md"
FINDING = REPO_ROOT / "shared" / "templates" / "finding.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "repository_intelligence.py"
BOUNDARY = REPO_ROOT / "tests" / "integration" / "test_packaging_runtime_boundary.py"
CORPUS_README = (
    REPO_ROOT
    / "docs"
    / "benchmark"
    / "corpus"
    / "repository-intelligence"
    / "README.md"
)

ENTITY_KINDS = ("file", "module", "class", "function", "symbol")
RELATIONSHIP_KINDS = ("calls", "implements", "references", "imports")
TRIGGERS = (
    "call_site",
    "interface_contract",
    "migration_schema",
    "config_consumer",
)


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class DesignRecordExistsAndIsTypedTests(unittest.TestCase):
    def test_docs_exist(self) -> None:
        self.assertTrue(MODEL.is_file())
        self.assertTrue(DIR_README.is_file())

    def test_every_entity_and_relationship_kind_appears(self) -> None:
        t = _norm(MODEL)
        for name in ENTITY_KINDS + RELATIONSHIP_KINDS + TRIGGERS:
            self.assertIn(name, t, f"{name} missing from the model")

    def test_candidate_architectures_are_compared(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Candidate architectures compared", t)
        self.assertIn("GraphRAG", t)
        self.assertIn("Rejected", t)
        self.assertIn("Recommended", t)

    def test_retrieval_bound_reuses_the_87_ring_ceiling_without_loosening_it(
        self,
    ) -> None:
        t = _norm(MODEL)
        self.assertIn("Retrieval bounds", t)
        self.assertIn("never re-derives or loosens", t)
        self.assertIn("standard", t)
        self.assertIn("elevated", t)
        self.assertIn("deep", t)

    def test_snapshot_staleness_is_reject_and_rebuild_not_a_soft_warning(
        self,
    ) -> None:
        t = _norm(MODEL)
        self.assertIn("Snapshot identity and staleness", t)
        self.assertIn("rejected and discarded outright", t)
        self.assertIn("never silently continues", t)
        self.assertIn(
            "Git / the current worktree remains the sole source of truth", t
        )

    def test_relationship_influence_attribution_states_the_four_rules(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Relationship-influence attribution", t)
        self.assertIn("influential_relationships", t)
        self.assertIn("not a general-purpose algorithm", t)
        self.assertIn("retains its provenance", t)
        self.assertIn(
            "Retrieving more context must never, by itself, inflate what "
            "counts as influential",
            t,
        )
        self.assertIn(
            "can never appear in influential_relationships and can never "
            "support a finding",
            t,
        )

    def test_safe_behavior_section_covers_ambiguity_missing_data_and_language(
        self,
    ) -> None:
        t = _norm(MODEL)
        self.assertIn(
            "Safe behavior for ambiguity, missing data, and unsupported languages",
            t,
        )
        self.assertIn("insufficient evidence", t)
        self.assertIn("never an invented relationship", t)

    def test_all_five_worked_examples_are_present(self) -> None:
        t = _norm(MODEL)
        for n in range(1, 6):
            self.assertIn(f"Worked example {n}", t)
        self.assertIn("Python", t)
        self.assertIn("TypeScript", t)

    def test_smallest_useful_first_implementation_defers_the_packaged_field(
        self,
    ) -> None:
        t = _norm(MODEL)
        self.assertIn("Smallest useful first implementation", t)
        self.assertIn(
            "a packaged finding-template field carrying influential_relationships",
            t,
        )
        self.assertIn("explicitly deferred to a later, separately-scoped", t)

    def test_runtime_boundary_is_stated(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Runtime boundary", t)
        self.assertIn("No code in this repository builds, persists, or queries", t)


class NotPackagedTests(unittest.TestCase):
    def test_model_declares_itself_not_packaged(self) -> None:
        self.assertIn("Not packaged", MODEL.read_text(encoding="utf-8"))
        self.assertIn("no packaged Skill resource depends on them", _norm(DIR_README))

    def test_reference_module_is_test_only(self) -> None:
        head = REFERENCE.read_text(encoding="utf-8")[:900]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_reference_module_registered_in_packaging_boundary(self) -> None:
        self.assertIn(
            '"repository_intelligence.py"', BOUNDARY.read_text(encoding="utf-8")
        )

    def test_finding_template_gets_no_new_field(self) -> None:
        # #129 introduces no packaged finding field — confirm the finding
        # template does not mention this model's attribution vocabulary.
        t = FINDING.read_text(encoding="utf-8")
        self.assertNotIn("influential_relationships", t)
        self.assertNotIn("repository-intelligence", t.lower())


class SharedPolicyReferencesAreLinkLevelTests(unittest.TestCase):
    def test_repository_expansion_names_the_model_without_duplicating_it(
        self,
    ) -> None:
        t = _norm(SHARED_EXPANSION)
        self.assertIn("repository-intelligence model", t.lower())
        self.assertIn(
            "without re-deriving or loosening this policy's ring ceiling", t
        )
        # no entity/relationship table duplicated into packaged policy
        self.assertNotIn("ALLOWED_KIND_TRIGGER_PAIRS", t)
        self.assertNotIn("influential_relationships", t)

    def test_evidence_names_the_model_without_duplicating_it(self) -> None:
        t = _norm(SHARED_EVIDENCE)
        self.assertIn("repository-intelligence model", t.lower())
        self.assertNotIn("influential_relationships", t)

    def test_shared_files_do_not_markdown_link_into_docs(self) -> None:
        for path in (SHARED_EXPANSION, SHARED_EVIDENCE, FINDING):
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("](../../docs/", raw, path.name)
            self.assertNotIn("](../../../docs/", raw, path.name)

    def test_shared_files_name_it_as_a_repository_development_document(
        self,
    ) -> None:
        for path in (SHARED_EXPANSION, SHARED_EVIDENCE):
            t = _norm(path)
            self.assertIn(
                "not a packaged resource, so it is named here, not linked", t
            )


class WiringTests(unittest.TestCase):
    def test_architecture_references_the_new_directory(self) -> None:
        t = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIn(
            "repository-intelligence/repository-intelligence-model.md", t
        )
        self.assertIn("repository-intelligence/README.md", t)
        norm = _norm(ARCHITECTURE)
        self.assertIn("repository-intelligence model", norm.lower())

    def test_architecture_future_work_states_no_runtime_retrieval(self) -> None:
        t = _norm(ARCHITECTURE)
        self.assertIn(
            "no code in this repository builds, persists, or queries a "
            "repository graph",
            t.lower(),
        )
        self.assertIn("no runtime retrieves entities or relationships", t)


class BenchmarkCorpusWiringTests(unittest.TestCase):
    def test_corpus_readme_exists_and_links_the_model(self) -> None:
        self.assertTrue(CORPUS_README.is_file())
        t = CORPUS_README.read_text(encoding="utf-8")
        self.assertIn("repository-intelligence-model.md", t)


class LinksResolveTests(unittest.TestCase):
    def test_every_relative_markdown_link_in_the_new_docs_resolves(self) -> None:
        link_re = re.compile(r"\]\((?!https?://|#)([^)]+)\)")
        broken: list[str] = []
        for md in (MODEL, DIR_README, CORPUS_README):
            base = md.parent
            for target in link_re.findall(md.read_text(encoding="utf-8")):
                path_part = target.split("#", 1)[0]
                if not path_part:
                    continue
                if not (base / path_part).resolve().exists():
                    broken.append(f"{md.name} -> {target}")
        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()
