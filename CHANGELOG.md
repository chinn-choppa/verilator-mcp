# История изменений / Changelog

## [Unreleased]

### Added / Добавлено
- Тесты реальных MCP `initialize`, `tools/list`, `tools/call` через JSON-RPC в памяти и локальный stdio.
- Real MCP client protocol tests using the official v2 SDK, in-memory and stdio.
- CI matrix with `uv` on Linux/Windows and Python 3.11/3.13/3.14.
- Двуязычные руководства по тестированию и совместимости / bilingual testing and compatibility guides.

### Limits / Ограничения
- No EDA execution is introduced in this change; cancellation, Verilator and Python 3.15 acceptance remain NOT_RUN.
- Запуск Verilator, отмена длительных команд и приёмка Python 3.15 требуют самостоятельной проверки.
