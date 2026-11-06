# Сборка SystemVerilog-тестбенча (M2)

[English](BUILD.en.md) · [RTL workspace](WORKSPACE.md) · [lint](LINT.md)

`build_run(manifest_path, timeout_seconds=180)` собирает **уже существующий** SystemVerilog-тестбенч в исполняемый бинарник Verilator. Он не создаёт тестбенчи и не запускает полученный бинарник.

## Входные данные

Оператор локального MCP-процесса устанавливает `VERILATOR_MCP_WORKSPACE_ROOT` и `VERILATOR_MCP_ARTIFACT_ROOT`. Каталоги существуют заранее и не пересекаются. Дополнительно необходимы Verilator, C++ компилятор (`c++`, `g++` или `clang++`) и GNU Make в доверенном `PATH`.

Пример manifest (все пути относительны от workspace):

```json
{
  "schema_version": 1,
  "top": "counter",
  "testbench_top": "tb_counter",
  "sources": ["rtl/counter.sv", "tb/tb_counter.sv"]
}
```

Пример в [tests/fixtures/build](../tests/fixtures/build/good.json) использует искусственные исходники Apache-2.0. Вложенные JSON filelists разрешены при выполнении [ограничений workspace](WORKSPACE.md).

Команда собирается исключительно сервером: `verilator --binary --timing --sv -Wall -Wno-fatal --top-module TB --Mdir ARTIFACT/obj` и разрешённые include/defines/parameters/sources. При включении `coverage_line=true` вместо `--binary` используется безопасная сгенерированная обёртка с `--cc --exe --build --coverage-line` и отдельным SHA-256 её исходника; подробнее — [COVERAGE.md](COVERAGE.md). Сборка ограничена 10–600 секундами, по умолчанию 180 секунд. У клиента нет доступа к произвольным ключам компилятора, `-f`, скриптам, shell, make-целям или каталогам вывода.

## Доказательства результата

Каждый запуск создаёт новый `build-<uuid>` под корнем артефактов. Записываются ограниченные журналы, исходная конфигурация, версии и SHA-256 исполняемых инструментов (Verilator, Make, C++), исходников и созданного бинарника. Результат возвращает `build_id`, `build_status`, `executed`, `exit_code`, `duration_ms`, `binary_sha256`, `binary_artifact`, `tool_versions`, `tool_sha256`, `config_sha256`, `source_sha256`, `artifacts`.

`build_status`: `PASS`, `BUILD_FAIL`, `TIMEOUT`, `INPUT_CHANGED`, `INCOMPLETE`, `ARTIFACT_MISSING_OR_UNSAFE`, `TOOLCHAIN_NOT_AVAILABLE`, `NOT_AVAILABLE`, `NOT_RUN`.

Даже при `PASS` обязательно `simulation_status=NOT_RUN` и `verification_verdict=NOT_RUN`. Синтаксические ошибки показывают `BUILD_FAIL`, отсутствие компилятора — `TOOLCHAIN_NOT_AVAILABLE`.

`source_hash_scope=explicit_sources_only` указывает ограничение: транзитивные `include` **пока не хешируются**. Хеш бинарника фиксирует его содержимое, но не является подписью доверенного происхождения.

## Безопасность и переносимость

Сборка Verilator вызывает C++ компилятор и Make. Процесс работает с полномочиями пользователя MCP-сервера, без песочницы ОС. Злонамеренный HDL, вложенные `include`, переменные окружения toolchain и TOCTOU могут нарушить границы manifest. Не собирайте недоверенные RTL без контейнера/VM и политики прав доступа. `build_run` не предназначен для исполнения сторонних команд. При выходе за лимит времени предпринимается best-effort завершение дерева дочерних процессов.

На Windows/MSYS2 реальная приёмка отдельно обозначена `NOT_RUN`; пути в JSON всегда используют `/`, а найденные инструменты должны быть настоящими `.exe`, не `.bat`/`.cmd`. Зависимость от `make` и компилятора проверяется отдельно.

## Проверка

```bash
uv run python -m unittest discover -s tests -p 'test_build_unit.py' -v
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_build_integration.py' -v
```

Без `VERILATOR_MCP_RUN_INTEGRATION=1` второй тест честно пропускается. Ubuntu CI устанавливает Verilator, Make и g++ и проверяет реальный `--binary` через MCP на корректном и ошибочном тестбенчах. Запуск бинарника относится исключительно к следующему этапу #6.
