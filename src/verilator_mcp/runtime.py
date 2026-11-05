"""Поиск EDA-инструмента без запуска программ и раскрытия локальных путей."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def inspect_tool(tool: str, env_name: str) -> dict[str, object]:
    """Вернуть факт обнаружения, не принимая путь от MCP-клиента."""
    override = os.getenv(env_name)
    if override is not None:
        p = Path(override)
        if not p.is_absolute() or not p.is_file():
            state = "INVALID_OVERRIDE"
        else:
            state = "DETECTED_UNVERIFIED"
    else:
        state = "DETECTED_UNVERIFIED" if shutil.which(tool) else "NOT_FOUND"
    return {
        "tool": tool,
        "state": state,
        "configured": override is not None,
        "executed": False,
    }
