"""Нативные pytest-проверки официального MCP SDK: JSON-RPC и stdio."""

from __future__ import annotations

import asyncio
import sys

from mcp import Client, StdioServerParameters

from verilator_mcp.server import create_server

EXPECTED_TOOLS = {"server_info", "tool_status", "parse_diagnostics"}


def test_in_memory_json_rpc_list_and_call():
    async def scenario():
        async with Client(create_server(), mode="legacy") as client:
            listed = await client.list_tools()
            assert {item.name for item in listed.tools} == EXPECTED_TOOLS
            assert all(item.input_schema for item in listed.tools)

            info = await client.call_tool("server_info", {})
            assert info.is_error is False
            assert info.structured_content["server"] == "verilator-mcp"
            assert info.structured_content["eda_execution_supported"] is False

            parsed = await client.call_tool(
                "parse_diagnostics",
                {"text": "%Error-UNSUPPORTED: rtl/top.sv:9:2: unsupported", "limit": 10},
            )
            assert parsed.is_error is False
            assert parsed.structured_content["count"] == 1
            assert parsed.structured_content["items"][0]["line"] == 9

    asyncio.run(scenario())


def test_invalid_payload_fails_closed():
    async def scenario():
        async with Client(create_server(), mode="legacy") as client:
            for arguments in (
                {"text": "x" * 1_048_577, "limit": 1},
                {"text": "", "limit": "invalid"},
            ):
                try:
                    result = await client.call_tool("parse_diagnostics", arguments)
                except Exception:
                    # JSON-RPC rejects a malformed payload with an error.
                    continue
                assert result.is_error is True

    asyncio.run(scenario())


def test_actual_stdio_process_list_and_call():
    async def scenario():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "verilator_mcp"],
            env={"PYTHONUTF8": "1"},
        )
        async with Client(params, mode="legacy", read_timeout_seconds=20) as client:
            listed = await client.list_tools()
            assert {tool.name for tool in listed.tools} == EXPECTED_TOOLS

            response = await client.call_tool("server_info", {})
            assert response.is_error is False
            assert response.structured_content["server"] == "verilator-mcp"

            diagnostics = await client.call_tool(
                "parse_diagnostics",
                {"text": "%Warning-WIDTH: top.sv:3:1: mismatch"},
            )
            assert diagnostics.is_error is False
            assert diagnostics.structured_content["count"] == 1

    asyncio.run(scenario())
