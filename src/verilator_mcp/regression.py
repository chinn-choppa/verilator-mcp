"""Последовательные воспроизводимые RTL-регрессии без произвольных команд."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .lint import _save_artifact
from .simulation import _artifacts, _validated_build, simulation_run_project
from .workspace import ManifestError

MAX_CASES = 8
_BUILD_ID = re.compile(r"build-[0-9a-f]{32}\Z")


class RegressionCase(BaseModel):
    """Один запуск только проверенной сборки с явно записанным seed."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    build_id: str = Field(min_length=38, max_length=38, pattern=r"^build-[0-9a-f]{32}$")
    seed: int = Field(default=1, ge=1, le=2_147_483_647)


def _aggregate(items: list[dict[str, object]]) -> tuple[str, dict[str, int]]:
    counts = {"PASS": 0, "FAIL": 0, "INCONCLUSIVE": 0, "NOT_RUN": 0}
    for item in items:
        verdict = item["verification_verdict"]
        if verdict not in counts:
            raise ValueError("Неизвестный результат внутренней симуляции")
        counts[verdict] += 1
    if counts["FAIL"]:
        return "FAIL", counts
    if counts["NOT_RUN"]:
        return "INCOMPLETE", counts
    if counts["INCONCLUSIVE"]:
        return "INCONCLUSIVE", counts
    if counts["PASS"] == len(items) and items:
        return "PASS", counts
    return "NOT_RUN", counts


async def regression_run_project(
    cases: list[RegressionCase], timeout_seconds: int = 30,
) -> dict[str, object]:
    """Последовательно запустить ≤8 проверенных сборок и сохранить доказательства.

    Один успешный build не становится успешным testcase. Все seeds и результаты
    симуляции сохраняются независимо. Система не подменяет пропущенные тесты PASS.
    """
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ManifestError("Нужен список от 1 до 8 тестовых случаев")
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 60:
        raise ManifestError("timeout_seconds должен быть целым от 1 до 60")
    if not all(isinstance(item, RegressionCase) for item in cases):
        raise ManifestError("Каждый случай должен содержать проверенные build_id и seed")

    _, artifact_root = _artifacts()
    # Проверить *все* build IDs до первого исполнения. Отсутствующий build
    # не должен приводить к частичной регрессии, выданной за успешную.
    for case in cases:
        if not _BUILD_ID.fullmatch(case.build_id):
            raise ManifestError("Недопустимый build_id")
        _validated_build(artifact_root, case.build_id)

    regression_id = "reg-" + uuid.uuid4().hex
    folder = artifact_root / regression_id
    folder.mkdir(mode=0o700, exist_ok=False)
    request = {
        "regression_id": regression_id,
        "schema_version": 1,
        "cases": [
            {"build_id": case.build_id, "seed": case.seed} for case in cases
        ],
        "timeout_seconds_per_case": timeout_seconds,
        "execution_order": "sequential",
        "verdict_semantics": "from simulation_run, not build success",
    }
    _save_artifact(folder / "request.json", json.dumps(request, ensure_ascii=False, indent=2))

    results: list[dict[str, object]] = []
    try:
        for index, case in enumerate(cases):
            try:
                sim = await simulation_run_project(
                    case.build_id, timeout_seconds=timeout_seconds, seed=case.seed
                )
                row: dict[str, object] = {
                    "index": index,
                    "build_id": case.build_id,
                    "build_status": "PASS",
                    "seed": case.seed,
                    "simulation_status": sim["run_status"],
                    "verification_verdict": sim["verification_verdict"],
                    "simulation_id": sim.get("run_id"),
                    "simulation_artifact": sim.get("artifacts", {}).get("result"),
                    "exit_code": sim.get("exit_code"),
                    "executed": sim["executed"],
                }
            except (ManifestError, OSError):
                # TOCTOU/удалённый артефакт в процессе регрессии; зафиксировать
                # NOT_RUN и не продолжать выполнять сомнительные бинарники.
                row = {
                    "index": index, "build_id": case.build_id, "build_status": "UNVERIFIED",
                    "seed": case.seed, "simulation_status": "NOT_RUN",
                    "verification_verdict": "NOT_RUN", "executed": False,
                    "reason": "BUILD_INVALIDATED",
                }
                results.append(row)
                for pending_index in range(index + 1, len(cases)):
                    pending = cases[pending_index]
                    results.append({
                        "index": pending_index, "build_id": pending.build_id,
                        "seed": pending.seed, "build_status": "NOT_RECHECKED",
                        "simulation_status": "NOT_RUN",
                        "verification_verdict": "NOT_RUN", "executed": False,
                        "reason": "PREVIOUS_CASE_INVALIDATED",
                    })
                break
            results.append(row)
    except asyncio.CancelledError:
        status, counts = _aggregate(results) if results else ("NOT_RUN", {
            "PASS": 0, "FAIL": 0, "INCONCLUSIVE": 0, "NOT_RUN": 0
        })
        cancelled = {
            "regression_id": regression_id, "status": "CANCELLED",
            "completed_cases": len(results), "requested_cases": len(cases),
            "partial_status": status, "counts": counts, "cases": results,
        }
        _save_artifact(
            folder / "result.json", json.dumps(cancelled, ensure_ascii=False, indent=2)
        )
        raise

    status, counts = _aggregate(results)
    output = {
        "operation": "regression",
        "regression_id": regression_id,
        "regression_status": status,
        "verification_verdict": (
            status if status in ("PASS", "FAIL", "INCONCLUSIVE") else "NOT_RUN"
        ),
        "requested_cases": len(cases),
        "completed_cases": len(results),
        "counts": counts,
        "cases": results,
        "replay": request["cases"],
        "timeout_seconds_per_case": timeout_seconds,
        "artifacts": {
            "request": regression_id + "/request.json",
            "result": regression_id + "/result.json",
        },
    }
    _save_artifact(folder / "result.json", json.dumps(output, ensure_ascii=False, indent=2))
    return output
