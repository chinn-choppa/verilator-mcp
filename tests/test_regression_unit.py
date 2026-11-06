"""Проверка ограниченных регрессий, воспроизводимых seeds и ошибок."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from verilator_mcp.regression import RegressionCase, _aggregate, regression_run_project
from verilator_mcp.workspace import ManifestError


class RegressionUnitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.workspace = base / "workspace"
        self.artifacts = base / "artifacts"
        self.workspace.mkdir()
        self.artifacts.mkdir()
        self.build_id = "build-" + "a" * 32
        env = patch.dict(os.environ, {
            "VERILATOR_MCP_WORKSPACE_ROOT": str(self.workspace),
            "VERILATOR_MCP_ARTIFACT_ROOT": str(self.artifacts),
        })
        env.start()
        self.addCleanup(env.stop)

    async def test_all_pass_and_exact_replay_seed(self):
        calls = []

        async def fake_sim(build_id, timeout_seconds, seed):
            calls.append((build_id, seed, timeout_seconds))
            return {
                "run_status": "PASS", "verification_verdict": "PASS",
                "run_id": f"sim-{len(calls):032x}",
                "artifacts": {"result": f"sim-{len(calls):032x}/result.json"},
                "exit_code": 0, "executed": True,
            }

        with (
            patch("verilator_mcp.regression._validated_build"),
            patch("verilator_mcp.regression.simulation_run_project", side_effect=fake_sim),
        ):
            cases = [
                RegressionCase(build_id=self.build_id, seed=42),
                RegressionCase(build_id=self.build_id, seed=42),
            ]
            result = await regression_run_project(cases, timeout_seconds=4)

        self.assertEqual(result["regression_status"], "PASS")
        self.assertEqual(result["verification_verdict"], "PASS")
        self.assertEqual(result["counts"]["PASS"], 2)
        self.assertEqual(result["replay"], [
            {"build_id": self.build_id, "seed": 42},
            {"build_id": self.build_id, "seed": 42},
        ])
        self.assertEqual(calls, [(self.build_id, 42, 4), (self.build_id, 42, 4)])
        self.assertNotEqual(result["cases"][0]["simulation_id"], result["cases"][1]["simulation_id"])
        result_path = self.artifacts / result["artifacts"]["result"]
        self.assertTrue(result_path.is_file())
        self.assertEqual(json.loads(result_path.read_text(encoding="utf-8"))["regression_status"], "PASS")

    async def test_failed_case_cannot_be_masked_by_success(self):
        async def fake_sim(build_id, timeout_seconds, seed):
            verdict = {1: "PASS", 2: "INCONCLUSIVE", 3: "FAIL"}[seed]
            return {
                "run_status": {"PASS": "PASS", "INCONCLUSIVE": "FINISHED_UNVERIFIED", "FAIL": "RUN_FAIL"}[verdict],
                "verification_verdict": verdict,
                "run_id": f"sim-{seed:032x}",
                "artifacts": {"result": f"sim-{seed:032x}/result.json"},
                "exit_code": 0 if seed != 3 else 1,
                "executed": True,
            }
        cases = [RegressionCase(build_id=self.build_id, seed=i) for i in range(1, 4)]
        with (
            patch("verilator_mcp.regression._validated_build"),
            patch("verilator_mcp.regression.simulation_run_project", side_effect=fake_sim),
        ):
            result = await regression_run_project(cases)
        self.assertEqual(result["regression_status"], "FAIL")
        self.assertEqual(result["verification_verdict"], "FAIL")
        self.assertEqual(result["counts"], {
            "PASS": 1, "FAIL": 1, "INCONCLUSIVE": 1, "NOT_RUN": 0,
        })
        self.assertTrue(all(item["build_status"] == "PASS" for item in result["cases"]))

    async def test_invalidated_build_is_explicitly_incomplete(self):
        async def fake_sim(build_id, timeout_seconds, seed):
            raise ManifestError("Artifact invalidated")
        with (
            patch("verilator_mcp.regression._validated_build"),
            patch("verilator_mcp.regression.simulation_run_project", side_effect=fake_sim),
        ):
            output = await regression_run_project([
                RegressionCase(build_id=self.build_id, seed=1),
                RegressionCase(build_id=self.build_id, seed=2),
            ])
        self.assertEqual(output["regression_status"], "INCOMPLETE")
        self.assertEqual(output["verification_verdict"], "NOT_RUN")
        self.assertEqual(output["counts"]["NOT_RUN"], 2)
        self.assertFalse(any(item["executed"] for item in output["cases"]))

    async def test_invalid_builds_rejected_before_creating_artifacts(self):
        with self.assertRaises(ManifestError):
            await regression_run_project([RegressionCase(build_id=self.build_id)])
        self.assertEqual(list(self.artifacts.iterdir()), [])

    async def test_invalid_case_boundaries(self):
        cases = [RegressionCase(build_id=self.build_id)]
        for bad in (0, -1, 61, True, "10", 1.2):
            with self.subTest(timeout=bad):
                with self.assertRaises(ManifestError):
                    await regression_run_project(cases, timeout_seconds=bad)
        for bad_cases in ([], cases * 9, "not a list", [object()]):
            with self.subTest(cases=str(bad_cases)[:40]):
                with self.assertRaises(ManifestError):
                    await regression_run_project(bad_cases)
        for seed in (0, True, "42", 2_147_483_648):
            with self.subTest(seed=seed):
                with self.assertRaises(ValidationError):
                    RegressionCase(build_id=self.build_id, seed=seed)
        with self.assertRaises(ValidationError):
            RegressionCase(build_id=self.build_id, seed=1, command="rm -rf /")

    def test_aggregate_fails_closed(self):
        status, counts = _aggregate([
            {"verification_verdict": "PASS"},
            {"verification_verdict": "INCONCLUSIVE"},
        ])
        self.assertEqual(status, "INCONCLUSIVE")
        self.assertEqual(counts["PASS"], 1)
        status, counts = _aggregate([
            {"verification_verdict": "PASS"},
            {"verification_verdict": "NOT_RUN"},
        ])
        self.assertEqual(status, "INCOMPLETE")
        self.assertEqual(counts["NOT_RUN"], 1)


if __name__ == "__main__":
    unittest.main()
