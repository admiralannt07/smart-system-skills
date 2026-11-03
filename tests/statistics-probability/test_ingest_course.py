"""Workflow gates exercised with synthetic decks and synthetic reference records."""

import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_extract_pptx as fixtures


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("ingest_course", ROOT / "scripts/ingest_course.py")
workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ExtractionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.folder
        self.fixture.make_deck(fixtures.shape('<a:r><a:t>Two values: 2 and 4.</a:t></a:r>'))
        plan = self.root / "plan" / self.root.name
        plan.mkdir(parents=True)
        (plan / "SPEC.md").write_text('## 2. Observed Lecture Baseline\nSynthetic baseline\n## 3. Architecture\n### Nesting and context contract\nShare scope\n## 8. Global Conventions and Mathematical Notation Protocol\nSynthetic notation\n## 9. End', encoding="utf-8")
        (self.root / "AGENTS.md").write_text("Synthetic policy", encoding="utf-8")
        (self.root / "scripts").mkdir()
        (self.root / "scripts/INGESTION_WORKFLOW.md").write_text("Synthetic workflow", encoding="utf-8")
        self.patcher = patch.object(workflow, "ROOT", self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.run = workflow.prepare(self.root)
        self.plan = workflow.load(self.run / "plan.json")
        self.task = self.plan["catalog"][0]["task_id"]
        self.packet = workflow.load(self.run / "packets" / (self.task + ".json"))
        self.locator = self.packet["elements"][0]["locator"]
        self.report = {key: self.packet[key] for key in ["task_id", "context_sha256", "source_sha256", "slide_sha256"]}
        self.report.update({"summary": "Synthetic arithmetic", "coverage": {self.locator: "semantic"},
                            "units": [{"type": "worked-example", "statement": "Two values have mean three.",
                                       "concepts": ["central-tendency"], "evidence_label": "LECTURE",
                                       "evidence": [{"locator": self.locator, "quote": "Two values: 2 and 4."}], "references": []}],
                            "investigations": [], "issues": [],
                            "visual": {"mode": "unavailable", "reason": "Synthetic fixture has no renderer."},
                            "checks": [{"description": "Mean", "locators": [self.locator], "expression": "mean([2,4])", "expected": 3}],
                            "limitations": ["Synthetic fixture; no full slide view."]})

    def test_safe_calculation_rejects_code_and_unbounded_work(self):
        self.assertEqual(workflow.calculate("comb(6,3)"), 20)
        self.assertEqual(workflow.calculate("median([120,180,180,200,260,310,900])"), 200)
        for expression in ["__import__('os').system('whoami')", "(1).__class__", "2**1000000", "factorial(100000)", "[1]*1000000", "float('nan')"]:
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                workflow.calculate(expression)

    def test_report_provenance_coverage_and_reference_gates(self):
        self.assertTrue(workflow.validate_report(self.packet, self.report, {})[0]["passed"])
        mutations = [
            lambda r: r.update(context_sha256="wrong"),
            lambda r: r.update(coverage={}),
            lambda r: r["units"][0]["evidence"][0].update(quote="fabricated quotation"),
            lambda r: r["units"][0].update(evidence_label="VERIFIED"),
            lambda r: r["units"][0].update(concepts=["nested/topic"]),
            lambda r: r["visual"].update(mode="regions-inspected", assets=["../made-up.png"]),
            lambda r: r["visual"].update(mode="slide-inspected", render={"path": "../../outside.png", "sha256": "fake"}),
        ]
        for mutation in mutations:
            report = copy.deepcopy(self.report)
            mutation(report)
            with self.assertRaises(ValueError):
                workflow.validate_report(self.packet, report, {})

    def test_flag_coverage_is_required(self):
        packet = copy.deepcopy(self.packet)
        packet["review_flags"] = ["equation-structure-and-notation"]
        with self.assertRaisesRegex(ValueError, "Every parser flag"):
            workflow.validate_report(packet, self.report, {})

    def test_packet_supplies_context_and_prepare_is_idempotent(self):
        packet = workflow.task_packet(self.run, self.task)
        self.assertEqual(packet["context"]["dataset"], None)
        self.assertEqual(packet["task"]["context_sha256"], self.plan["context_sha256"])
        self.assertEqual(workflow.prepare(self.root), self.run)

    def test_duplicate_filename_with_identical_bytes_is_deduplicated(self):
        (self.root / "renamed.pptx").write_bytes(self.fixture.source.read_bytes())
        plan = workflow.load(workflow.prepare(self.root) / "plan.json")
        self.assertEqual(len(plan["decks"]), 1)
        self.assertEqual(len(plan["catalog"]), 1)
        self.assertEqual(len(plan["decks"][0]["aliases"]), 1)

    def test_modified_context_source_and_packets_are_rejected(self):
        path = self.run / "packets" / (self.task + ".json")
        original = path.read_bytes()
        path.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "packet changed"):
            workflow.verify_run(self.run)
        path.write_bytes(original)
        (self.root / "AGENTS.md").write_text("Changed policy", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "context is stale"):
            workflow.verify_run(self.run)

    def analysis(self, report=None, relationships=None):
        (self.run / "analysis.json").write_bytes(workflow.encoded({"references": {}, "reports": [report or self.report], "relationships": relationships or []}))

    def test_end_to_end_partial_status_and_failed_calculation(self):
        self.analysis()
        path, result = workflow.finalize(self.run)
        self.assertEqual(result["reviewed_slides"], 1)
        self.assertEqual(result["status"], "partial-validation")
        self.assertTrue((path / "report.md").exists())
        self.report["checks"][0]["expected"] = 900
        self.analysis()
        _, result = workflow.finalize(self.run)
        self.assertEqual(result["status"], "checks-failed")

    def test_cycle_and_missing_task_detection(self):
        self.report["units"][0]["concepts"].append("data-foundations")
        relationships = [{"from": a, "to": b, "kind": "prerequisite", "evidence_label": "INFERENCE", "reason": "Synthetic edge", "tasks": [self.task]}
                         for a, b in [("central-tendency", "data-foundations"), ("data-foundations", "central-tendency")]]
        self.analysis(relationships=relationships)
        with self.assertRaisesRegex(ValueError, "Circular"):
            workflow.finalize(self.run)
        (self.run / "analysis.json").write_bytes(workflow.encoded({"references": {}, "reports": [], "relationships": []}))
        _, result = workflow.finalize(self.run)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["missing_tasks"], [self.task])


if __name__ == "__main__":
    unittest.main()
