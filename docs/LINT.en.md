# Verilator lint execution (M1)

[Русский](LINT.md)

`lint_run(manifest_path, timeout_seconds=60)` invokes **real** `verilator --lint-only` only after finding a permitted executable and probing `--version`. Input JSON contract: [WORKSPACE.en.md](WORKSPACE.en.md).

## Safety preconditions

1. The local operator configures existing, non-overlapping `VERILATOR_MCP_WORKSPACE_ROOT` and `VERILATOR_MCP_ARTIFACT_ROOT`.
2. Verilator is resolved from the trusted `PATH` or an absolute `VERILATOR_MCP_EXECUTABLE`. On Windows, `.bat/.cmd` wrappers are refused to avoid implicit shell execution.
3. The agent supplies only a workspace-relative manifest path and a bounded integer timeout (1..180 seconds). Arbitrary flags, shell, Tcl/DO, and testbench runs are not exposed.
4. The fixed command is `--lint-only --sv -Wall -Wno-fatal --top-module TOP --Mdir ARTIFACT/obj` followed by validated `-I`, `-D`, `-G` options and source files in order.
5. Each process stream is capped at 64 KiB. Truncated diagnostics cannot be reported as a full PASS. A separate version probe is required before claiming actual lint execution.

On timeout/cancellation, the runner attempts to kill the POSIX process group or the Windows process tree via the built-in `taskkill /T`. This is **not** a replacement for cgroups, Windows Job Objects, or OS-level isolation.

**Isolation limits:** the local process runs with the user's privileges. Verilator parses trusted RTL, including `include` directives. Manifest path validation cannot guarantee that hostile RTL never reads files beyond the workspace. Use additional OS sandboxing for untrusted designs. Manifest validation, hashing and lint execution also involve residual TOCTOU races.

## Result contract

- `lint_status`: `PASS`, `PASS_WITH_WARNINGS`, `FAIL`, `TIMEOUT`, `INCOMPLETE`, `INPUT_CHANGED`, `INCONSISTENT_OUTPUT`, `NOT_AVAILABLE`, `NOT_RUN`.
- `executed`: whether the lint command itself actually ran.
- `exit_code`, `tool_version`, `duration_ms`, `run_id`, `diagnostics`, `logs_truncated`.
- `config_sha256`, `source_sha256`, `source_hash_scope=explicit_sources_only`: transitively included HDL headers are **not** fully hashed.
- `verification_verdict=NOT_RUN` in all cases: lint is not functional verification and is not a four-state simulation replacement.

Results are stored exclusively under `VERILATOR_MCP_ARTIFACT_ROOT/lint-<uuid>/`: `request.json`, `result.json`, bounded `stdout.log`, `stderr.log`. Local absolute roots are replaced with aliases in MCP responses, but raw local log files may contain RTL details; do not post them publicly without review.

`NOT_AVAILABLE` creates no artifact directory. Invalid inputs produce MCP tool errors.

## Integration check

Requires an installed `verilator`:

```bash
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_lint_integration.py' -v
```

Ubuntu CI installs distribution-packaged Verilator and exercises passing/failing synthetic SystemVerilog through the official MCP client. Unit, negative and transport tests also run on Windows. Native Verilator/MSYS2 execution on Windows remains `NOT_RUN` pending a verified run.
