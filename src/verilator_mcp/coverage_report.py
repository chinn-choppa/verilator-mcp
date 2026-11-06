"""Отчёты по реально собранному Verilator coverage.dat без догадок."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from .execution import MAX_LOG_BYTES, run_bounded
from .lint import _save_artifact
from .simulation import _artifacts, _public_log, _read_record
from .workspace import ManifestError

_RUN_ID = re.compile(r"sim-[0-9a-f]{32}\Z")
_DA = re.compile(r"DA:(\d+),(\d+)(?:,\w+)?\Z")
MAX_COVERAGE_BYTES = 16_777_216
MAX_INFO_BYTES = 1_048_576
MAX_POINTS = 20_000


def _trusted_coverage_tool() -> Path | None:
    name = shutil.which("verilator_coverage")
    if not name:
        return None
    try:
        path = Path(name).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    permitted = "verilator_coverage.exe" if os.name == "nt" else "verilator_coverage"
    if not path.is_file() or path.name.lower() != permitted:
        return None
    if os.name != "nt" and not os.access(path, os.X_OK):
        return None
    return path


def _safe_source(source: str, workspace: Path) -> str:
    """Не выводить абсолютные имена файлов вне разрешённого проекта."""
    path = Path(source)
    try:
        resolved = (path if path.is_absolute() else workspace / path).resolve(strict=False)
        if resolved.is_relative_to(workspace):
            return resolved.relative_to(workspace).as_posix()
    except (ValueError, OSError, RuntimeError):
        pass
    return "<EXTERNAL_SOURCE>"


def parse_lcov_info(text: str, workspace: Path) -> dict[str, object]:
    """Консервативно извлечь только доказанные SF/DA записи LCOV."""
    if len(text.encode("utf-8")) > MAX_INFO_BYTES:
        raise ManifestError("LCOV отчёт слишком велик")
    found: dict[str, dict[int, int]] = {}
    active: str | None = None
    points = 0
    for line in text.splitlines():
        if len(line) > 4096:
            raise ManifestError("Слишком длинная LCOV строка")
        if line.startswith("SF:"):
            active = _safe_source(line[3:], workspace)
            if active == "<EXTERNAL_SOURCE>":
                # Не публикуем чужие пути, но считаем наблюдённые точки отдельно.
                active = "<EXTERNAL_SOURCE>"
            if len(found) >= 128 and active not in found:
                raise ManifestError("Слишком много файлов в LCOV")
            found.setdefault(active, {})
        elif line.startswith("DA:"):
            if active is None:
                raise ManifestError("LCOV DA без исходного файла")
            match = _DA.fullmatch(line)
            if match is None:
                raise ManifestError("Повреждённая LCOV строка DA")
            number, count = int(match[1]), int(match[2])
            if number < 1 or points >= MAX_POINTS:
                raise ManifestError("Некорректное число строк покрытия")
            points += 1
            existing = found[active].get(number, 0)
            found[active][number] = existing + count
        elif line == "end_of_record":
            active = None
    if points == 0:
        return {"status": "EMPTY", "files": [], "total_lines": None, "covered_lines": None}
    files = []
    for source, lines in sorted(found.items()):
        total = len(lines)
        covered = sum(1 for count in lines.values() if count > 0)
        files.append({"source": source, "total_lines": total, "covered_lines": covered})
    total_lines = sum(x["total_lines"] for x in files)
    covered_lines = sum(x["covered_lines"] for x in files)
    return {
        "status": "READY",
        "files": files,
        "total_lines": total_lines,
        "covered_lines": covered_lines,
        "line_rate": round(covered_lines / total_lines, 6) if total_lines else None,
        "point_records": points,
    }


async def coverage_report_project(run_id: str, timeout_seconds: int = 20) -> dict[str, object]:
    """Сформировать ограниченный LCOV результат по ранее завершённой симуляции."""
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise ManifestError("Некорректный идентификатор симуляции")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 60:
        raise ManifestError("timeout_seconds должен быть целым 1..60")
    workspace, artifact_root = _artifacts()
    folder = (artifact_root / run_id).resolve(strict=True)
    if folder.parent != artifact_root or not folder.is_dir():
        raise ManifestError("Каталог симуляции вне разрешённого корня")
    run = _read_record(folder, "result.json")
    if run.get("run_id") != run_id or run.get("operation") != "simulation":
        raise ManifestError("Нет подтверждённого результата симуляции")

    state = run.get("coverage_status", "DISABLED")
    common = {
        "operation": "coverage", "run_id": run_id,
        "simulation_verdict": run.get("verification_verdict"),
        "source": "actual_verilator_coverage_artifact",
    }
    if state != "RECORDED":
        return {
            **common, "report_status": {
                "DISABLED": "NOT_ENABLED", "NOT_OBSERVED": "NOT_OBSERVED",
                "EMPTY": "EMPTY", "UNREADABLE": "UNREADABLE",
                "UNSAFE": "UNSAFE", "TOO_LARGE": "TOO_LARGE",
            }.get(state, "NOT_RUN"), "executed": False,
        }

    data = (folder / "coverage.dat").resolve(strict=True)
    if data.parent != folder or not data.is_file():
        raise ManifestError("Недопустимый файл данных покрытия")
    if data.stat().st_size > MAX_COVERAGE_BYTES:
        return {**common, "report_status": "TOO_LARGE", "executed": False}
    if data.stat().st_size == 0:
        return {**common, "report_status": "EMPTY", "executed": False}

    tool = _trusted_coverage_tool()
    if tool is None:
        return {**common, "report_status": "NOT_AVAILABLE", "executed": False}
    info = folder / "coverage.info"
    if info.exists() or info.is_symlink():
        return {**common, "report_status": "UNSAFE", "executed": False}
    try:
        proc = await run_bounded(
            [str(tool), "--write-info", str(info), str(data)],
            folder, timeout_seconds, max_log_bytes=MAX_LOG_BYTES,
        )
    except OSError:
        return {**common, "report_status": "NOT_RUN", "executed": False}

    if proc.timed_out:
        status = "TIMEOUT"
    elif proc.exit_code != 0:
        status = "TOOL_FAIL"
    elif proc.stdout_truncated or proc.stderr_truncated:
        status = "INCOMPLETE"
    elif not info.is_file():
        status = "NOT_OBSERVED"
    elif info.resolve(strict=True).parent != folder:
        status = "UNSAFE"
    elif info.stat().st_size > MAX_INFO_BYTES:
        status = "TOO_LARGE"
    else:
        try:
            parsed = parse_lcov_info(info.read_text(encoding="utf-8"), workspace)
        except (UnicodeError, OSError, ManifestError):
            status = "INVALID"
        else:
            status = parsed["status"]

    result: dict[str, object] = {
        **common, "report_status": status,
        "executed": True,
        "exit_code": proc.exit_code,
        "duration_ms": proc.duration_ms,
        "stderr": _public_log(proc.stderr, workspace, artifact_root),
        "artifacts": {
            "report": run_id + "/coverage_report.json",
            "raw": run_id + "/coverage.dat",
            **({"lcov": run_id + "/coverage.info"} if status == "READY" else {}),
        },
    }
    if status == "READY":
        result["summary"] = parsed
    _save_artifact(folder / "coverage_report.json", json.dumps(result, ensure_ascii=False, indent=2))
    return result
