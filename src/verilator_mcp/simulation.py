"""Выполнение только ранее собранных проверенных бинарников, без shell."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from .build import _hash_file
from .execution import MAX_LOG_BYTES, ProcessResult, run_bounded
from .lint import _save_artifact
from .workspace import ManifestError, _identifier, _root_from_env, _unique_object

_BUILD_ID = re.compile(r"build-[0-9a-f]{32}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_RECORD_BYTES = 262_144


def _read_record(folder: Path, name: str) -> dict[str, Any]:
    """Проверить абсолютный путь и размер локальной записи до разбора JSON."""
    path = (folder / name).resolve(strict=True)
    if not path.is_relative_to(folder) or not path.is_file():
        raise ManifestError("Запись сборки выходит за пределы разрешённой директории")
    try:
        if path.stat().st_size > MAX_RECORD_BYTES:
            raise ManifestError("Размер файла записи сборки превышает лимит")
        with path.open("rb") as stream:
            data = stream.read(MAX_RECORD_BYTES + 1)
        if len(data) > MAX_RECORD_BYTES:
            raise ManifestError("Превышен лимит JSON-записи сборки")
        record = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ManifestError("Недоступная или повреждённая запись сборки") from exc
    if not isinstance(record, dict):
        raise ManifestError("Запись сборки должна быть JSON-объектом")
    return record


def _artifacts() -> tuple[Path, Path]:
    """Корни задаёт только оператор MCP, не клиент."""
    workspace = _root_from_env("VERILATOR_MCP_WORKSPACE_ROOT", os.getenv("VERILATOR_MCP_WORKSPACE_ROOT"))
    artifacts = _root_from_env("VERILATOR_MCP_ARTIFACT_ROOT", os.getenv("VERILATOR_MCP_ARTIFACT_ROOT"))
    if workspace.is_relative_to(artifacts) or artifacts.is_relative_to(workspace):
        raise ManifestError("Workspace и каталог артефактов не могут пересекаться")
    return workspace, artifacts


def _validated_build(
    artifact_root: Path, build_id: str,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Не доверять сохранённому имени исполняемого файла: вычислить его заново."""
    if not isinstance(build_id, str) or not _BUILD_ID.fullmatch(build_id):
        raise ManifestError("Некорректный build_id")
    folder = (artifact_root / build_id).resolve(strict=True)
    if folder.parent != artifact_root or not folder.is_dir():
        raise ManifestError("Каталог сборки находится вне разрешённого корня")

    request = _read_record(folder, "request.json")
    result = _read_record(folder, "result.json")
    if (
        result.get("build_id") != build_id
        or request.get("build_id") != build_id
        or result.get("build_status") != "PASS"
        or result.get("executed") is not True
        or result.get("simulation_status") != "NOT_RUN"
    ):
        raise ManifestError("Нельзя запускать неподтверждённую сборку")
    project = request.get("project")
    if not isinstance(project, dict):
        raise ManifestError("Отсутствует описание проекта в записи сборки")
    top = _identifier(project.get("testbench_top"), "testbench_top")
    expected = f"{build_id}/obj/V{top}" + (".exe" if os.name == "nt" else "")
    if result.get("binary_artifact") != expected:
        raise ManifestError("Несоответствие имени исполняемого файла")
    if (
        request.get("config_sha256") != result.get("config_sha256")
        or request.get("source_sha256") != result.get("source_sha256")
        or not isinstance(result.get("binary_sha256"), str)
        or not _SHA256.fullmatch(result["binary_sha256"])
    ):
        raise ManifestError("Несоответствие идентификаторов исходников и бинарника")
    for key in ("coverage_line_enabled", "assertions_enabled"):
        if request.get(key, False) is not result.get(key, False):
            raise ManifestError("Несогласованные флаги инструментированной сборки")
        if type(result.get(key, False)) is not bool:
            raise ManifestError("Некорректный флаг инструментирования")
    versions = result.get("tool_versions")
    hashes = result.get("tool_sha256")
    if (
        not isinstance(versions, dict) or not isinstance(hashes, dict)
        or any(role not in versions or role not in hashes for role in ("verilator", "make", "compiler"))
        or any(not isinstance(hashes[role], str) or not _SHA256.fullmatch(hashes[role])
               for role in ("verilator", "make", "compiler"))
    ):
        raise ManifestError("В записи сборки нет подтверждённого происхождения")

    executable = (folder / "obj" / ("V" + top + (".exe" if os.name == "nt" else ""))).resolve(strict=True)
    if executable.parent != folder / "obj" or not executable.is_file():
        raise ManifestError("Подозрительный путь исполняемого файла")
    return executable, request, result


