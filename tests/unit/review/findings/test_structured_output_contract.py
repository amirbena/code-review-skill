#!/usr/bin/env python3
"""Cross-Skill contract tests for the structured review result (Issue #71).

Contract: docs/review-result/review-result-model.md section 8. Sample outputs
from both Skills must validate against the versioned schema, fail closed on
unversioned/unsupported/invalid results, keep shared fields identical across
Skills, and agree with the human report produced by the same review.

Run with:
    python3 -m unittest tests.unit.review.findings.test_structured_output_contract
"""

from __future__ import annotations

import copy
import json
import re
import unittest
from pathlib import Path

from tests.reference.review import finding_identity as fi
from tests.reference.review import review_result as rr
from tests.reference.review import structured_output_contract as soc
from tests.support.paths import REPO_ROOT

SAMPLES_DIR = Path(__file__).resolve().parent / "structured_output_samples"
MANIFEST = json.loads((SAMPLES_DIR / "manifest.json").read_text(encoding="utf-8"))
SAMPLES = {entry["file"]: entry for entry in MANIFEST["samples"]}
MODEL = REPO_ROOT / "docs" / "review-result" / "review-result-model.md"
LOCAL_POLICY = REPO_ROOT / "shared" / "policies" / "structured-output.md"
GITHUB_POLICY = REPO_ROOT / "skills" / "github-pr-review" / "policies" / "structured-output.md"


def _text(name: str) -> str:
    return (SAMPLES_DIR / name).read_text(encoding="utf-8")


def _split(name: str) -> soc.SplitOutput:
    return soc.split_output(_text(name), SAMPLES[name]["skill"])


def _with_result(text: str, result: object) -> str:
    body = json.dumps(result, indent=2)
    return re.sub(r"```json\n.*?\n```", lambda _m: f"```json\n{body}\n```", text, flags=re.S)


def _errors(name: str, text: str | None = None) -> tuple[str, ...]:
    entry = SAMPLES[name]
    return soc.contract_errors(
        _text(name) if text is None else text,
        entry["skill"],
        entry["known_head"],
        entry.get("target_committed", True),
    )


def _by_skill(skill: str) -> list[str]:
    return [name for name, entry in SAMPLES.items() if entry["skill"] == skill]


class SampleCorpusTests(unittest.TestCase):
    def test_manifest_lists_every_sample_on_disk(self) -> None:
        on_disk = {p.relative_to(SAMPLES_DIR).as_posix() for p in SAMPLES_DIR.rglob("*.md")}
        self.assertEqual(on_disk, set(SAMPLES))

    def test_each_skill_covers_every_outcome(self) -> None:
        for skill in soc.SKILLS:
            outcomes = {_split(name).result["decision"]["outcome"] for name in _by_skill(skill)}
            with self.subTest(skill=skill):
                self.assertEqual(outcomes, {"clean", "blocking", "incomplete"})

    def test_sample_file_skill_matches_its_directory(self) -> None:
        for name, entry in SAMPLES.items():
            with self.subTest(sample=name):
                self.assertEqual(name.split("/", 1)[0], entry["skill"])


class SchemaConformanceTests(unittest.TestCase):
    def test_every_sample_honors_the_contract(self) -> None:
        for name in SAMPLES:
            with self.subTest(sample=name):
                self.assertEqual(_errors(name), ())

    def test_every_sample_carries_the_published_version(self) -> None:
        for name in SAMPLES:
            with self.subTest(sample=name):
                self.assertEqual(_split(name).result["schema_version"], rr.SCHEMA_VERSION)

    def test_identities_are_the_canonical_minted_values(self) -> None:
        for name, entry in SAMPLES.items():
            findings = {f["id"]: f["identity"] for f in _split(name).result["findings"]}
            self.assertEqual(set(findings), set(entry["findings"]), name)
            for finding_id, key in entry["findings"].items():
                descriptor = fi.build_descriptor(**MANIFEST["identity_inputs"][key])
                with self.subTest(sample=name, finding=finding_id):
                    self.assertEqual(findings[finding_id]["stable_id"], fi.mint_identity(descriptor))
                    self.assertEqual(findings[finding_id]["matching_eligible"], fi.is_matchable(descriptor))

    def test_fabricated_identity_is_invisible_to_output_checks(self) -> None:
        # Boundary: the descriptor is not in the result, so only live runs can
        # show an unminted stable_id (#529, not these checks).
        name = "local-code-review/blocking-committed.md"
        result = copy.deepcopy(_split(name).result)
        for finding in result["findings"]:
            finding["identity"]["stable_id"] = "fid_v1_" + "0" * 32
        self.assertEqual(_errors(name, _with_result(_text(name), result)), ())


