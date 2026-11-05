"""Локальный stdio MCP; запуск Verilator пока запрещён."""

from __future__ import annotations

from mcp.server import MCPServer

from . import __version__
from .diagnostics import parse_diagnostics_text
from .runtime import inspect_tool
from .workspace import validate_manifest


def create_server() -> MCPServer:
    """Зарегистрировать ограниченные операции."""
    server = MCPServer("verilator-mcp")

    @server.tool()
    def server_info() -> dict[str, object]:
        """Сообщить о возможностях сервера без запуска EDA."""
        return {
            "server": "verilator-mcp",
            "version": __version__,
            "vendor_tool": "verilator",
            "stage": "workspace_contract",
            "operations": [
                "server_info", "tool_status", "parse_diagnostics", "project_validate"
            ],
            "eda_execution_supported": False,
        }

    @server.tool()
    def tool_status() -> dict[str, object]:
        """Найти установленный инструмент, не выполняя его."""
        return inspect_tool("verilator", "VERILATOR_MCP_EXECUTABLE")

    @server.tool()
    def parse_diagnostics(text: str, limit: int = 200) -> dict[str, object]:
        """Распознать известные диагностические строки с ограничением размера."""
        return parse_diagnostics_text(text, "verilator", limit)

    @server.tool()
    def project_validate(manifest_path: str) -> dict[str, object]:
        """Проверить JSON manifest в предварительно разрешённом RTL workspace.

        Корни берутся только из окружения локального сервера; tool read-only.
        """
        return validate_manifest(manifest_path).public_summary()

    return server


def main() -> None:
    """Запустить MCP на stdio (stdout зарезервирован для JSON-RPC)."""
    create_server().run(transport="stdio")
