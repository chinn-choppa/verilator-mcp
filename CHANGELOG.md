# История изменений / Changelog

## [Unreleased]

### Added / Добавлено
- Verified binary execution and reproducible seeds; explicit PASS/FAIL/INCONCLUSIVE/NOT_RUN with `$finish`, `$fatal`, and watchdog evidence (#6).
- Безопасный запуск только результатов сборки, фиксация seed, контроль SHA-256 и отдельные проверки отмены.

- Safe `build_run`: real `--binary` compilation of existing self-checking SV testbenches with toolchain provenance and output hashing (#5).
- Сборка реального тестбенча без запуска: отдельные артефакты, тайм-ауты, проверки C++/make, негативные тесты на синтаксические ошибки.

- Real bounded Verilator lint with version probe, exit status, source hashes, diagnostics and local artifacts (#4).
- Реальный lint-only, управление дочерними процессами, ограничение журналов и проверка RTL на открытых фикстурах.
- Explicitly no simulation verdict and no free shell or native filelist arguments.
- Versioned read-only RTL workspace manifest, bounded nested JSON filelists and canonical-path validation (#3).
- Версионированное описание проекта с проверкой путей, глубины вложенности, ограничением входов и защите от выхода за workspace.
- Real MCP client tests for in-memory JSON-RPC and stdio (#2).
- Настоящие протокольные проверки на Python 3.11/3.13/3.14 и Windows/Linux; двуязычная документация.

### Limits / Ограничения
- Neither project validation nor a completed MCP request proves RTL correctness or simulation success.
- Запуск Verilator, отмена длительных команд и приёмка Python 3.15 пока NOT_RUN.
