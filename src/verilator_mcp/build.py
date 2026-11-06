"""Отдельная безопасная сборка SystemVerilog testbench без его исполнения."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

from .execution import MAX_LOG_BYTES, ProcessResult, run_bounded
from .lint import (
    _VERILATOR_VERSION, _arguments, _hash_sources, _public_text,
    _save_artifact, find_verilator,
)
from .workspace import ManifestError, RTLProject, validate_manifest


def _trusted_toolchain() -> dict[str, Path] | None:
    """Инструменты из операторского PATH, не из пользовательского MCP-запроса."""
    found: dict[str, Path] = {}
    for name, candidates in {
        "make": ("make",),
        "compiler": ("c++", "g++", "clang++"),
    }.items():
        path = next((shutil.which(candidate) for candidate in candidates if shutil.which(candidate)), None)
        if path is None:
            return None
        resolved = Path(path).resolve()
        if not resolved.is_file() or (os.name == "nt" and resolved.suffix.lower() != ".exe"):
            return None
        found[name] = resolved
    return found


def _hash_file(path: Path, max_bytes: int = 268_435_456) -> str:
    """Хеш бинарника с ограниченным чтением (не следует считать подписью)."""
    if not path.is_file() or path.stat().st_size > max_bytes:
        raise ManifestError("Бинарник отсутствует или превышает допустимый размер")
    digest = hashlib.sha256()
    read_bytes = 0
    with path.open("rb") as handle:
        while chunk := handle.read(65_536):
            read_bytes += len(chunk)
            if read_bytes > max_bytes:
                raise ManifestError("Бинарник изменился или превысил лимит")
            digest.update(chunk)
    return digest.hexdigest()


def _build_arguments(
    project: RTLProject, folder: Path, *, coverage_line: bool = False, assertions: bool = True,
) -> list[str]:
    args = _arguments(project, folder)
    args[0] = "--binary"
    args.insert(1, "--timing")
    if assertions:
        args.insert(2, "--assert")
    if coverage_line:
        args.insert(2, "--coverage-line")
    args[args.index("--top-module") + 1] = project.testbench_top
    return args


def _output_binary(project: RTLProject, folder: Path) -> Path:
    name = "V" + project.testbench_top + (".exe" if os.name == "nt" else "")
    candidate = folder / "obj" / name
    if not candidate.is_file():
        raise ManifestError("Исполняемый файл сборки не обнаружен")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(folder.resolve(strict=True)):
        raise ManifestError("Исполняемый файл выходит за пределы артефактов")
    return resolved


async def build_run_project(
    manifest_path: str, timeout_seconds: int = 180,
    coverage_line: bool = False, assertions: bool = True,
) -> dict[str, object]:
    """Сборка SV testbench, не выполняющая полученный бинарник."""
    if type(timeout_seconds) is not int or not 10 <= timeout_seconds <= 600:
        raise ManifestError("timeout_seconds для сборки должен быть целым 10..600")
    if type(coverage_line) is not bool or type(assertions) is not bool:
        raise ManifestError("coverage_line и assertions должны быть булевыми значениями")
    project = validate_manifest(manifest_path)
    if not project.testbench_top:
        raise ManifestError("Для сборки требуется testbench_top в manifest")

    config = project.public_summary()
    hashes = _hash_sources(project)
    executable = find_verilator()
    if executable is None:
        return {
            "operation": "build", "build_status": "NOT_AVAILABLE",
            "executed": False, "simulation_status": "NOT_RUN",
            "verification_verdict": "NOT_RUN",
        }
    toolchain = _trusted_toolchain()
    if toolchain is None:
        return {
            "operation": "build", "build_status": "TOOLCHAIN_NOT_AVAILABLE",
            "executed": False, "simulation_status": "NOT_RUN",
            "verification_verdict": "NOT_RUN",
        }
    # Уникальная новая директория, без перезаписи пользовательских артефактов.
    run_id = "build-" + uuid.uuid4().hex
    folder = project.artifact_root / run_id
    folder.mkdir(mode=0o700, exist_ok=False)

    args = _build_arguments(project, folder, coverage_line=coverage_line, assertions=assertions)
    build_request = {
        **config, "build_id": run_id,
        "argv": ["<VERILATOR>", *[_public_text(x, project, executable) for x in args]],
        "source_sha256": hashes,
        "source_hash_scope": "explicit_sources_only",
        "timeout_seconds": timeout_seconds,
        "coverage_line_enabled": coverage_line,
        "assertions_enabled": assertions,
    }
    _save_artifact(folder / "request.json", json.dumps(build_request, indent=2, ensure_ascii=False))

    def skipped(reason: str) -> dict[str, object]:
        result: dict[str, object] = {
            "operation": "build", "build_status": "NOT_RUN",
            "executed": False, "simulation_status": "NOT_RUN",
            "verification_verdict": "NOT_RUN",
            "build_id": run_id, "reason": reason,
            "artifacts": {"result": run_id + "/result.json"},
        }
        _save_artifact(folder / "result.json", json.dumps(result, indent=2, ensure_ascii=False))
        return result

    try:
        version_probe = await run_bounded([str(executable), "--version"], folder, 10)
        version = version_probe.stdout.strip().splitlines()[:1]
        tool_version = version[0] if version else ""
        if (
            version_probe.timed_out or version_probe.exit_code != 0
            or not _VERILATOR_VERSION.match(tool_version)
        ):
            return skipped("VERILATOR_VERSION_UNVERIFIED")
        versions: dict[str, str] = {"verilator": tool_version}
        tool_hashes = {"verilator": _hash_file(executable)}
        for role, path in toolchain.items():
            probe = await run_bounded([str(path), "--version"], folder, 10)
            if probe.exit_code != 0 or probe.timed_out:
                return skipped("TOOLCHAIN_VERSION_UNVERIFIED")
            first = (probe.stdout or probe.stderr).strip().splitlines()[:1]
            if not first:
                return skipped("TOOLCHAIN_VERSION_UNVERIFIED")
            versions[role] = first[0]
            tool_hashes[role] = _hash_file(path)
    except (OSError, ManifestError):
        return skipped("TOOLCHAIN_PROBE_FAILED")

    try:
        proc = await run_bounded(
            [str(executable), *args], folder, timeout_seconds,
            max_log_bytes=MAX_LOG_BYTES,
        )
    except OSError:
        return skipped("VERILATOR_BUILD_EXECUTION_FAILED")

    changed = False
    try:
        changed = (
            hashes != _hash_sources(project)
            or config["config_sha256"]
            != validate_manifest(project.relative(project.manifest)).public_summary()["config_sha256"]
        )
    except ManifestError:
        changed = True

    binary: Path | None = None
    binary_hash: str | None = None
    binary_error = False
    if not proc.timed_out and proc.exit_code == 0:
        try:
            binary = _output_binary(project, folder)
            binary_hash = _hash_file(binary)
        except (ManifestError, OSError):
            binary_error = True

    truncated = proc.stdout_truncated or proc.stderr_truncated
    if changed:
        status = "INPUT_CHANGED"
    elif proc.timed_out:
        status = "TIMEOUT"
    elif proc.exit_code is None:
        status = "NOT_RUN"
    elif proc.exit_code != 0:
        status = "BUILD_FAIL"
    elif truncated:
        status = "INCOMPLETE"
    elif binary_error:
        status = "ARTIFACT_MISSING_OR_UNSAFE"
    else:
        status = "PASS"

    _save_artifact(folder / "stdout.log", proc.stdout)
    _save_artifact(folder / "stderr.log", proc.stderr)
    result = {
        "operation": "build",
        "build_status": status,
        "executed": True,
        "exit_code": proc.exit_code,
        "timed_out": proc.timed_out,
        "duration_ms": proc.duration_ms,
        "logs_truncated": truncated,
        "build_id": run_id,
        "coverage_line_enabled": coverage_line,
        "assertions_enabled": assertions,
        "tool_versions": versions,
        "tool_sha256": tool_hashes,
        "config_sha256": config["config_sha256"],
        "source_sha256": hashes,
        "source_hash_scope": "explicit_sources_only",
        "binary_sha256": binary_hash if status == "PASS" else None,
        "binary_artifact": (
            binary.relative_to(project.artifact_root).as_posix()
            if status == "PASS" and binary else None
        ),
        "simulation_status": "NOT_RUN",
        "verification_verdict": "NOT_RUN",
        "stdout": _public_text(proc.stdout, project, executable),
        "stderr": _public_text(proc.stderr, project, executable),
        "artifacts": {
            "request": run_id + "/request.json",
            "result": run_id + "/result.json",
            "stdout": run_id + "/stdout.log",
            "stderr": run_id + "/stderr.log",
        },
    }
    _save_artifact(folder / "result.json", json.dumps(result, ensure_ascii=False, indent=2))
    return result
