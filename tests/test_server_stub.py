"""Проверка набора инструментов через изолированный stub, без EDA."""
import importlib
import sys
import types


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
        raise AssertionError("Настоящий MCP-сервер запускать нельзя")


def test_tool_registration_and_responses(monkeypatch):
    mcp = types.ModuleType("mcp")
    server_module = types.ModuleType("mcp.server")
    server_module.MCPServer = MCPStub
    mcp.server = server_module
    target = "verilator_mcp.server"
    monkeypatch.setitem(sys.modules, "mcp", mcp)
    monkeypatch.setitem(sys.modules, "mcp.server", server_module)
    monkeypatch.delitem(sys.modules, target, raising=False)
    try:
        module = importlib.import_module(target)
        server = module.create_server()
        assert set(server.tools) == {"server_info", "tool_status", "parse_diagnostics"}
        assert server.tools["server_info"]()["stage"] == "bootstrap"
        assert server.tools["server_info"]()["eda_execution_supported"] is False
        assert server.tools["parse_diagnostics"]("", limit=1)["count"] == 0
    finally:
        # Prevent leakage of the stub-built module into subsequent pytest cases.
        monkeypatch.delitem(sys.modules, target, raising=False)