class FailClosedTests(unittest.TestCase):
    """schema-versioning.md section 3: nothing is consumed from an unsupported result."""

    NAME = "github-pr-review/blocking.md"

    def _mutated(self, mutate) -> tuple[str, ...]:
        result = copy.deepcopy(_split(self.NAME).result)
        mutate(result)
        return _errors(self.NAME, _with_result(_text(self.NAME), result))

    def assertFails(self, mutate, fragment: str) -> None:
        errors = self._mutated(mutate)
        self.assertTrue(any(fragment in e for e in errors), f"{fragment!r} not in {errors}")

    def test_unversioned_result(self) -> None:
        self.assertFails(lambda r: r.pop("schema_version"), "missing or not MAJOR.MINOR.PATCH")

    def test_malformed_versions(self) -> None:
        for bad in ("1.0", "v1.0.0", "1.0.0-rc1", 1, None):
            with self.subTest(version=bad):
                self.assertFails(lambda r, v=bad: r.update(schema_version=v), "missing or not MAJOR.MINOR.PATCH")

    def test_unsupported_major(self) -> None:
        for bad in ("2.0.0", "0.9.0"):
            with self.subTest(version=bad):
                self.assertFails(lambda r, v=bad: r.update(schema_version=v), "unsupported major")

    def test_newer_minor_than_the_published_schema(self) -> None:
        self.assertFails(lambda r: r.update(schema_version="1.1.0"), "newer than the published schema")

    def test_unpublished_patch_is_schema_invalid(self) -> None:
        self.assertFails(lambda r: r.update(schema_version="1.0.1"), "$.schema_version")

    def test_schema_invalid_result(self) -> None:
        self.assertFails(lambda r: r.update(verdict="ok"), "unexpected property 'verdict'")
        self.assertFails(lambda r: r["findings"][0].pop("identity"), "missing required property 'identity'")

    def test_owner_inconsistent_result(self) -> None:
        self.assertFails(lambda r: r["counts"].update(p2=0), "$.counts")

    def test_result_that_is_not_an_object(self) -> None:
        errors = _errors(self.NAME, _with_result(_text(self.NAME), [1, 2]))
        self.assertEqual(errors, ("$: structured result is not a JSON object",))

    def test_unparseable_json(self) -> None:
        text = _text(self.NAME).replace('"schema_version"', "schema_version", 1)
        self.assertIn("not valid JSON", _errors(self.NAME, text)[0])

    def test_missing_block_without_a_not_emitted_statement(self) -> None:
        text = re.sub(r"```json\n.*?\n```\n", "", _text(self.NAME), flags=re.S)
        self.assertIn("no structured result block", _errors(self.NAME, text)[0])

    def test_second_json_block(self) -> None:
        text = _text(self.NAME)
        block = re.search(r"```json\n.*?\n```\n", text, re.S).group(0)
        self.assertIn("exactly one json block", _errors(self.NAME, text + "\n" + block)[0])

    def test_content_after_the_block(self) -> None:
        self.assertIn("must be the last part", _errors(self.NAME, _text(self.NAME) + "\nTrailing prose.\n")[0])

    def test_local_result_needs_its_heading(self) -> None:
        name = "local-code-review/blocking-committed.md"
        text = _text(name).replace(soc.STRUCTURED_HEADING, "### Machine Output")
        self.assertIn(soc.STRUCTURED_HEADING, _errors(name, text)[0])

    def test_not_emitted_statement_is_recognized_but_not_a_result(self) -> None:
        name = "local-code-review/blocking-committed.md"
        text = _text(name).split(soc.STRUCTURED_HEADING, 1)[0]
        text += f"{soc.NOT_EMITTED_PREFIX} verdict-consistency check withheld the report\n"
        split = soc.split_output(text, soc.LOCAL)
        self.assertIsNone(split.result)
        self.assertEqual(split.not_emitted_reason, "verdict-consistency check withheld the report")
        self.assertEqual(_errors(name, text), ("structured result was not emitted",))


