"""Официальный MCP SDK обязателен для проверки конструкции сервера."""
from verilator_mcp.server import create_server


def test_constructs_with_installed_sdk():
    assert create_server() is not None
