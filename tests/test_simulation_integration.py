"""Actual Verilator self-checking verdicts, fatal, no-verdict and watchdog."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client

from verilator_mcp.build import _trusted_toolchain
from verilator_mcp.lint import find_verilator
from verilator_mcp.server import create_server


@unittest.skipUnless(
    os.getenv("VERILATOR_MCP_RUN_INTEGRATION") == "1",
    "REAL_VERILATOR_NOT_RUN: integration flag absent",
)
class RealSimulationIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_simulation_verdicts_end_to_end(self):
        self.assertIsNotNone(find_verilator(), "Verilator must be installed")
        self.assertIsNotNone(_trusted_toolchain(), "C++/Make must be installed")
        workspace = Path(__file__).resolve().parent / "fixtures" / "simulation"
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {
                "VERILATOR_MCP_WORKSPACE_ROOT": str(workspace),
                "VERILATOR_MCP_ARTIFACT_ROOT": tmp,
            }):
                async with Client(create_server(), mode="legacy", read_timeout_seconds=400) as client:
                    tools = await client.list_tools()
                    self.assertIn("simulation_run", {tool.name for tool in tools.tools})
                    for name, expected_run, expected_verdict, timeout in (
                        ("good", "PASS", "PASS", 30),
                        ("fatal", "RUN_FAIL", "FAIL", 30),
                        ("unknown", "FINISHED_UNVERIFIED", "INCONCLUSIVE", 30),
                        ("timeout", "TIMEOUT", "FAIL", 1),
                    ):
                        with self.subTest(testbench=name):
                            build = await client.call_tool("build_run", {
                                "manifest_path": name + ".json",
                                "timeout_seconds": 240,
                            })
                            self.assertFalse(build.is_error, str(build.content))
                            built = build.structured_content
                            self.assertEqual(built["build_status"], "PASS", built)
                            sim = await client.call_tool("simulation_run", {
                                "build_id": built["build_id"], "timeout_seconds": timeout,
                                "seed": 42,
                            })
                            self.assertFalse(sim.is_error, str(sim.content))
                            result = sim.structured_content
                            self.assertEqual(result["run_status"], expected_run, result)
                            self.assertEqual(result["verification_verdict"], expected_verdict)
                            self.assertTrue(result["executed"])
                            self.assertEqual(result["seed"], 42)
                            self.assertTrue((Path(tmp) / result["artifacts"]["result"]).is_file())
                            if name == "good":
                                self.assertTrue(result["pass_marker_observed"])
                                self.assertTrue(result["finish_observed"])
                                self.assertEqual(result["exit_code"], 0)
                            elif name == "fatal":
                                self.assertTrue(result["fatal_observed"])
                                self.assertNotEqual(result["exit_code"], 0)
                            elif name == "unknown":
                                self.assertTrue(result["finish_observed"])
                                self.assertFalse(result["pass_marker_observed"])
                                self.assertEqual(result["exit_code"], 0)
                            else:
                                self.assertTrue(result["timed_out"])


if __name__ == "__main__":
    unittest.main()