class SurfacePopulationTests(unittest.TestCase):
    def _state_errors(self, name: str, **state) -> tuple[str, ...]:
        entry = SAMPLES[name]
        result = copy.deepcopy(_split(name).result)
        result["reviewed_state"].update(state)
        return soc.surface_errors(result, entry["skill"], entry["known_head"], entry.get("target_committed", True))

    def test_local_uncommitted_target_never_claims_a_head(self) -> None:
        name = "local-code-review/clean-p2-uncommitted.md"
        self.assertTrue(self._state_errors(name, reviewed_head_sha=SAMPLES[name]["known_head"]))

    def test_local_committed_head_is_the_workspace_head(self) -> None:
        name = "local-code-review/blocking-committed.md"
        self.assertTrue(self._state_errors(name, reviewed_head_sha="a" * 40))
        self.assertTrue(self._state_errors(name, reviewed_head_sha=None))

    def test_local_review_is_full_and_stateless(self) -> None:
        name = "local-code-review/blocking-committed.md"
        self.assertTrue(self._state_errors(name, completeness="delta-re-review"))
        self.assertTrue(self._state_errors(name, prior_reviewed_sha="a" * 40))

    def test_github_head_is_the_pr_head(self) -> None:
        self.assertTrue(self._state_errors("github-pr-review/blocking.md", reviewed_head_sha="a" * 40))

    def test_github_null_head_only_when_incomplete(self) -> None:
        self.assertTrue(self._state_errors("github-pr-review/blocking.md", reviewed_head_sha=None))
        self.assertEqual(self._state_errors("github-pr-review/incomplete-head-unknown.md"), ())

    def test_skill_field_names_the_producer(self) -> None:
        result = copy.deepcopy(_split("github-pr-review/blocking.md").result)
        result["skill"] = soc.LOCAL
        self.assertTrue(soc.surface_errors(result, soc.GITHUB, result["reviewed_state"]["reviewed_head_sha"]))


class CrossSkillParityTests(unittest.TestCase):
    def _groups(self) -> dict[str, dict[str, str]]:
        groups: dict[str, dict[str, str]] = {}
        for name, entry in SAMPLES.items():
            if "parity_group" in entry:
                groups.setdefault(entry["parity_group"], {})[entry["skill"]] = name
        return groups

    def test_every_group_pairs_both_skills(self) -> None:
        groups = self._groups()
        self.assertTrue(groups)
        for group, members in groups.items():
            with self.subTest(group=group):
                self.assertEqual(set(members), set(soc.SKILLS))

    def test_shared_fields_are_identical_for_the_same_review(self) -> None:
        for group, members in self._groups().items():
            local, github = (_split(members[s]).result for s in soc.SKILLS)
            with self.subTest(group=group):
                self.assertEqual(soc.shared_projection(local), soc.shared_projection(github))

    def test_only_declared_surface_fields_differ(self) -> None:
        for group, members in self._groups().items():
            local, github = (_split(members[s]).result for s in soc.SKILLS)
            differing = {key for key in local if local[key] != github[key]}
            with self.subTest(group=group):
                self.assertLessEqual(differing, set(soc.SURFACE_SPECIFIC_FIELDS))
                self.assertEqual(set(local["reviewed_state"]), set(github["reviewed_state"]))

    def test_surface_fields_are_schema_fields(self) -> None:
        self.assertLessEqual(set(soc.SURFACE_SPECIFIC_FIELDS), set(rr.load_schema()["required"]))

    def test_projection_detects_a_shared_field_drift(self) -> None:
        local = _split("local-code-review/blocking-committed.md").result
        github = copy.deepcopy(_split("github-pr-review/blocking.md").result)
        github["findings"][0]["confidence"] = "confirmed"
        self.assertNotEqual(soc.shared_projection(local), soc.shared_projection(github))

    def test_decision_renderings_match_the_model_and_both_policies(self) -> None:
        model = MODEL.read_text(encoding="utf-8").split("## 4. Decision codes", 1)[1].split("## 5.", 1)[0]
        rows = re.findall(r"^\| `(\w+)`(?: \(outcome only\))? \| `([A-Z ]+)` \| `([A-Za-z ]+)` \|", model, re.M)
        self.assertEqual({code for code, _l, _g in rows}, {"clean", "blocking", "incomplete"})
        local_policy = " ".join(LOCAL_POLICY.read_text(encoding="utf-8").split())
        github_policy = GITHUB_POLICY.read_text(encoding="utf-8")
        for code, local_label, github_label in rows:
            with self.subTest(code=code):
                self.assertEqual(soc.RENDERED_OUTCOME[soc.LOCAL][local_label.upper()], code)
                self.assertEqual(soc.RENDERED_OUTCOME[soc.GITHUB][github_label.upper()], code)
                self.assertIn(f"`{code}` → `{local_label}`", local_policy)
                self.assertRegex(github_policy, rf"\| `{code}`(?: \(outcome only\))? \| `{github_label}`")

    def test_both_policies_emit_the_published_version(self) -> None:
        for policy in (LOCAL_POLICY, GITHUB_POLICY):
            with self.subTest(policy=policy.parent.parent.name):
                self.assertIn(f'"schema_version": "{rr.SCHEMA_VERSION}"', policy.read_text(encoding="utf-8"))


