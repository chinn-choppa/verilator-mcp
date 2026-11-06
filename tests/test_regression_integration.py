"""Настоящая регрессия с разными verdict и повторяемым seed через MCP."""

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
class RealRegressionIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_mixed_verdict_and_seed_replay(self):
        self.assertIsNotNone(find_verilator(), "Verilator required for integration")
        self.assertIsNotNone(_trusted_toolchain(), "C++ and Make required for integration")
        workspace = Path(__file__).resolve().parent / "fixtures" / "simulation"
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {
                "VERILATOR_MCP_WORKSPACE_ROOT": str(workspace),
                "VERILATOR_MCP_ARTIFACT_ROOT": tmp,
            }):
                async with Client(create_server(), mode="legacy", read_timeout_seconds=400) as client:
                    tools = await client.list_tools()
                    self.assertIn("regression_run", {item.name for item in tools.tools})
                    builds = {}
                    for kind in ("good", "fatal", "unknown"):
                        result = await client.call_tool("build_run", {
                            "manifest_path": kind + ".json", "timeout_seconds": 240,
                        })
                        self.assertFalse(result.is_error, str(result.content))
                        self.assertEqual(result.structured_content["build_status"], "PASS")
                        builds[kind] = result.structured_content["build_id"]
                    cases = [
                        {"build_id": builds["good"], "seed": 42},
                        {"build_id": builds["good"], "seed": 42},
                        {"build_id": builds["fatal"], "seed": 17},
                        {"build_id": builds["unknown"], "seed": 17},
                    ]
                    output = await client.call_tool("regression_run", {
                        "cases": cases, "timeout_seconds": 15,
                    })
                    self.assertFalse(output.is_error, str(output.content))
                    report = output.structured_content
                    self.assertEqual(report["regression_status"], "FAIL", report)
                    self.assertEqual(report["counts"], {
                        "PASS": 2, "FAIL": 1, "INCONCLUSIVE": 1, "NOT_RUN": 0,
                    })
                    self.assertEqual(report["replay"], cases)
                    self.assertTrue(all(case["build_status"] == "PASS" for case in report["cases"]))
                    self.assertEqual(
                        [case["seed"] for case in report["cases"]], [42, 42, 17, 17]
                    )
                    ids = [case["simulation_id"] for case in report["cases"]]
                    self.assertEqual(len(set(ids)), 4)
                    self.assertTrue((Path(tmp) / report["artifacts"]["result"]).is_file())


if __name__ == "__main__":
    unittest.main()
