# verilator-mcp

[Русский](README.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

A portable, local-first Verilator MCP server for RTL engineering with any compatible AI agent. Independently maintained for the FPGA/ASIC community.

**Status: experimental, real lint-only (0.0.1).** Verilator lint runs only against an operator-approved workspace. Building, simulating and functional verification are not implemented yet.

## Quick start

Requires Python 3.11+ and `uv`:

```bash
git clone https://github.com/chinn-choppa/verilator-mcp.git
cd verilator-mcp
uv sync
uv run verilator-mcp
```

Example for clients supporting the `mcpServers` configuration key (replace with trusted local paths):

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

Actual MCP client configuration formats vary. The operator sets existing, non-overlapping workspace and artifact directories.

## MCP tools

| Tool | Behavior |
| --- | --- |
| `server_info` | Server stage and available operations |
| `tool_status` | Read-only Verilator discovery |
| `parse_diagnostics` | Bounded structured parsing of diagnostic text |
| `project_validate` | Validate a local JSON manifest and paths without EDA execution |
| `lint_run` | Run bounded real `verilator --lint-only`; never claim simulation PASS |

Read the [lint contract](docs/LINT.en.md), [workspace contract](docs/WORKSPACE.en.md), [tool contract](docs/TOOL_CONTRACT.en.md), [testing](docs/TESTING.en.md), [compatibility](docs/COMPATIBILITY.en.md), [architecture](docs/ARCHITECTURE.md), and [roadmap](docs/ROADMAP.md).

```bash
uv run python -m unittest discover -s tests -v
```

Verilator primarily uses two-state semantics and does not replace a full four-state simulator. Successful lint or testbench execution alone does not prove RTL functionality.

Apache-2.0 licensed. Not affiliated with the official Verilator maintainers.
