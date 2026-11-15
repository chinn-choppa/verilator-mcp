# Проверка проекта

## Быстрые проверки без EDA и внешней сети

```bash
PYTHONPATH=src uv run --locked pytest -q tests
python -m compileall -q src tests
```

PowerShell:

```powershell
$env:PYTHONPATH = "src"
uv run --locked pytest -q tests
python -m compileall -q src tests
Remove-Item Env:PYTHONPATH
```

## При наличии SDK MCP

```bash
uv sync
uv run verilator-mcp
```

Подключить MCP Inspector либо клиент Codex/Claude/OpenCode, проверить реальный `tools/list`, затем вызвать `server_info` и `parse_diagnostics` на синтетических данных. Только после успешного фактического вызова инструмента можно фиксировать `MCP_TOOL_PASS`. Простой старт процесса или наличие пакета означает максимум `INSTALLED`.

## Реальное EDA-тестирование

**Пока не предусмотрено** в bootstrap. После появления команд выполняйте на публичных минимальных RTL-проектах: lint, негативный кейс, сбой лицензии/тайм-аут, успешное завершение по самопроверяющемуся тесту, повреждённый файл, неверный путь и ограничение каталогов. Записывайте версии и SHA используемых исходников.

## Pytest и зависимости

Канонический запуск: `uv sync --locked`, затем `uv run --locked pytest -q tests`.
`pytest==9.2.0` установлен в dev dependency group. Отсутствующий MCP SDK
считается ошибкой теста, а не автоматически пропускаемым случаем.
Нативные fixtures `monkeypatch`, `tmp_path` и параметризация применяются
без `unittest`. Протокол MCP и реальное EDA остаются отдельной приёмкой.
