# Проверка проекта

[English](TESTING.en.md)

## Проверки MCP без установленного Verilator

Все проверки используют официальный SDK, а не подмену сервера.

```bash
uv sync
uv run python -m compileall -q src tests
uv run python -m unittest discover -s tests -v
```

`tests/test_mcp_protocol.py` проверяет два отдельных сценария:

1. Настоящий `initialize`, `tools/list`, `tools/call` через клиент MCP и JSON-RPC в памяти (`mode="legacy"`).
2. Запуск реального stdio-процесса посредством `StdioServerParameters` и повторные `tools/list` / `tools/call`.

Негативные сценарии включают неверные типы и превышение лимита текста. При неуспешном вызове тест не допускает `is_error=false`. Любые посторонние данные в stdout нарушают протокол stdio.

CI выполняет эти тесты на Ubuntu и Windows с Python 3.11, 3.13, 3.14. Успешный протокольный вызов означает только `MCP_TOOL_PASS`, но не `EDA_PASS`.

## Границы приёмки

Проверка отмены **длительной** операции и завершения дерева дочерних EDA-процессов относится к реализации исполнителя (#4–#6); пока `NOT_RUN`. Python 3.15 и реальные запуски Verilator также `NOT_RUN`, пока не получены независимые результаты.

Для ручной проверки можно дополнительно подключить MCP Inspector либо другой стандартный MCP-клиент. Логи содержат только открытые синтетические данные.

## Настоящий Verilator lint

Linux CI устанавливает Verilator из репозитория ОС, выполняет `--version`, затем через реальный MCP-клиент прогоняет публичные `good_top.sv` и `bad_top.sv`. Тест проверяет статусы `PASS` или `PASS_WITH_WARNINGS` и `FAIL`, коды выхода, доказательство вызова и артефакты.

```bash
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_lint_integration.py' -v
```

Без флага тест честно пропускается как `REAL_VERILATOR_NOT_RUN`. На Windows запускаются настоящие процессные тесты тайм-аута/логов, но Verilator/MSYS2 остаётся `NOT_RUN` до самостоятельной приёмки. См. [LINT.md](LINT.md).

## Настоящая симуляция и результаты тестбенча

Отдельная Ubuntu CI job собирает и выполняет четыре публичных тестбенча: успешная самопроверка, `$fatal`, `$finish` без маркера и watchdog. Unit-тест дополнительно проверяет реальную отмену дочернего процесса.

```bash
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_simulation_integration.py' -v
```

Windows/MSYS2 Verilator и Python 3.15 до независимой приёмки — `NOT_RUN`. Контракт: [SIMULATION.md](SIMULATION.md).

## Реальное строковое покрытие (M3)

Позитивный и негативные тесты LCOV дополняются настоящей GitHub Actions проверкой инструментированной сборки `verilator --cc --exe --build --coverage-line` и `verilator_coverage --write-info` на публичном самопроверяющемся RTL.

```bash
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_coverage_integration.py' -v
```

Нулевой размер или отсутствие `coverage.dat` не считаются нулевым покрытием. Подробности: [COVERAGE.md](COVERAGE.md).

## Реальная регрессия с фиксированными seed

В Ubuntu CI к проверке симуляции добавлен настоящий вызов `regression_run` с разными исходами и повтором одинакового seed. В Windows CI выполняются unit, contract и negative проверки без реального EDA.

```bash
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_regression_integration.py' -v
```

См. [REGRESSION.md](REGRESSION.md).
