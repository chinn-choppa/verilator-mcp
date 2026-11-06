"""Локальный stdio MCP с ограниченным Verilator lint, без сборки и симуляции."""

from __future__ import annotations

from mcp.server import MCPServer

from . import __version__
from .build import build_run_project
from .coverage_report import coverage_report_project
from .diagnostics import parse_diagnostics_text
from .lint import lint_run_project
from .runtime import inspect_tool
from .simulation import simulation_run_project
from .workspace import validate_manifest


def create_server() -> MCPServer:
    """Зарегистрировать безопасные, типизированные операции."""
    server = MCPServer("verilator-mcp")

    @server.tool()
    def server_info() -> dict[str, object]:
        """Сообщить о возможностях без утверждений о прохождении верификации."""
        return {
            "server": "verilator-mcp",
            "version": __version__,
            "vendor_tool": "verilator",
            "stage": "coverage_ready",
            "operations": [
                "server_info", "tool_status", "parse_diagnostics",
                "project_validate", "lint_run", "build_run", "simulation_run",
                "coverage_report",
            ],
            "eda_execution_supported": True,
            "simulation_supported": True,
            "build_supported": True,
        }

    @server.tool()
    def tool_status() -> dict[str, object]:
        """Найти Verilator без выполнения EDA."""
        return inspect_tool("verilator", "VERILATOR_MCP_EXECUTABLE")

    @server.tool()
    def parse_diagnostics(text: str, limit: int = 200) -> dict[str, object]:
        """Консервативно разобрать ограниченный фрагмент диагностик."""
        return parse_diagnostics_text(text, "verilator", limit)

    @server.tool()
    def project_validate(manifest_path: str) -> dict[str, object]:
        """Выполнить read-only проверку разрешённого workspace."""
        return validate_manifest(manifest_path).public_summary()

    @server.tool()
    async def lint_run(manifest_path: str, timeout_seconds: int = 60) -> dict[str, object]:
        """Выполнить только Verilator lint; не подтверждать функциональную верификацию."""
        return await lint_run_project(manifest_path, timeout_seconds)

    @server.tool()
    async def build_run(
        manifest_path: str, timeout_seconds: int = 180,
        coverage_line: bool = False, assertions: bool = True,
    ) -> dict[str, object]:
        """Собрать существующий SystemVerilog тестбенч, не запуская симуляцию."""
        return await build_run_project(manifest_path, timeout_seconds, coverage_line, assertions)

    @server.tool()
    async def simulation_run(
        build_id: str, timeout_seconds: int = 30, seed: int = 1,
    ) -> dict[str, object]:
        """Запустить только подтверждённую сборку; PASS требует свидетельства из TB."""
        return await simulation_run_project(build_id, timeout_seconds, seed)

    @server.tool()
    async def coverage_report(run_id: str, timeout_seconds: int = 20) -> dict[str, object]:
        """Проверить и разобрать реальные данные покрытия через verilator_coverage."""
        return await coverage_report_project(run_id, timeout_seconds)

    return server


def main() -> None:
    """Запустить локальный stdio MCP."""
    create_server().run(transport="stdio")
