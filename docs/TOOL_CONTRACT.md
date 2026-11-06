# Контракт MCP-инструментов v1

[English](TOOL_CONTRACT.en.md)

Все операции возвращают JSON-совместимые структуры и не открывают сетевые порты.

| Операция | Действие | Запускает EDA |
| --- | --- | --- |
| `server_info()` | Версия, стадия, список операций | Нет |
| `tool_status()` | Обнаружение Verilator без выполнения | Нет |
| `parse_diagnostics(text, limit=200)` | Консервативный парсер до 1 МиБ / 200 записей | Нет |
| `project_validate(manifest_path)` | Проверка manifest в операторском workspace | Нет |
| `lint_run(manifest_path, timeout_seconds=60)` | Запуск ограниченного Verilator `--lint-only` | Да |
| `build_run(manifest_path, timeout_seconds=180)` | Сборка существующего SV-тестбенча через `--binary`; симуляция не выполняется | Да |

`tool_status` возвращает `tool`, `state`, `configured`, `executed=false`. Состояния: `DETECTED_UNVERIFIED`, `NOT_FOUND`, `INVALID_OVERRIDE`. Пути локальной установки не раскрываются.

`parse_diagnostics` возвращает `tool`, `count`, `truncated`, `items` (`severity`, `code`, `file`, `line`, `column`, `message`, `raw`). Отсутствие распознанных строк **не доказывает успех** EDA.

`project_validate` принимает **только относительный путь к JSON manifest**; корни конфигурируются сервером через `VERILATOR_MCP_WORKSPACE_ROOT` и `VERILATOR_MCP_ARTIFACT_ROOT`. Успешный результат: `state=VALID`, `executed=false`, `manifest`, `config_sha256`, `project` с нормализованными `top`, `sources`, `include_dirs`, `defines`, `parameters`, `testbench_top`. При ошибке MCP возвращает error, не фиктивный `VALID`. См. [контракт workspace](WORKSPACE.md).

`project_validate` не компилирует исходники, не открывает RTL для чтения содержимого и не создаёт артефакты. Операция `lint_run` уже использует настоящий исполняемый файл после проверки версии. Возвращает `lint_status`, `verification_verdict=NOT_RUN`, `executed`, `exit_code`, `tool_version`, `duration_ms`, `diagnostics`, `logs_truncated`, хеши входной конфигурации и явные ссылки на ограниченные артефакты. Состояния `NOT_AVAILABLE` и `NOT_RUN` не являются успешным lint. Полный контракт, включая `TIMEOUT`, `INPUT_CHANGED`, `INCOMPLETE` и предупреждения: [LINT.md](LINT.md). `build_run` требует `testbench_top`, проверяет toolchain и компилирует исполняемый файл. Результаты: `build_status`, `build_id`, `binary_sha256`, `binary_artifact`, `tool_versions`, `tool_sha256`, `source_sha256`, `exit_code`. Во всех случаях `simulation_status=NOT_RUN` и `verification_verdict=NOT_RUN`. [Подробности](BUILD.md). Следующий этап — отдельный `simulation_run`.

Сервер не предоставляет `run_command`, произвольный shell, Tcl/DO и свободные флаги Verilator. Verilator не является полной заменой 4-state симулятору.
