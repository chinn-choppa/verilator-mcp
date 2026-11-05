# Запуск Verilator lint (M1)

[English](LINT.en.md)

Начиная с этого этапа `lint_run(manifest_path, timeout_seconds=60)` запускает **только** реальный `verilator --lint-only`, если Verilator обнаружен и проверен через `--version`. Контракт входного JSON: [WORKSPACE.md](WORKSPACE.md).

## Условия безопасности

1. Локальный оператор задаёт существующие непересекающиеся `VERILATOR_MCP_WORKSPACE_ROOT` и `VERILATOR_MCP_ARTIFACT_ROOT`.
2. Путь к `verilator` берётся из доверенного `PATH` или абсолютного `VERILATOR_MCP_EXECUTABLE`. `.bat/.cmd` на Windows запрещены, чтобы не допустить неявную оболочку.
3. Агент может указать только относительное имя manifest и лимит времени (целое 1..180 секунд). Произвольные CLI-флаги, shell, Tcl/DO и запуск тестбенчей не доступны.
4. Verilator запускается с `--lint-only --sv -Wall -Wno-fatal --top-module TOP --Mdir ARTIFACT/obj`, затем передаются ограниченные `-I`, `-D`, `-G` и проверенные исходники в заданном порядке.
5. Вывод каждого процесса ограничен 64 КиБ на поток; вывод с обрезкой **не** даёт полного PASS. Версия проверяется отдельным процессом; запуск без успешной проверки версии не объявляется выполненным lint.

В случае timeout или отмены сервер пытается завершить группу процессов (POSIX) либо дерево процессов через системный `taskkill /T` (Windows); это не замена cgroups, Job Objects и полноценной ОС-песочницы.

**Ограничения изоляции:** локальный сервер работает с правами пользователя. Verilator разбирает содержимое доверенного RTL, включая директивы `include`; manifest path checks не гарантируют, что злонамеренный RTL не обратится к другим файлам. Не следует подавать недоверенные источники без дополнительной ОС-изоляции. Между чтением manifest, хешированием и запуском остаются гонки TOCTOU.

## Контракт результата

- `lint_status`: `PASS`, `PASS_WITH_WARNINGS`, `FAIL`, `TIMEOUT`, `INCOMPLETE`, `INPUT_CHANGED`, `INCONSISTENT_OUTPUT`, `NOT_AVAILABLE`, `NOT_RUN`.
- `executed`: реально ли был запущен именно lint-процесс.
- `exit_code`, `tool_version`, `duration_ms`, `run_id`, `diagnostics`, `logs_truncated`.
- `config_sha256`, `source_sha256`, `source_hash_scope=explicit_sources_only`; заголовки, подключаемые внутри RTL, **не** входят в полный хеш транзитивных зависимостей.
- `verification_verdict=NOT_RUN` всегда: lint не тестирует функциональное поведение и не заменяет четырехсостояниевую симуляцию.

Результаты сохраняются только под `VERILATOR_MCP_ARTIFACT_ROOT/lint-<uuid>/`: `request.json`, `result.json`, ограниченные `stdout.log` и `stderr.log`. Возвращаемые клиенту абсолютные корни заменяются псевдонимами, но локальные сырые журналы могут включать содержимое исходников; не загружайте их в публичные Issue без проверки.

Состояние `NOT_AVAILABLE` не создаёт выходных каталогов. Ошибки ввода возвращаются как MCP tool error.

## Интеграционная проверка

Требуется доступный `verilator`:

```bash
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_lint_integration.py' -v
```

CI Ubuntu устанавливает Verilator из дистрибутива и проверяет реальный положительный и отрицательный SV-кейс через официальный MCP-клиент. Остальные unit/negative/transport-тесты выполняются также на Windows. Verilator/MSYS2 на Windows остаётся отдельным `NOT_RUN`, пока не появится подтверждённый запуск.
