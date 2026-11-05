"""Реальное EDA-интеграционное тестирование только при явном включении."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client
from verilator_mcp.lint import find_verilator
from verilator_mcp.server import create_server


@unittest.skipUnless(
    os.environ.get("VERILATOR_MCP_RUN_INTEGRATION") == "1",
    "REAL_VERILATOR_NOT_RUN: integration flag absent",
)
class RealVerilatorIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_lint_pass_and_fail_through_mcp(self):
        self.assertIsNotNone(find_verilator(), "Verilator must be installed in integration CI")
        workspace = Path(__file__).resolve().parent / "fixtures" / "lint"
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "VERILATOR_MCP_WORKSPACE_ROOT": str(workspace),
                "VERILATOR_MCP_ARTIFACT_ROOT": tmp,
            }
            with patch.dict(os.environ, env):
                async with Client(create_server(), mode="legacy") as client:
                    good = await client.call_tool(
                        "lint_run", {"manifest_path": "good.json", "timeout_seconds": 30}
                    )
                    bad = await client.call_tool(
                        "lint_run", {"manifest_path": "bad.json", "timeout_seconds": 30}
                    )
                self.assertFalse(good.is_error)
                self.assertFalse(bad.is_error)
                good_result = good.structured_content
                bad_result = bad.structured_content
                self.assertIn(good_result["lint_status"], {"PASS", "PASS_WITH_WARNINGS"})
                self.assertEqual(good_result["exit_code"], 0)
                self.assertTrue(good_result["executed"])
                self.assertTrue(good_result["tool_version"].startswith("Verilator "))
                self.assertEqual(good_result["verification_verdict"], "NOT_RUN")
                self.assertEqual(bad_result["lint_status"], "FAIL")
                self.assertNotEqual(bad_result["exit_code"], 0)
                self.assertTrue(bad_result["executed"])
                self.assertGreater(bad_result["diagnostics"]["count"], 0)
                self.assertTrue((Path(tmp) / good_result["artifacts"]["result"]).is_file())
                self.assertTrue((Path(tmp) / bad_result["artifacts"]["stderr"]).is_file())


if __name__ == "__main__":
    unittest.main()
