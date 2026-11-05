"""Консервативный парсер диагностик: только доказанные совпадения."""

from __future__ import annotations

import re

MAX_INPUT_BYTES = 1_048_576
MAX_ITEMS = 200

_VERILATOR = re.compile(
    r"^%(?P<level>Warning|Error)(?:-(?P<code>[A-Z0-9_]+))?:\s*"
    r"(?:(?P<file>(?:[A-Za-z]:)?[^:]+):(?P<line>\d+)(?::(?P<col>\d+))?:\s*)?"
    r"(?P<message>.*)$"
)
_SYNPLIFY = re.compile(
    r"^@(?P<level>[EWI]):\s*"
    r"(?:(?P<file>.+?)\((?P<line>\d+)\):\s*)?"
    r"(?P<message>.*)$"
)
_QUESTA = re.compile(
    r"^\*\*\s*(?P<level>Error|Warning|Info|Fatal):\s*"
    r"(?:\((?P<code>[^)]+)\)\s*)?(?P<message>.*)$"
)


def parse_diagnostics_text(text: str, tool: str, limit: int = 200) -> dict[str, object]:
    """Возвращать только строки с известным диагностическим префиксом."""
    if not isinstance(text, str):
        raise ValueError("text должен быть строкой")
    if len(text.encode("utf-8")) > MAX_INPUT_BYTES:
        raise ValueError("Слишком большой вход: максимум 1 МиБ")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_ITEMS:
        raise ValueError("limit должен быть целым числом от 1 до 200")

    patterns = {"verilator": _VERILATOR, "synplify_pro": _SYNPLIFY, "vsim": _QUESTA}
    if tool not in patterns:
        raise ValueError("Неизвестный EDA-инструмент")
    pattern = patterns[tool]
    aliases = {"E": "error", "W": "warning", "I": "info", "Fatal": "fatal"}
    items: list[dict[str, object]] = []
    count = 0
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if match is None:
            continue
        count += 1
        if len(items) >= limit:
            continue
        g = match.groupdict()
        level = g.get("level") or ""
        severity = aliases.get(level, level.lower())
        file = g.get("file")
        items.append({
            "severity": severity,
            "code": g.get("code"),
            "file": file,
            "line": int(g["line"]) if g.get("line") else None,
            "column": int(g["col"]) if g.get("col") else None,
            "message": g.get("message") or "",
            "raw": line[:4096],
        })
    return {"tool": tool, "count": count, "truncated": count > len(items), "items": items}
