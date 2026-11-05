"""Настоящий, ограниченный Verilator lint: без shell, build или симуляции."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path

from .diagnostics import parse_diagnostics_text
from .execution import MAX_LOG_BYTES, ProcessResult, run_bounded
from .workspace import ManifestError, RTLProject, validate_manifest

MAX_INPUT_BYTES = 268_435_456
MAX_SINGLE_SOURCE_BYTES = 33_554_432
_VERILATOR_VERSION = re.compile(r"^Verilator\s+\d", re.IGNORECASE)
_ALLOWED_POSIX = frozenset({"verilator", "verilator_bin"})
_ALLOWED_WINDOWS = frozenset({"verilator.exe", "verilator_bin.exe"})


def find_verilator() -> Path | None:
    """Путь к бинарнику выбирает локальный оператор, никогда MCP-клиент."""
    configured = os.getenv("VERILATOR_MCP_EXECUTABLE")
    name = configured if configured is not None else shutil.which("verilator")
    if not name:
        return None
    path = Path(name)
    # Windows .bat/.cmd can implicitly invoke a command shell even with shell=False.
    if not path.is_absolute():
        return None
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not resolved.is_file():
        return None
    allowed = _ALLOWED_WINDOWS if os.name == "nt" else _ALLOWED_POSIX
    if path.name.lower() not in allowed or resolved.name.lower() not in allowed:
        return None
    if os.name != "nt" and not os.access(resolved, os.X_OK):
        return None
    return resolved


def _hash_sources(project: RTLProject) -> dict[str, str]:
    hashes: dict[str, str] = {}
    total = 0
    for path in project.sources:
        try:
            size = path.stat().st_size
            if size > MAX_SINGLE_SOURCE_BYTES or total + size > MAX_INPUT_BYTES:
                raise ManifestError("Превышен лимит размера RTL-исходников")
            checksum = hashlib.sha256()
            read_size = 0
            with path.open("rb") as source:
                while data := source.read(65_536):
                    read_size += len(data)
                    if read_size > MAX_SINGLE_SOURCE_BYTES or total + read_size > MAX_INPUT_BYTES:
                        raise ManifestError("RTL-источник изменился или превышает лимит размера")
                    checksum.update(data)
            total += read_size
        except (OSError, RuntimeError) as exc:
            raise ManifestError("Не удалось прочитать разрешённый RTL-источник") from exc
        hashes[project.relative(path)] = checksum.hexdigest()
    return hashes


def _arguments(project: RTLProject, cwd: Path) -> list[str]:
    """Аргументы полностью собираются сервером из валидированного контракта."""
    argv = [
        "--lint-only", "--sv", "-Wall", "-Wno-fatal",
        "--top-module", project.top, "--Mdir", str(cwd / "obj"),
    ]
    argv.extend("-I" + str(p) for p in project.include_dirs)
    argv.extend("-D" + name + "=" + value for name, value in project.defines)
    argv.extend("-G" + name + "=" + str(value) for name, value in project.parameters)
    argv.extend(str(p) for p in project.sources)
    return argv


def _public_text(text: str, project: RTLProject, executable: Path) -> str:
    # Только псевдонимы локальных абсолютных каталогов, без обмана по содержимому.
    paths = [
        (str(project.workspace), "<WORKSPACE>"),
        (str(project.artifact_root), "<ARTIFACTS>"),
        (str(executable), "<VERILATOR>"),
    ]
    for root, alias in sorted(paths, key=lambda item: len(item[0]), reverse=True):
        text = text.replace(root, alias).replace(root.replace("\\", "/"), alias)
    return text


def _save_artifact(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _result_from_process(
    proc: ProcessResult,
    project: RTLProject,
    executable: Path,
    version: str,
    run_id: str,
    folder: Path,
    initial_hashes: dict[str, str],
    config: dict[str, object],
) -> dict[str, object]:
    changed = False
    try:
        changed = (
            initial_hashes != _hash_sources(project)
            or validate_manifest(project.relative(project.manifest)).public_summary()["config_sha256"]
            != config["config_sha256"]
        )
    except ManifestError:
        changed = True
    diagnostic_text = _public_text(proc.stderr + "\n" + proc.stdout, project, executable)
    parsed = parse_diagnostics_text(diagnostic_text, "verilator")
    truncated = proc.stdout_truncated or proc.stderr_truncated or bool(parsed["truncated"])
    errors = any(x["severity"] in ("error", "fatal") for x in parsed["items"])
    warnings = any(x["severity"] == "warning" for x in parsed["items"])
    if changed:
        status = "INPUT_CHANGED"
    elif proc.timed_out:
        status = "TIMEOUT"
    elif proc.exit_code is None:
        status = "NOT_RUN"
    elif proc.exit_code != 0:
        status = "FAIL"
    elif truncated:
        status = "INCOMPLETE"
    elif errors:
        status = "INCONSISTENT_OUTPUT"
    elif warnings:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
    _save_artifact(folder / "stdout.log", proc.stdout)
    _save_artifact(folder / "stderr.log", proc.stderr)
    output = {
        "run_id": run_id,
        "operation": "lint",
        "lint_status": status,
        "verification_verdict": "NOT_RUN",
        "executed": True,
        "exit_code": proc.exit_code,
        "duration_ms": proc.duration_ms,
        "timed_out": proc.timed_out,
        "tool_version": version,
        "config_sha256": config["config_sha256"],
        "source_sha256": initial_hashes,
        "source_hash_scope": "explicit_sources_only",
        "logs_truncated": truncated,
        "diagnostics": parsed,
        "stdout": _public_text(proc.stdout, project, executable),
        "stderr": _public_text(proc.stderr, project, executable),
        "artifacts": {
            "result": run_id + "/result.json",
            "stdout": run_id + "/stdout.log",
            "stderr": run_id + "/stderr.log",
        },
    }
    _save_artifact(folder / "result.json", json.dumps(output, ensure_ascii=False, indent=2))
    return output


async def lint_run_project(manifest_path: str, timeout_seconds: int = 60) -> dict[str, object]:
    """Выполнить только lint на доверенном пути с доказательствами исполнения."""
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 180:
        raise ManifestError("timeout_seconds должен быть целым от 1 до 180")
    project = validate_manifest(manifest_path)
    config = project.public_summary()
    source_hashes = _hash_sources(project)
    executable = find_verilator()
    if executable is None:
        return {
            "operation": "lint", "lint_status": "NOT_AVAILABLE",
            "verification_verdict": "NOT_RUN", "executed": False,
            "tool_version": None, "exit_code": None,
        }

    run_id = "lint-" + uuid.uuid4().hex
    folder = project.artifact_root / run_id
    folder.mkdir(mode=0o700, exist_ok=False)
    argv = _arguments(project, folder)
    safe_args = [_public_text(arg, project, executable) for arg in argv]
    manifest_record = {
        **config,
        "run_id": run_id,
        "argv": ["<VERILATOR>", *safe_args],
        "source_sha256": source_hashes,
        "source_hash_scope": "explicit_sources_only",
        "timeout_seconds": timeout_seconds,
    }
    _save_artifact(folder / "request.json", json.dumps(
        manifest_record, ensure_ascii=False, indent=2
    ))

    def skipped(reason: str, tool_version: str | None = None) -> dict[str, object]:
        output: dict[str, object] = {
            "operation": "lint", "lint_status": "NOT_RUN",
            "verification_verdict": "NOT_RUN", "executed": False,
            "tool_version": tool_version, "exit_code": None,
            "run_id": run_id, "reason": reason,
            "artifacts": {"result": run_id + "/result.json"},
        }
        _save_artifact(folder / "result.json", json.dumps(output, ensure_ascii=False, indent=2))
        return output

    try:
        probe = await run_bounded([str(executable), "--version"], folder, 10)
    except OSError:
        return skipped("VERILATOR_VERSION_PROBE_FAILED")
    version = probe.stdout.strip().splitlines()[:1]
    first_line = version[0] if version else ""
    if probe.timed_out or probe.exit_code != 0 or not _VERILATOR_VERSION.match(first_line):
        return skipped("VERILATOR_VERSION_UNVERIFIED")
    try:
        proc = await run_bounded(
            [str(executable), *argv], folder, timeout_seconds, max_log_bytes=MAX_LOG_BYTES
        )
    except OSError:
        return skipped("VERILATOR_EXECUTION_FAILED", first_line)
    return _result_from_process(
        proc, project, executable, first_line, run_id, folder, source_hashes, config
    )
