"""Проверки discovery, не требующие запуска EDA."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verilator_mcp.runtime import inspect_tool


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tool = "verilator"
        self.env_name = "VERILATOR_MCP_EXECUTABLE"

    def test_absent_tool(self):
        with patch.dict(os.environ, {self.env_name: ""}, clear=False):
            got = inspect_tool(self.tool, self.env_name)
        self.assertEqual(got["state"], "INVALID_OVERRIDE")
        self.assertFalse(got["executed"])
        self.assertNotIn("path", got)

    def test_explicit_existing_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "fake-tool"
            p.write_text("not a real tool", encoding="utf-8")
            with patch.dict(os.environ, {self.env_name: str(p)}):
                got = inspect_tool(self.tool, self.env_name)
        self.assertEqual(got["state"], "DETECTED_UNVERIFIED")
        self.assertTrue(got["configured"])
        self.assertFalse(got["executed"])

    def test_missing_tool_in_path(self):
        with patch.dict(os.environ, {self.env_name: ""}, clear=False):
            os.environ.pop(self.env_name, None)
            with patch("verilator_mcp.runtime.shutil.which", return_value=None):
                got = inspect_tool(self.tool, self.env_name)
        self.assertEqual(got["state"], "NOT_FOUND")
        self.assertFalse(got["configured"])

    def test_path_tool_discovery(self):
        with patch.dict(os.environ, {self.env_name: ""}, clear=False):
            os.environ.pop(self.env_name, None)
            with patch("verilator_mcp.runtime.shutil.which", return_value="/tmp/eda"):
                got = inspect_tool(self.tool, self.env_name)
        self.assertEqual(got["state"], "DETECTED_UNVERIFIED")
        self.assertFalse(got["executed"])


if __name__ == "__main__":
    unittest.main()