class ReportAgreementTests(unittest.TestCase):
    """The comparator reads rendered facts; it never re-derives the decision."""

    def _agreement(self, name: str, human: str | None = None, result: dict | None = None) -> tuple[str, ...]:
        split = _split(name)
        skill = SAMPLES[name]["skill"]
        report = soc.parse_human_report(split.human if human is None else human, skill)
        return soc.agreement_errors(report, split.result if result is None else result, skill)

    def assertDisagrees(self, errors: tuple[str, ...], fragment: str) -> None:
        self.assertTrue(any(e.startswith(fragment) for e in errors), f"{fragment!r} not in {errors}")

    def test_every_sample_agrees(self) -> None:
        for name in SAMPLES:
            with self.subTest(sample=name):
                self.assertEqual(self._agreement(name), ())

    def test_flipped_rendered_decision(self) -> None:
        flips = {
            "local-code-review/blocking-committed.md": ("**CHANGES REQUIRED**", "**REVIEW CLEAN**"),
            "github-pr-review/blocking.md": ("**REQUEST CHANGES**", "**APPROVE**"),
            "local-code-review/incomplete.md": ("**REVIEW INCOMPLETE**", "**CHANGES REQUIRED**"),
            "github-pr-review/clean-p2-delta.md": ("**APPROVE**", "**REVIEW INCOMPLETE**"),
        }
        for name, (old, new) in flips.items():
            with self.subTest(sample=name):
                self.assertDisagrees(self._agreement(name, human=_split(name).human.replace(old, new)), "decision")

    def test_other_skill_label_is_not_recognized_locally(self) -> None:
        name = "local-code-review/blocking-committed.md"
        human = _split(name).human.replace("**CHANGES REQUIRED**", "**REQUEST CHANGES**")
        self.assertDisagrees(self._agreement(name, human=human), "human report: unrecognized")

    def test_github_self_review_label_maps_to_the_same_outcome(self) -> None:
        name = "github-pr-review/blocking.md"
        human = _split(name).human.replace(
            "**REQUEST CHANGES**", "**CHANGES REQUIRED** — GitHub review mutation withheld: reviewer is the PR author"
        )
        self.assertEqual(self._agreement(name, human=human), ())

    def test_counts_disagree(self) -> None:
        for name, old, new in (
            ("local-code-review/blocking-committed.md", "- P0: 0, P1: 2, P2: 1", "- P0: 0, P1: 1, P2: 1"),
            ("github-pr-review/blocking.md", "- P1: 2", "- P1: 1"),
        ):
            with self.subTest(sample=name):
                self.assertDisagrees(self._agreement(name, human=_split(name).human.replace(old, new)), "counts")

    def test_finding_severity_or_title_disagrees(self) -> None:
        for name in ("local-code-review/blocking-committed.md", "github-pr-review/blocking.md"):
            for field, value in (("severity", "P0"), ("title", "Something else")):
                result = copy.deepcopy(_split(name).result)
                result["findings"][0][field] = value
                with self.subTest(sample=name, field=field):
                    self.assertDisagrees(self._agreement(name, result=result), "findings")

    def test_finding_missing_from_the_result(self) -> None:
        for name in ("local-code-review/clean-p2-uncommitted.md", "github-pr-review/clean-p2-delta.md"):
            result = copy.deepcopy(_split(name).result)
            result["findings"] = []
            with self.subTest(sample=name):
                self.assertDisagrees(self._agreement(name, result=result), "findings")

    def test_finding_id_disagrees(self) -> None:
        for name in ("local-code-review/blocking-committed.md", "github-pr-review/blocking.md"):
            result = copy.deepcopy(_split(name).result)
            result["findings"][1]["id"] = "F9"
            with self.subTest(sample=name):
                self.assertDisagrees(self._agreement(name, result=result), "finding id")

    def test_affected_locations_disagree(self) -> None:
        for name in ("local-code-review/blocking-committed.md", "github-pr-review/blocking.md"):
            result = copy.deepcopy(_split(name).result)
            result["findings"][1]["affected_locations"].pop()
            result["findings"][1]["affected_locations"].append({"location": "src/x.py:1", "note": "n"})
            with self.subTest(sample=name):
                self.assertDisagrees(self._agreement(name, result=result), "affected locations")

    def test_consolidated_finding_rendering_is_parsed(self) -> None:
        for name in ("local-code-review/blocking-committed.md", "github-pr-review/blocking.md"):
            report = soc.parse_human_report(_split(name).human, SAMPLES[name]["skill"])
            consolidated = next(f for f in report.findings if f.id == "F2")
            with self.subTest(sample=name):
                self.assertEqual(len(consolidated.affected_locations), 2)

    def test_local_order_disagrees(self) -> None:
        name = "local-code-review/blocking-committed.md"
        result = copy.deepcopy(_split(name).result)
        result["findings"].reverse()
        self.assertDisagrees(self._agreement(name, result=result), "findings: result order")

    def test_coverage_disagrees(self) -> None:
        name = "github-pr-review/clean-p2-delta.md"
        human = _split(name).human.replace("- coverage: `complete`", "- coverage: `incomplete — partition skipped`")
        self.assertDisagrees(self._agreement(name, human=human), "coverage")

    def test_reviewed_head_disagrees(self) -> None:
        for name in ("local-code-review/blocking-committed.md", "github-pr-review/blocking.md"):
            head = SAMPLES[name]["known_head"]
            with self.subTest(sample=name):
                self.assertDisagrees(self._agreement(name, human=_split(name).human.replace(head, "a" * 40)), "reviewed head")

    def test_human_voice_heading_is_parsed(self) -> None:
        name = "github-pr-review/blocking.md"
        human = _split(name).human.replace("#### F2 [P1] ", "#### F2 P1 (Blocking): ")
        self.assertEqual(self._agreement(name, human=human), ())

    def test_comparator_does_not_derive_the_decision(self) -> None:
        name = "github-pr-review/clean-p2-delta.md"
        result = copy.deepcopy(_split(name).result)
        result["findings"][0]["severity"] = "P1"
        result["counts"] = {"p0": 0, "p1": 1, "p2": 0}
        human = _split(name).human.replace("- **P2 — ", "- **P1 — ").replace("- P1: 0\n- P2: 1", "- P1: 1\n- P2: 0")
        self.assertEqual(self._agreement(name, human=human, result=result), ())
        self.assertTrue(any("$.decision.derived" in e for e in soc.producer_errors(result)))

    def test_comparison_is_deterministic(self) -> None:
        name = "github-pr-review/blocking.md"
        result = copy.deepcopy(_split(name).result)
        result["findings"][0]["title"] = "Other"
        self.assertEqual(self._agreement(name, result=result), self._agreement(name, result=result))


if __name__ == "__main__":
    unittest.main()
