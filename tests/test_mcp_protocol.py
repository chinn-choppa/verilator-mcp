"""Реальные проверки MCP-клиента без подмены официального SDK."""

from __future__ import annotations

import sys
import unittest

from mcp import Client, StdioServerParameters

from verilator_mcp.server import create_server

EXPECTED_TOOLS = {"server_info", "tool_status", "parse_diagnostics"}


class MCPProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_in_memory_json_rpc_list_and_call(self) -> None:
        # В отличие от прямого вызова Python-функции, legacy mode
        # использует MCP JSON-RPC и обязательный initialize handshake.
        async with Client(create_server(), mode="legacy") as client:
            listed = await client.list_tools()
            self.assertEqual({item.name for item in listed.tools}, EXPECTED_TOOLS)
            self.assertTrue(all(item.input_schema for item in listed.tools))

            info = await client.call_tool("server_info", {})
            self.assertFalse(info.is_error)
            self.assertEqual(info.structured_content["server"], "verilator-mcp")
            self.assertFalse(info.structured_content["eda_execution_supported"])

            parsed = await client.call_tool(
                "parse_diagnostics",
                {"text": "%Error-UNSUPPORTED: rtl/top.sv:9:2: unsupported", "limit": 10},
            )
            self.assertFalse(parsed.is_error)
            self.assertEqual(parsed.structured_content["count"], 1)
            self.assertEqual(parsed.structured_content["items"][0]["line"], 9)

    async def test_invalid_payload_fails_closed(self) -> None:
        async with Client(create_server(), mode="legacy") as client:
            # Ошибка может быть результатом инструмента или ошибкой JSON-RPC.
            # Ни тот ни другой путь не должен превращаться в успешный результат.
            try:
                result = await client.call_tool(
                    "parse_diagnostics", {"text": "x" * 1_048_577, "limit": 1}
                )
            except Exception:
                pass
            else:
                self.assertTrue(result.is_error)

            try:
                result = await client.call_tool(
                    "parse_diagnostics", {"text": "", "limit": "invalid"}
                )
            except Exception:
                pass
            else:
                self.assertTrue(result.is_error)

    async def test_actual_stdio_process_list_and_call(self) -> None:
        # Настоящий дочерний процесс: любые посторонние stdout-строки
        # нарушат протокольный обмен. Никакой mock / stub здесь нет.
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

            diagnostics = await client.call_tool(
                "parse_diagnostics",
                {"text": "%Warning-WIDTH: top.sv:3:1: mismatch"},
            )
            self.assertFalse(diagnostics.is_error)
            self.assertEqual(diagnostics.structured_content["count"], 1)


if __name__ == "__main__":
    unittest.main()
