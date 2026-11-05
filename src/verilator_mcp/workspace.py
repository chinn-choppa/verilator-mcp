"""Строгий read-only контракт RTL-проекта; никакого выполнения EDA."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

MAX_MANIFEST_BYTES = 65_536
MAX_SOURCES = 512
MAX_INCLUDES = 64
MAX_FILELISTS = 64
MAX_DEPTH = 8
_IDENTIFIER = re.compile(r"[a-zA-Z_][a-zA-Z0-9_$]*\Z")
_DEFINE_VALUE = re.compile(r"[a-zA-Z0-9_]*\Z")
_FORBIDDEN_WINDOWS = frozenset('<>:"\\|?*')
_RESERVED_WINDOWS = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class ManifestError(ValueError):
    """Некорректная или небезопасная конфигурация проекта."""


@dataclass(frozen=True)
class RTLProject:
    """Уже проверенная конфигурация; пути абсолютны только внутри процесса."""

    workspace: Path
    artifact_root: Path
    manifest: Path
    top: str
    sources: tuple[Path, ...]
    include_dirs: tuple[Path, ...]
    defines: tuple[tuple[str, str], ...]
    parameters: tuple[tuple[str, int], ...]
    testbench_top: str | None

    def relative(self, path: Path) -> str:
        return path.relative_to(self.workspace).as_posix()

    def public_summary(self) -> dict[str, object]:
        """Отдавать клиенту переносимые относительные пути без корней ФС."""
        config = {
            "schema_version": 1,
            "top": self.top,
            "sources": [self.relative(p) for p in self.sources],
            "include_dirs": [self.relative(p) for p in self.include_dirs],
            "defines": dict(self.defines),
            "parameters": dict(self.parameters),
            "testbench_top": self.testbench_top,
        }
        encoded = json.dumps(config, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return {
            "state": "VALID",
            "executed": False,
            "manifest": self.relative(self.manifest),
            "config_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            "project": config,
        }


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError("Повторяющееся поле JSON: " + key)
        result[key] = value
    return result


def _relative_name(value: object, suffixes: frozenset[str] | None = None) -> PurePosixPath:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ManifestError("Путь должен быть непустой строкой не длиннее 512 символов")
    if (
        any(ord(ch) < 32 for ch in value)
        or any(ch in _FORBIDDEN_WINDOWS for ch in value)
        or value.strip() != value
    ):
        raise ManifestError("Недопустимые символы в пути")
    path = PurePosixPath(value)
    if (
        path.is_absolute() or value.startswith("/")
        or path.as_posix() != value
        or any(p in ("", ".", "..") for p in value.split("/"))
    ):
        raise ManifestError("Разрешены только нормализованные относительные пути без '..'")
    for component in path.parts:
        if component.rstrip(" .") != component:
            raise ManifestError("Недопустимое окончание компонента пути Windows")
        if component.split(".", 1)[0].upper() in _RESERVED_WINDOWS:
            raise ManifestError("Зарезервированное имя устройства Windows")
    if suffixes is not None and path.suffix.lower() not in suffixes:
        raise ManifestError("Недопустимое расширение файла")
    return path


def _inside(root: Path, relative: object, *, kind: str, suffixes: frozenset[str] | None = None) -> Path:
    path = _relative_name(relative, suffixes)
    try:
        resolved = root.joinpath(*path.parts).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ManifestError(f"Недоступный путь типа {kind}") from exc
    if not resolved.is_relative_to(root):
        raise ManifestError("Путь или символьная ссылка выходит за пределы workspace")
    if kind == "directory" and not resolved.is_dir():
        raise ManifestError("Ожидался каталог")
    if kind == "file" and not resolved.is_file():
        raise ManifestError("Ожидался обычный файл")
    return resolved


def _root_from_env(name: str, value: str | None) -> Path:
    if not value:
        raise ManifestError(f"Переменная {name} должна быть задана администратором MCP")
    path = Path(value)
    if not path.is_absolute():
        raise ManifestError(f"Корень {name} обязан быть абсолютным")
    try:
        path = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ManifestError(f"Недоступный корень {name}") from exc
    if not path.is_dir():
        raise ManifestError(f"Корень {name} должен быть каталогом")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_MANIFEST_BYTES + 1)
        if len(data) > MAX_MANIFEST_BYTES:
            raise ManifestError("JSON manifest превышает 64 КиБ")
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("Недоступный, некорректный или не-UTF-8 manifest") from exc
    if not isinstance(document, dict):
        raise ManifestError("Корень manifest должен быть JSON-объектом")
    return document


def _check_keys(data: dict[str, Any], *, root: bool) -> None:
    allowed = {"schema_version", "sources", "include_dirs", "filelists"}
    if root:
        allowed |= {"top", "defines", "parameters", "testbench_top"}
    if set(data) - allowed:
        raise ManifestError("Неизвестное поле manifest: " + sorted(set(data) - allowed)[0])
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ManifestError("Поддерживается только schema_version=1")


def _strings(data: dict[str, Any], name: str) -> list[str]:
    value = data.get(name, [])
    if not isinstance(value, list) or any(not isinstance(p, str) for p in value):
        raise ManifestError(f"Поле {name} должно быть массивом строк")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) > 128 or not _IDENTIFIER.fullmatch(value):
        raise ManifestError(f"Недопустимый идентификатор: {label}")
    return value


def _defined(data: dict[str, Any], key: str, *, parameter: bool) -> tuple[tuple[str, Any], ...]:
    values = data.get(key, {})
    if not isinstance(values, dict) or len(values) > 128:
        raise ManifestError(f"{key}: ожидается JSON-объект до 128 ключей")
    result: list[tuple[str, Any]] = []
    for name, value in sorted(values.items()):
        _identifier(name, key)
        if parameter:
            if type(value) is not int or not 0 <= value <= 2_147_483_647:
                raise ManifestError("Параметры должны быть неотрицательными целыми <= 2^31-1")
        else:
            if not isinstance(value, str) or len(value) > 64 or not _DEFINE_VALUE.fullmatch(value):
                raise ManifestError("Значения defines: только ASCII буквы, цифры и '_'")
        result.append((name, value))
    return tuple(result)


def validate_manifest(
    manifest_path: str,
    *,
    workspace_root: str | None = None,
    artifact_root: str | None = None,
) -> RTLProject:
    """Валидация без создания файлов/каталогов и без запуска процессов.

    Корни выбирает оператор через переменные окружения, не MCP-клиент.
    """
    workspace = _root_from_env(
        "VERILATOR_MCP_WORKSPACE_ROOT",
        workspace_root if workspace_root is not None else os.getenv("VERILATOR_MCP_WORKSPACE_ROOT"),
    )
    artifacts = _root_from_env(
        "VERILATOR_MCP_ARTIFACT_ROOT",
        artifact_root if artifact_root is not None else os.getenv("VERILATOR_MCP_ARTIFACT_ROOT"),
    )
    if workspace.is_relative_to(artifacts) or artifacts.is_relative_to(workspace):
        raise ManifestError("Workspace и каталог артефактов обязаны быть раздельными")
    root_manifest = _inside(
        workspace, manifest_path, kind="file", suffixes=frozenset({".json"})
    )
    sources: list[Path] = []
    includes: list[Path] = []
    visited_files: set[Path] = set()
    active: set[Path] = set()
    seen_sources: set[Path] = set()
    seen_includes: set[Path] = set()

    def visit(path: Path, depth: int, *, is_root: bool = False) -> dict[str, Any]:
        if depth > MAX_DEPTH:
            raise ManifestError("Слишком глубокая вложенность filelists")
        if path in active:
            raise ManifestError("Циклическая ссылка filelist")
        if path in visited_files or len(visited_files) >= MAX_FILELISTS:
            raise ManifestError("Повторный или избыточный filelist")
        active.add(path)
        visited_files.add(path)
        try:
            data = _read_json(path)
            _check_keys(data, root=is_root)
            for name in _strings(data, "filelists"):
                target = _inside(
                    workspace, name, kind="file", suffixes=frozenset({".json"})
                )
                visit(target, depth + 1)
            for name in _strings(data, "sources"):
                source = _inside(
                    workspace, name, kind="file", suffixes=frozenset({".v", ".sv"})
                )
                if source in seen_sources or len(sources) >= MAX_SOURCES:
                    raise ManifestError("Повторённый или избыточный RTL source")
                seen_sources.add(source)
                sources.append(source)
            for name in _strings(data, "include_dirs"):
                include = _inside(workspace, name, kind="directory")
                if include not in seen_includes:
                    if len(includes) >= MAX_INCLUDES:
                        raise ManifestError("Слишком много include_dirs")
                    seen_includes.add(include)
                    includes.append(include)
            return data
        finally:
            active.remove(path)

    root_data = visit(root_manifest, 0, is_root=True)
    if not sources:
        raise ManifestError("Нужен хотя бы один RTL source")
    top = _identifier(root_data.get("top"), "top")
    testbench = root_data.get("testbench_top")
    if testbench is not None:
        testbench = _identifier(testbench, "testbench_top")
    return RTLProject(
        workspace=workspace,
        artifact_root=artifacts,
        manifest=root_manifest,
        top=top,
        sources=tuple(sources),
        include_dirs=tuple(includes),
        defines=_defined(root_data, "defines", parameter=False),
        parameters=_defined(root_data, "parameters", parameter=True),
        testbench_top=testbench,
    )
