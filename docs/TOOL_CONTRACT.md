# Контракт MCP-инструментов v1

[English](TOOL_CONTRACT.en.md)

Все операции возвращают JSON-совместимые структуры и не открывают сетевые порты.

| Операция | Действие | Запускает EDA |
| --- | --- | --- |
| `server_info()` | Версия, стадия, список операций | Нет |
| `tool_status()` | Обнаружение Verilator без выполнения | Нет |
| `parse_diagnostics(text, limit=200)` | Консервативный парсер до 1 МиБ / 200 записей | Нет |
| `project_validate(manifest_path)` | Проверка manifest в операторском workspace | Нет |

`tool_status` возвращает `tool`, `state`, `configured`, `executed=false`. Состояния: `DETECTED_UNVERIFIED`, `NOT_FOUND`, `INVALID_OVERRIDE`. Пути локальной установки не раскрываются.

`parse_diagnostics` возвращает `tool`, `count`, `truncated`, `items` (`severity`, `code`, `file`, `line`, `column`, `message`, `raw`). Отсутствие распознанных строк **не доказывает успех** EDA.

`project_validate` принимает **только относительный путь к JSON manifest**; корни конфигурируются сервером через `VERILATOR_MCP_WORKSPACE_ROOT` и `VERILATOR_MCP_ARTIFACT_ROOT`. Успешный результат: `state=VALID`, `executed=false`, `manifest`, `config_sha256`, `project` с нормализованными `top`, `sources`, `include_dirs`, `defines`, `parameters`, `testbench_top`. При ошибке MCP возвращает error, не фиктивный `VALID`. См. [контракт workspace](WORKSPACE.md).

`project_validate` не компилирует исходники, не открывает RTL для чтения содержимого и не создаёт артефакты. Следующие этапы добавят отдельные `lint_run`, `build_run` и `simulation_run` с реальными кодами завершения и доказательствами исполнения.

Сервер не предоставляет `run_command`, произвольный shell, Tcl/DO и свободные флаги Verilator. Verilator не является полной заменой 4-state симулятору.
