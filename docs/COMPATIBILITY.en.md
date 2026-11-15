# Compatibility

[Русский](COMPATIBILITY.md)

| Layer | CI matrix (requires GitHub Actions evidence) | Additional acceptance |
| --- | --- | --- |
| Python | 3.11, 3.13, 3.14 | 3.15: NOT_RUN pending verification |
| MCP SDK | Pinned to `mcp==2.3.0` | Real `tools/list` and `tools/call` in CI |
| Windows | `windows-latest`, stdio | Verilator on Windows/MSYS2: NOT_RUN |
| Linux | `ubuntu-latest`, stdio | Verilator: NOT_RUN |
| Verilator | Not bundled as a Python dependency | lint/build/simulation: NOT_RUN |

This table lists **planned CI checks**, not completed test evidence. Do not mark a combination PASS until its specific workflow run succeeds. Installation, import, tool listing and EDA execution are distinct levels of confidence.

Verilator is primarily a two-state simulator; it does not replace a full four-state simulation environment.
