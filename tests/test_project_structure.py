"""Проверки структуры публичного пакета с pytest."""
from pathlib import Path
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("relative", [
    "README.md", "README.en.md", "CONTRIBUTING.md", "SECURITY.md",
    "CODE_OF_CONDUCT.md", "LICENSE", "AGENTS.md", "CHANGELOG.md",
    ".github/workflows/ci.yml", "docs/ARCHITECTURE.md",
    "docs/TOOL_CONTRACT.md", "docs/TESTING.md", "docs/ROADMAP.md",
    "uv.lock",
])
def test_required_public_file(relative):
    assert (ROOT / relative).is_file(), relative


def test_pyproject_exposes_console_script():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["name"] == ROOT.name
    assert ROOT.name in data["project"]["scripts"]
    assert "mcp==2.3.0" in data["project"]["dependencies"]
    assert "pytest==9.2.0" in data["dependency-groups"]["dev"]
