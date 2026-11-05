# История изменений / Changelog

## [Unreleased]

### Added / Добавлено
- Versioned read-only RTL workspace manifest, bounded nested JSON filelists and canonical-path validation (#3).
- Версионированное описание проекта с проверкой путей, глубины вложенности, ограничением входов и защите от выхода за workspace.
- Real MCP client tests for in-memory JSON-RPC and stdio (#2).
- Настоящие протокольные проверки на Python 3.11/3.13/3.14 и Windows/Linux; двуязычная документация.

### Limits / Ограничения
- Neither project validation nor a completed MCP request proves RTL correctness or simulation success.
- Запуск Verilator, отмена длительных команд и приёмка Python 3.15 пока NOT_RUN.
