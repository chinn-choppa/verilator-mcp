# verilator-mcp

[Русский](README.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

Community-focused, local-first MCP adapter for **Verilator**. This is an independently maintained open-source project, not an official vendor product.

**Status: experimental bootstrap (0.0.1).** The initial release exposes a minimal MCP server, installation detection and bounded diagnostic parsing. It does **not** execute synthesis, simulation, hardware programming or arbitrary shell commands.

## Setup

Python 3.11+ and `uv` are required:

```bash
git clone https://github.com/chinn-choppa/verilator-mcp.git
cd verilator-mcp
uv sync
uv run verilator-mcp
```

MCP tools: `server_info`, `tool_status`, `parse_diagnostics`. Use a local stdio-capable MCP client and configure it to launch the installed command. A real MCP client test is separate from Python unit tests.

## Development

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

Review [architecture](docs/ARCHITECTURE.md), [roadmap](docs/ROADMAP.md) and [security](SECURITY.md). Russian is used for most engineering documentation; international contributions are welcome, including improvements to English documentation.

Licensed under Apache-2.0. No proprietary EDA executables, licenses or private project data are distributed here.