def _public_log(text: str, workspace: Path, artifact_root: Path) -> str:
    for value, alias in sorted(
        ((str(workspace), "<WORKSPACE>"), (str(artifact_root), "<ARTIFACTS>")),
        key=lambda x: len(x[0]), reverse=True,
    ):
        text = text.replace(value, alias).replace(value.replace("\\", "/"), alias)
    return text


def _classify_run(
    proc: ProcessResult, expected_marker: str, *, binary_changed: bool,
) -> tuple[str, str, bool, bool, bool]:
    """Exit 0 НЕ является основанием для verification PASS."""
    log = proc.stdout + "\n" + proc.stderr
    finish = "Verilog $finish" in log
    fatal = any(x in log for x in ("$fatal", "%Error", "Assertion failed", "Verilog $stop"))
    marker = expected_marker in proc.stdout.splitlines()
    truncated = proc.stdout_truncated or proc.stderr_truncated

    if binary_changed:
        return "BINARY_CHANGED", "INCONCLUSIVE", finish, fatal, marker
    if proc.timed_out:
        return "TIMEOUT", "FAIL", finish, fatal, marker
    if proc.exit_code is None:
        return "NOT_RUN", "NOT_RUN", finish, fatal, marker
    if proc.exit_code != 0 or fatal:
        return "RUN_FAIL", "FAIL", finish, fatal, marker
    if truncated:
        return "INCOMPLETE", "INCONCLUSIVE", finish, fatal, marker
    if marker and finish:
        return "PASS", "PASS", finish, fatal, marker
    if finish:
        return "FINISHED_UNVERIFIED", "INCONCLUSIVE", finish, fatal, marker
    return "EXIT_ZERO_UNVERIFIED", "INCONCLUSIVE", finish, fatal, marker


def _raw_coverage_state(folder: Path, enabled: bool) -> str:
    """Факт обнаружения артефакта; не приравнивать отсутствие к нулевому покрытию."""
    if not enabled:
        return "DISABLED"
    path = folder / "coverage.dat"
    if not path.exists():
        return "NOT_OBSERVED"
    try:
        checked = path.resolve(strict=True)
        if checked.parent != folder or not checked.is_file():
            return "UNSAFE"
        size = checked.stat().st_size
    except (OSError, RuntimeError):
        return "UNREADABLE"
    if size == 0:
        return "EMPTY"
    if size > 16_777_216:
        return "TOO_LARGE"
    return "RECORDED"


