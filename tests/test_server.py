"""Вспомогательный тест конструктора сервера при наличии MCP SDK."""

import unittest


class ServerTests(unittest.TestCase):
    def test_constructs_with_installed_sdk(self):
        try:
            import mcp  # noqa: F401
        except ImportError:
            self.skipTest("MCP SDK не установлен; требуется реальный SDK и MCP client для приёмки")
        from verilator_mcp.server import create_server
        self.assertIsNotNone(create_server())


if __name__ == "__main__":
    unittest.main()
