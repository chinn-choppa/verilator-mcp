"""Actual Verilator --binary build, through the official MCP client."""

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
class RealBuildIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_binary_build_success_and_failure_without_simulation(self) -> None:
        self.assertIsNotNone(find_verilator(), "Verilator must be installed for integration")
        self.assertIsNotNone(_trusted_toolchain(), "C++/make required for integration")
        workspace = Path(__file__).resolve().parent / "fixtures" / "build"
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "VERILATOR_MCP_WORKSPACE_ROOT": str(workspace),
                "VERILATOR_MCP_ARTIFACT_ROOT": tmp,
            }
            with patch.dict(os.environ, env):
                async with Client(create_server(), mode="legacy") as client:
                    listed = await client.list_tools()
                    self.assertIn("build_run", {tool.name for tool in listed.tools})
                    good = await client.call_tool(
                        "build_run", {"manifest_path": "good.json", "timeout_seconds": 240}
                    )
                    bad = await client.call_tool(
                        "build_run", {"manifest_path": "bad.json", "timeout_seconds": 120}
                    )
            self.assertFalse(good.is_error, str(good.content))
            self.assertFalse(bad.is_error, str(bad.content))
            passed = good.structured_content
            failed = bad.structured_content
            self.assertEqual(passed["build_status"], "PASS", passed)
            self.assertTrue(passed["executed"])
            self.assertEqual(passed["exit_code"], 0)
            self.assertEqual(passed["simulation_status"], "NOT_RUN")
            self.assertEqual(passed["verification_verdict"], "NOT_RUN")
            self.assertEqual(len(passed["binary_sha256"]), 64)
            self.assertTrue((Path(tmp) / passed["binary_artifact"]).is_file())
            self.assertEqual(len(passed["tool_sha256"]), 3)
            self.assertEqual(failed["build_status"], "BUILD_FAIL")
            self.assertNotEqual(failed["exit_code"], 0)
            self.assertTrue(failed["executed"])
            self.assertIsNone(failed["binary_artifact"])
            self.assertEqual(failed["verification_verdict"], "NOT_RUN")
            self.assertTrue((Path(tmp) / passed["artifacts"]["result"]).is_file())
            self.assertTrue((Path(tmp) / failed["artifacts"]["stderr"]).is_file())


if __name__ == "__main__":
    unittest.main()
