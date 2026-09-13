#!/usr/bin/env python3
"""Documentation-contract checks for the finding-confidence model (Issue #178).

Pins docs/finding-confidence/finding-confidence-model.md, its navigational
README, the unified `confidence` finding field on the shared finding
template and its rendering, the expectations marker, and the wiring into the
architecture map, the runtime-validation feature guide, and the
contextual-evidence model. Structural / whitespace-normalized prose checks,
in the same style as test_context_evidence_docs.py.

Run with:
    python3 -m unittest tests.policy.test_finding_confidence_docs
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

DOCDIR = REPO_ROOT / "docs" / "finding-confidence"
MODEL = DOCDIR / "finding-confidence-model.md"
DIR_README = DOCDIR / "README.md"
FINDING = REPO_ROOT / "shared" / "templates" / "finding.md"
FINDING_RENDERING = REPO_ROOT / "shared" / "templates" / "finding-rendering.md"
REVIEW_SUMMARY = REPO_ROOT / "shared" / "templates" / "review-summary.md"
RUNTIME_VALIDATION = REPO_ROOT / "shared" / "policies" / "runtime-validation.md"
CONTEXT_MODEL = REPO_ROOT / "docs" / "review-context" / "contextual-evidence-model.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
FEATURE = REPO_ROOT / "docs" / "features" / "runtime-validation.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "review" / "finding_confidence.py"
BOUNDARY = REPO_ROOT / "tests" / "integration" / "packaging" / "_shared.py"
EXPECTATIONS = REPO_ROOT / "scripts" / "skill_metadata" / "expectations.py"

VALUES = (
    "confirmed",
    "credible",
    "runtime-validation-unavailable",
    "external-contract-unvalidated",
    "insufficient-context",
)


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class DesignRecordExistsTests(unittest.TestCase):
    def test_docs_exist(self) -> None:
        self.assertTrue(MODEL.is_file())
        self.assertTrue(DIR_README.is_file())

    def test_model_declares_itself_not_packaged(self) -> None:
        self.assertIn("Not packaged", MODEL.read_text(encoding="utf-8"))
        self.assertIn("no packaged Skill resource depends on them", _norm(DIR_README))

    def test_every_value_and_its_entry_criteria_are_documented(self) -> None:
        t = _norm(MODEL)
        self.assertIn("The closed value set", t)
        self.assertIn("The set is closed", t)
        for value in VALUES:
            self.assertIn(value, t, f"value {value} missing from the model")
        self.assertIn("Entry criteria", t)

    def test_no_numeric_probability_scoring(self) -> None:
        t = _norm(MODEL)
        self.assertIn("never a probability score", t)
        self.assertIn("AI confidence %", t)
        self.assertIn("It is a label", t)

    def test_reconciliation_maps_128_and_118_onto_one_field(self) -> None:
        t = _norm(MODEL)
        self.assertIn("one field, not three overlapping ones", t.lower())
        self.assertIn("Mapping table", t)
        # the concrete #128 state names roll up as documented
        self.assertIn("runtime validation = runtime-confirmed | confirmed", t)
        self.assertIn(
            "runtime validation = attempted-inconclusive | runtime-validation-unavailable",
            t,
        )
        self.assertIn("reasoned (default) | no contribution", t)
        # the #118 authoritative/informational typing rolls in, not a 2nd field
        self.assertIn("authoritative contextual source is the proof of a violation", t)
        self.assertIn("informational contextual source | no contribution", t)

    def test_deterministic_derivation_order_is_stated(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Deterministic derivation order", t)
        self.assertIn("first match in this order", t)
        self.assertIn("confirmed always wins", t)
        self.assertIn("credible is the floor and the tie-break", t)

    def test_default_is_credible_and_never_absent(self) -> None:
        t = _norm(MODEL)
        self.assertIn("the value is credible", t)
        self.assertIn("never emitted with an absent or unknown confidence", t.lower())

    def test_non_weakening_invariant_is_explicit(self) -> None:
        t = _norm(MODEL)
        self.assertIn(
            "Confidence never lowers the bar, the severity, or the decision", t
        )
        self.assertIn("The evidence bar is unchanged", t)
        self.assertIn("never a licence to report one that has not", t)
        self.assertIn(
            "insufficient-context in particular never converts a speculative hunch",
            t,
        )
        self.assertIn("Severity is unchanged", t)
        self.assertIn("confirmed does not escalate a P2", t)
        self.assertIn("The decision is unchanged", t)
        self.assertIn("never reads confidence", t)
        self.assertIn("Identity is unchanged", t)

    def test_output_section_covers_machine_and_human_surfaces(self) -> None:
        t = _norm(MODEL)
        self.assertIn("required field of the #67", t)
        self.assertIn("renders on the finding only when it is not the credible default", t)

    def test_human_line_is_suppressed_when_redundant_with_runtime_validation(self) -> None:
        t = _norm(MODEL)
        self.assertIn(
            "omitted from human output when it would only repeat a Runtime "
            "validation line already shown",
            t,
        )
        # but not when it adds something the runtime line does not
        self.assertIn(
            "a confirmed established by static or contextual evidence, "
            "external-contract-unvalidated, or insufficient-context",
            t,
        )
        # the machine schema is unaffected
        self.assertIn("always carried there, regardless of the human-surface suppression", t)

    def test_non_goals_and_smallest_first_slice(self) -> None:
        t = _norm(MODEL)
        self.assertIn("Non-goals", t)
        self.assertIn("No numeric probability", t)
        self.assertIn("Smallest useful first implementation", t)
        self.assertIn("One packaged field", t)


class PackagedFindingFieldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = FINDING.read_text(encoding="utf-8")
        self.norm = _norm(FINDING)

    def test_finding_template_has_the_confidence_section(self) -> None:
        self.assertIn("## Confidence and evidence state", self.text)
        section = re.search(
            r"## Confidence and evidence state\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(section)
        body = re.sub(r"\s+", " ", section.group(1).replace("**", "").replace("`", ""))
        for value in VALUES:
            self.assertIn(value, body)
        self.assertIn("One field, not three", body)
        self.assertIn("When a Skill does not compute confidence, the value is credible", body)
        self.assertIn("It never lowers the bar, the severity, or the decision", body)
        self.assertIn("mechanical decision derivation never reads confidence", body)
        self.assertIn("Rendered only when the value is not the credible default", body)
        self.assertIn(
            "omitted from human output when it would only repeat a Runtime "
            "validation line already shown",
            body,
        )
        self.assertIn("machine-readable output always carries confidence", body)

    def test_confidence_is_an_optional_field_not_mandatory_core(self) -> None:
        opt = re.search(
            r"## Optional and surface-specific fields\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(opt)
        opt_body = re.sub(r"\s+", " ", opt.group(1).replace("**", "").replace("`", ""))
        self.assertIn("confidence", opt_body)
        self.assertIn("Rendered only when it is not the credible default", opt_body)
        # not added to the mandatory-core question
        self.assertIn("What? Where? Evidence? Impact? Fix?", self.norm)
        self.assertNotIn("What? Where? Evidence? Confidence", self.norm)

    def test_rules_bullet_names_the_value_set_and_non_weakening_rule(self) -> None:
        rules = re.search(r"## Rules\n(.*?)\Z", self.text, re.S)
        self.assertIsNotNone(rules)
        body = re.sub(r"\s+", " ", rules.group(1).replace("**", "").replace("`", ""))
        self.assertIn("the confidence field records the finding's one unified evidence-state value", body)
        self.assertIn("never lowers the evidence bar for reporting", body)

    def test_provenance_sections_defer_the_epistemic_rollup_to_confidence(self) -> None:
        rt = re.search(
            r"## Runtime validation state and provenance\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(rt)
        self.assertIn("The epistemic roll-up is `confidence`", rt.group(1))
        cx = re.search(
            r"## Contextual evidence and provenance\n(.*?)\n## ", self.text, re.S
        )
        self.assertIsNotNone(cx)
        self.assertIn("The epistemic roll-up is `confidence`", cx.group(1))

    def test_rendering_exemplar_shows_the_optional_line_after_evidence(self) -> None:
        text = FINDING_RENDERING.read_text(encoding="utf-8")
        self.assertIn("**Confidence:**", text)
        variant = next(
            b
            for b in re.findall(r"```markdown\n(.*?)\n```", text, re.S)
            if "**Confidence:**" in b
        )
        self.assertLess(
            variant.index("**Evidence:**"), variant.index("**Confidence:**")
        )
        self.assertLess(
            variant.index("**Confidence:**"), variant.index("**Impact:**")
        )
        norm = _norm(FINDING_RENDERING)
        self.assertIn("credible default is never rendered", norm)
        self.assertIn("on the inline surface it folds into the Evidence: prose", norm)
        self.assertIn(
            "not merely the roll-up of a Runtime validation line already shown", norm
        )
        self.assertIn(
            "is not already conveyed by a shown Runtime validation line", norm
        )

    def test_review_summary_notes_confidence_is_presentation_only(self) -> None:
        self.assertIn(
            "rolls up, together with any contextual-evidence provenance, "
            "into the finding's single confidence value",
            _norm(REVIEW_SUMMARY),
        )

    def test_expectations_marker_is_registered(self) -> None:
        self.assertIn(
            '"## Confidence and evidence state"',
            EXPECTATIONS.read_text(encoding="utf-8"),
        )


class SharedPolicyReferencesAreLinkLevelTests(unittest.TestCase):
    def test_runtime_validation_names_the_model_without_duplicating_it(self) -> None:
        t = _norm(RUNTIME_VALIDATION)
        self.assertIn("finding-confidence model", t.lower())
        self.assertIn("runtime-confirmed rolls up as confirmed", t)
        # no value-set table copied into packaged policy
        self.assertNotIn("Mapping table", t)
        self.assertNotIn("Deterministic derivation order", t)

    def test_shared_files_do_not_markdown_link_into_docs(self) -> None:
        for path in (FINDING, FINDING_RENDERING, REVIEW_SUMMARY, RUNTIME_VALIDATION):
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("](../../docs/", raw, path.name)
            self.assertNotIn("](../../../docs/", raw, path.name)
            self.assertNotIn("finding-confidence/finding-confidence-model.md)", raw, path.name)


class ReferenceModuleTests(unittest.TestCase):
    def test_reference_module_is_test_only(self) -> None:
        head = REFERENCE.read_text(encoding="utf-8")[:600]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_reference_module_registered_in_packaging_boundary(self) -> None:
        self.assertIn('"finding_confidence.py"', BOUNDARY.read_text(encoding="utf-8"))


class WiringTests(unittest.TestCase):
    def test_architecture_references_the_new_directory(self) -> None:
        t = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIn("finding-confidence/finding-confidence-model.md", t)
        self.assertIn("finding-confidence/README.md", t)
        self.assertIn("Finding-confidence model", t)

    def test_architecture_future_work_still_names_the_67_schema_as_unbuilt(self) -> None:
        t = _norm(ARCHITECTURE)
        self.assertIn("Machine-readable review output schema", t)
        self.assertIn("still unbuilt", t)

    def test_feature_guide_mentions_the_unified_value(self) -> None:
        t = _norm(FEATURE)
        self.assertIn("rolls up into the finding's single confidence value", t)
        for value in VALUES:
            self.assertIn(value, t)

    def test_context_model_points_at_the_confidence_model(self) -> None:
        raw = CONTEXT_MODEL.read_text(encoding="utf-8")
        self.assertIn("finding-confidence/finding-confidence-model.md", raw)
        self.assertIn("machine-readable provenance block", _norm(CONTEXT_MODEL))


class LinksResolveTests(unittest.TestCase):
    def test_every_relative_markdown_link_in_the_new_docs_resolves(self) -> None:
        link_re = re.compile(r"\]\((?!https?://|#)([^)]+)\)")
        broken: list[str] = []
        for md in (MODEL, DIR_README):
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
