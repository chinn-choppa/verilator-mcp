"""Реальные MCP JSON-RPC + stdio проверки, без заглушек протокола."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client, StdioServerParameters

from verilator_mcp.server import create_server

EXPECTED_TOOLS = {
    "server_info", "tool_status", "parse_diagnostics", "project_validate", "lint_run", "build_run", "simulation_run", "coverage_report"
}


class MCPProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_in_memory_json_rpc_list_and_call(self) -> None:
        async with Client(create_server(), mode="legacy") as client:
            listed = await client.list_tools()
            self.assertEqual({item.name for item in listed.tools}, EXPECTED_TOOLS)
            self.assertTrue(all(item.input_schema for item in listed.tools))
            info = await client.call_tool("server_info", {})
            self.assertFalse(info.is_error)
            self.assertTrue(info.structured_content["eda_execution_supported"])
            self.assertTrue(info.structured_content["simulation_supported"])
            self.assertTrue(info.structured_content["build_supported"])
            parsed = await client.call_tool("parse_diagnostics", {
                "text": "%Error-UNSUPPORTED: rtl/top.sv:9:2: unsupported",
                "limit": 10,
            })
            self.assertFalse(parsed.is_error)
            self.assertEqual(parsed.structured_content["items"][0]["line"], 9)

    async def test_invalid_payload_fails_closed(self) -> None:
        async with Client(create_server(), mode="legacy") as client:
            for request in (
                {"text": "x" * 1_048_577, "limit": 1},
                {"text": "", "limit": "invalid"},
            ):
                try:
                    result = await client.call_tool("parse_diagnostics", request)
                except Exception:
                    continue
                self.assertTrue(result.is_error)

    async def test_actual_stdio_process_list_and_call(self) -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "verilator_mcp"],
            env={"PYTHONUTF8": "1"},
        )
        async with Client(params, mode="legacy", read_timeout_seconds=20) as client:
            listed = await client.list_tools()
            self.assertEqual({tool.name for tool in listed.tools}, EXPECTED_TOOLS)
            response = await client.call_tool("server_info", {})
            self.assertFalse(response.is_error)
            self.assertEqual(response.structured_content["server"], "verilator-mcp")
            diagnostics = await client.call_tool("parse_diagnostics", {
                "text": "%Warning-WIDTH: top.sv:3:1: mismatch",
            })
            self.assertFalse(diagnostics.is_error)
            self.assertEqual(diagnostics.structured_content["count"], 1)

    async def test_workspace_and_missing_linter_via_real_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"
            artifacts = Path(tmp) / "artifacts"
            root.mkdir()
            artifacts.mkdir()
            (root / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
            (root / "project.json").write_text(json.dumps({
                "schema_version": 1, "top": "top", "sources": ["top.sv"],
            }), encoding="utf-8")
            with patch.dict(os.environ, {
                "VERILATOR_MCP_WORKSPACE_ROOT": str(root),
                "VERILATOR_MCP_ARTIFACT_ROOT": str(artifacts),
                "VERILATOR_MCP_EXECUTABLE": str(root / "not-installed"),
            }):
                async with Client(create_server(), mode="legacy") as client:
                    result = await client.call_tool("project_validate", {
                        "manifest_path": "project.json",
                    })
                    self.assertFalse(result.is_error)
                    self.assertEqual(result.structured_content["project"]["top"], "top")
                    missing = await client.call_tool("lint_run", {
                        "manifest_path": "project.json", "timeout_seconds": 3,
                    })
                    self.assertFalse(missing.is_error)
                    self.assertEqual(missing.structured_content["lint_status"], "NOT_AVAILABLE")
                    self.assertFalse(missing.structured_content["executed"])
                    self.assertEqual(missing.structured_content["verification_verdict"], "NOT_RUN")
                    self.assertEqual(list(artifacts.iterdir()), [])
                    build = await client.call_tool("build_run", {
                        "manifest_path": "project.json", "timeout_seconds": 100,
                    })
                    self.assertTrue(build.is_error)  # Нет обязательного testbench_top.
                    self.assertEqual(list(artifacts.iterdir()), [])
                    try:
                        bad = await client.call_tool("lint_run", {
                            "manifest_path": "../private.json", "timeout_seconds": 0,
                        })
                    except Exception:
                        pass
                    else:
                        self.assertTrue(bad.is_error)


if __name__ == "__main__":
    unittest.main()
