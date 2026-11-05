# MCP tool contract v1

[Русский](TOOL_CONTRACT.md)

All operations return JSON-compatible structures without exposing network listeners.

| Operation | Behavior | Executes EDA |
| --- | --- | --- |
| `server_info()` | Version, stage, operation names | No |
| `tool_status()` | Detect Verilator without executing it | No |
| `parse_diagnostics(text, limit=200)` | Conservative log parser, <=1 MiB / 200 items | No |
| `project_validate(manifest_path)` | Validate JSON manifest under operator-configured workspace | No |
| `lint_run(manifest_path, timeout_seconds=60)` | Run bounded real Verilator `--lint-only` | Yes |

`tool_status` returns `tool`, `state`, `configured`, `executed=false`. States: `DETECTED_UNVERIFIED`, `NOT_FOUND`, `INVALID_OVERRIDE`. Local executable paths are not exposed.

`parse_diagnostics` returns `tool`, `count`, `truncated`, `items` (`severity`, `code`, `file`, `line`, `column`, `message`, `raw`). Zero recognized messages **does not imply EDA success**.

`project_validate` takes **only a workspace-relative JSON manifest path**. Roots are operator-controlled through `VERILATOR_MCP_WORKSPACE_ROOT` and `VERILATOR_MCP_ARTIFACT_ROOT`. A successful response contains `state=VALID`, `executed=false`, `manifest`, `config_sha256`, and normalized `project` fields (`top`, `sources`, `include_dirs`, `defines`, `parameters`, `testbench_top`). Rejection becomes an MCP tool error, never an invented `VALID`. See [workspace contract](WORKSPACE.en.md).

Validation does not compile RTL, read RTL source contents, or create artifacts. `lint_run` invokes the actual executable after a version probe. It returns `lint_status`, `verification_verdict=NOT_RUN`, `executed`, `exit_code`, `tool_version`, `duration_ms`, `diagnostics`, `logs_truncated`, hashes and bounded artifact references. `NOT_AVAILABLE` and `NOT_RUN` do not imply lint success. For states including `TIMEOUT`, `INPUT_CHANGED`, `INCOMPLETE` and warnings, see [LINT.en.md](LINT.en.md). Future milestones introduce separate `build_run` and `simulation_run` operations.

There is no generic `run_command`, shell, Tcl/DO runner, or free-form Verilator flags. Verilator is not a full four-state simulator replacement.
