"""Actual Verilator instrumented build, sim and LCOV report via MCP."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from verilator_mcp.coverage_report import _trusted_coverage_tool
from verilator_mcp.lint import find_verilator
from verilator_mcp.server import create_server


@unittest.skipUnless(
    os.getenv("VERILATOR_MCP_RUN_INTEGRATION") == "1",
    "REAL_VERILATOR_NOT_RUN: integration flag absent",
)
class CoverageIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_line_coverage_from_self_checked_design(self):
        self.assertIsNotNone(find_verilator(), "Verilator required")
        self.assertIsNotNone(_trusted_coverage_tool(), "verilator_coverage required")
        workspace = Path(__file__).resolve().parent / "fixtures" / "simulation"
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {
                "VERILATOR_MCP_WORKSPACE_ROOT": str(workspace),
                "VERILATOR_MCP_ARTIFACT_ROOT": tmp,
            }):
                async with Client(create_server(), mode="legacy", read_timeout_seconds=400) as client:
                    built = await client.call_tool("build_run", {
                        "manifest_path": "good.json", "timeout_seconds": 240,
                        "coverage_line": True, "assertions": True,
                    })
                    self.assertFalse(built.is_error, str(built.content))
                    self.assertEqual(built.structured_content["build_status"], "PASS")
                    self.assertTrue(built.structured_content["coverage_line_enabled"])

                    sim = await client.call_tool("simulation_run", {
                        "build_id": built.structured_content["build_id"],
                        "timeout_seconds": 30, "seed": 7,
                    })
                    self.assertFalse(sim.is_error, str(sim.content))
                    simulation = sim.structured_content
                    self.assertEqual(simulation["verification_verdict"], "PASS")
                    self.assertEqual(simulation["coverage_status"], "RECORDED", simulation)

                    result = await client.call_tool("coverage_report", {
                        "run_id": simulation["run_id"], "timeout_seconds": 30,
                    })
                    self.assertFalse(result.is_error, str(result.content))
                    report = result.structured_content
                    self.assertEqual(report["report_status"], "READY", report)
                    self.assertTrue(report["executed"])
                    self.assertGreater(report["summary"]["total_lines"], 0)
                    self.assertGreater(report["summary"]["covered_lines"], 0)
                    self.assertLessEqual(
                        report["summary"]["covered_lines"],
                        report["summary"]["total_lines"],
                    )
                    self.assertTrue((Path(tmp) / report["artifacts"]["lcov"]).is_file())


if __name__ == "__main__":
    unittest.main()
