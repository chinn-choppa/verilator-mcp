"""Синтетический тест регистрации инструментов без внешнего MCP SDK."""

import importlib
import sys
import types
import unittest
from unittest.mock import patch


class MCPStub:
    def __init__(self, name):
        self.name = name
        self.tools = {}

    def tool(self):
        def register(fn):
            self.tools[fn.__name__] = fn
            return fn
        return register

    def run(self, transport):
        raise AssertionError("Нельзя запускать настоящий сервер из stub теста")


class ServerStubTests(unittest.TestCase):
    def test_tool_registration_and_responses(self):
        mcp = types.ModuleType("mcp")
        server_mod = types.ModuleType("mcp.server")
        server_mod.MCPServer = MCPStub
        mcp.server = server_mod
        target = "verilator_mcp.server"
        with patch.dict(sys.modules, {"mcp": mcp, "mcp.server": server_mod}):
            sys.modules.pop(target, None)
            try:
                module = importlib.import_module(target)
                server = module.create_server()
                self.assertEqual(set(server.tools), {"server_info", "tool_status", "parse_diagnostics"})
                info = server.tools["server_info"]()
                self.assertEqual(info["stage"], "bootstrap")
                self.assertFalse(info["eda_execution_supported"])
                found = server.tools["parse_diagnostics"]("", limit=1)
                self.assertEqual(found["count"], 0)
            finally:
                sys.modules.pop(target, None)


if __name__ == "__main__":
    unittest.main()