async def simulation_run_project(
    build_id: str, timeout_seconds: int = 30, seed: int = 1,
) -> dict[str, object]:
    """Запустить только разрешённый бинарник из build_run с проверенным SHA-256."""
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 180:
        raise ManifestError("timeout_seconds должен быть целым числом от 1 до 180")
    if type(seed) is not int or not 1 <= seed <= 2_147_483_647:
        raise ManifestError("seed должен быть целым числом от 1 до 2147483647")
    workspace, artifact_root = _artifacts()
    binary, request, build = _validated_build(artifact_root, build_id)

    try:
        if _hash_file(binary) != build["binary_sha256"]:
            return {
                "operation": "simulation", "run_status": "ARTIFACT_INVALID",
                "verification_verdict": "NOT_RUN", "executed": False,
                "build_id": build_id, "seed": seed, "reason": "BINARY_SHA256_MISMATCH",
            }
    except (OSError, ManifestError):
        return {
            "operation": "simulation", "run_status": "ARTIFACT_INVALID",
            "verification_verdict": "NOT_RUN", "executed": False,
            "build_id": build_id, "seed": seed, "reason": "BINARY_UNREADABLE",
        }

    run_id = "sim-" + uuid.uuid4().hex
    nonce = uuid.uuid4().hex
    folder = artifact_root / run_id
    folder.mkdir(mode=0o700, exist_ok=False)
    argv = [
        str(binary),
        "+verilator+seed+" + str(seed),
        "+VERILATOR_MCP_TOKEN=" + nonce,
    ]
    coverage_enabled = build.get("coverage_line_enabled", False)
    # Старые Verilator (включая 5.020) не поддерживают runtime-ключ
    # +verilator+coverage+file+... . Используем стандартное coverage.dat
    # в уникальном cwd каждой симуляции, не доверяя путь MCP-клиенту.
    evidence = {
        "run_id": run_id, "build_id": build_id, "seed": seed,
        "command": ["<BUILT_BINARY>", argv[1], "+VERILATOR_MCP_TOKEN=<PER_RUN_TOKEN>"],
        "binary_sha256": build["binary_sha256"],
        "config_sha256": request["config_sha256"],
        "tool_versions": build["tool_versions"],
        "timeout_seconds": timeout_seconds,
        "criterion": "exit_code==0 AND exact token line AND Verilog $finish",
        "coverage_line_enabled": coverage_enabled,
        "coverage_file": "coverage.dat" if coverage_enabled else None,
        "assertions_enabled": build.get("assertions_enabled", False),
    }
    _save_artifact(folder / "request.json", json.dumps(evidence, ensure_ascii=False, indent=2))
    try:
        proc = await run_bounded(argv, folder, timeout_seconds, max_log_bytes=MAX_LOG_BYTES)
    except OSError:
        result: dict[str, object] = {
            "operation": "simulation", "run_status": "NOT_RUN",
            "verification_verdict": "NOT_RUN", "executed": False,
            "run_id": run_id, "build_id": build_id, "seed": seed,
            "reason": "EXECUTION_FAILED",
            "artifacts": {"result": run_id + "/result.json"},
        }
        _save_artifact(folder / "result.json", json.dumps(result, ensure_ascii=False, indent=2))
        return result

    try:
        binary_changed = _hash_file(binary) != build["binary_sha256"]
    except (OSError, ManifestError):
        binary_changed = True
    status, verdict, finish, fatal, marker = _classify_run(
        proc, "VERILATOR_MCP_PASS:" + nonce, binary_changed=binary_changed
    )
    coverage_state = _raw_coverage_state(folder, coverage_enabled)
    assertion_state = (
        "NOT_ENABLED" if not build.get("assertions_enabled", False)
        else "FAILURE_OBSERVED" if "Assertion failed" in proc.stdout + proc.stderr
        else "NO_FAILURE_OBSERVED"
    )
    result = {
        "operation": "simulation",
        "run_status": status,
        "verification_verdict": verdict,
        "executed": True,
        "run_id": run_id,
        "build_id": build_id,
        "seed": seed,
        "exit_code": proc.exit_code,
        "duration_ms": proc.duration_ms,
        "timed_out": proc.timed_out,
        "logs_truncated": proc.stdout_truncated or proc.stderr_truncated,
        "finish_observed": finish,
        "fatal_observed": fatal,
        "pass_marker_observed": marker,
        "coverage_status": coverage_state,
        "assertion_observation": assertion_state,
        "binary_sha256": build["binary_sha256"],
        "config_sha256": request["config_sha256"],
        "tool_versions": build["tool_versions"],
        "tool_sha256": build["tool_sha256"],
        "stdout": _public_log(proc.stdout, workspace, artifact_root),
        "stderr": _public_log(proc.stderr, workspace, artifact_root),
        "artifacts": {
            "request": run_id + "/request.json",
            "result": run_id + "/result.json",
            "stdout": run_id + "/stdout.log",
            "stderr": run_id + "/stderr.log",
            **({"coverage_raw": run_id + "/coverage.dat"} if coverage_state == "RECORDED" else {}),
        },
    }
    _save_artifact(folder / "stdout.log", proc.stdout)
    _save_artifact(folder / "stderr.log", proc.stderr)
    _save_artifact(folder / "result.json", json.dumps(result, ensure_ascii=False, indent=2))
    return result
