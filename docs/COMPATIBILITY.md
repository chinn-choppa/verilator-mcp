# Совместимость

[English](COMPATIBILITY.en.md)

| Уровень | CI-матрица (требует результатов GitHub Actions) | Дополнительная приёмка |
| --- | --- | --- |
| Python | 3.11, 3.13, 3.14 | 3.15: NOT_RUN, проверять отдельно |
| MCP SDK | Зафиксирован `mcp==2.3.0` | Настоящие `tools/list` и `tools/call` в CI |
| Windows | `windows-latest`, stdio | Windows/MSYS2 Verilator: NOT_RUN |
| Linux | `ubuntu-latest`, stdio | Verilator: NOT_RUN |
| Verilator | Публичный системный пакет в Ubuntu CI | Реальные lint/build/simulation в отдельных заданиях; подтверждение после зелёного CI |

Это перечень **запланированных проверок CI**. Результат PASS можно утверждать только после успешного конкретного запуска workflow. Установка, импорт, list и реальное исполнение EDA — разные уровни доказательств.

Verilator использует в основном двухсостояниевую модель и не заменяет полноценную четырёхсостояниевую симуляцию.
