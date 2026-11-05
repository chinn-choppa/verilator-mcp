"""Структурные проверки публичного репозитория."""

import tomllib
import unittest
from pathlib import Path


class ProjectStructureTests(unittest.TestCase):
    def test_required_public_files(self):
        root = Path(__file__).resolve().parents[1]
        for name in (
            "README.md", "README.en.md", "CONTRIBUTING.md", "SECURITY.md",
            "CODE_OF_CONDUCT.md", "LICENSE", "AGENTS.md", "CHANGELOG.md",
            ".github/workflows/ci.yml", "docs/ARCHITECTURE.md",
            "docs/TOOL_CONTRACT.md", "docs/TESTING.md", "docs/ROADMAP.md",
        ):
            with self.subTest(name=name):
                self.assertTrue((root / name).is_file())

    def test_pyproject_exposes_console_script(self):
        root = Path(__file__).resolve().parents[1]
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["project"]["name"], root.name)
        self.assertIn(root.name, data["project"]["scripts"])
        self.assertIn("mcp==2.3.0", data["project"]["dependencies"])


if __name__ == "__main__":
    unittest.main()
