# verilator-mcp

[English](README.en.md) · [Участие](CONTRIBUTING.md) · [Безопасность](SECURITY.md)

Переносимый локальный MCP-сервер для анализа и верификации RTL через Verilator. Независимый проект для FPGA/ASIC-инженеров и любых совместимых AI-агентов.

**Статус: экспериментальный, lint и сборка (0.0.1).** На разрешённом проекте доступны проверка lint и компиляция существующего SystemVerilog-тестбенча. Симуляция и функциональная верификация пока не реализованы.

## Быстрый старт

Нужны Python 3.11+ и `uv`:

```bash
git clone https://github.com/chinn-choppa/verilator-mcp.git
cd verilator-mcp
uv sync
uv run verilator-mcp
```

Пример для клиентов с ключом `mcpServers` (пути замените на доверенные локальные):

```json
{
  "mcpServers": {
    "verilator-mcp": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/verilator-mcp", "run", "verilator-mcp"],
      "env": {
        "VERILATOR_MCP_WORKSPACE_ROOT": "/absolute/path/to/workspace",
        "VERILATOR_MCP_ARTIFACT_ROOT": "/absolute/path/to/separate-artifacts"
      }
    }
  }
}
```

У разных MCP-клиентов свои схемы конфигурации. Корни workspace и артефактов указывает владелец процесса; они должны существовать и не пересекаться.

## MCP-инструменты

| Инструмент | Результат |
| --- | --- |
| `server_info` | Состояние и возможности сервера |
| `tool_status` | Безвредное обнаружение установленного Verilator |
| `parse_diagnostics` | Ограниченный структурированный разбор логов |
| `project_validate` | Проверка локального JSON manifest и допустимых путей без выполнения EDA |
| `lint_run` | Реальный ограниченный `verilator --lint-only`; никаких результатов симуляции |
| `build_run` | Компиляция существующего SystemVerilog-тестбенча в изолированный каталог, без запуска |

Подробности: [сборка](docs/BUILD.md), [lint](docs/LINT.md), [workspace](docs/WORKSPACE.md), [контракт инструментов](docs/TOOL_CONTRACT.md), [проверки](docs/TESTING.md), [совместимость](docs/COMPATIBILITY.md), [архитектура](docs/ARCHITECTURE.md), [план](docs/ROADMAP.md).

```bash
uv run python -m unittest discover -s tests -v
```

Verilator в основном использует двухсостояниевую семантику и не заменяет полноценный четырёхсостояниевый симулятор. Ни успешный lint, ни запуск тестбенча сами по себе не доказывают функциональную корректность дизайна.

Лицензия Apache-2.0. Проект не является официальным продуктом разработчиков Verilator.
