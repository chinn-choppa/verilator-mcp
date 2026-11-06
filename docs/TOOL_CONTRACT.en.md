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
| `build_run(manifest_path, timeout_seconds=180)` | Compile existing SV testbench with `--binary`, do not simulate | Yes |
| `simulation_run(build_id, timeout_seconds=30, seed=1)` | Execute a verified build artifact with explicit testbench evidence | Yes |

`tool_status` returns `tool`, `state`, `configured`, `executed=false`. States: `DETECTED_UNVERIFIED`, `NOT_FOUND`, `INVALID_OVERRIDE`. Local executable paths are not exposed.

`parse_diagnostics` returns `tool`, `count`, `truncated`, `items` (`severity`, `code`, `file`, `line`, `column`, `message`, `raw`). Zero recognized messages **does not imply EDA success**.

`project_validate` takes **only a workspace-relative JSON manifest path**. Roots are operator-controlled through `VERILATOR_MCP_WORKSPACE_ROOT` and `VERILATOR_MCP_ARTIFACT_ROOT`. A successful response contains `state=VALID`, `executed=false`, `manifest`, `config_sha256`, and normalized `project` fields (`top`, `sources`, `include_dirs`, `defines`, `parameters`, `testbench_top`). Rejection becomes an MCP tool error, never an invented `VALID`. See [workspace contract](WORKSPACE.en.md).

Validation does not compile RTL, read RTL source contents, or create artifacts. `lint_run` invokes the actual executable after a version probe. It returns `lint_status`, `verification_verdict=NOT_RUN`, `executed`, `exit_code`, `tool_version`, `duration_ms`, `diagnostics`, `logs_truncated`, hashes and bounded artifact references. `NOT_AVAILABLE` and `NOT_RUN` do not imply lint success. For states including `TIMEOUT`, `INPUT_CHANGED`, `INCOMPLETE` and warnings, see [LINT.en.md](LINT.en.md). `build_run` requires `testbench_top`, checks the C++ toolchain and creates an executable. It returns `build_status`, `build_id`, `binary_sha256`, `binary_artifact`, `tool_versions`, `tool_sha256`, `source_sha256`, and `exit_code`. Both `simulation_status` and `verification_verdict` remain `NOT_RUN`. See [build contract](BUILD.en.md). `simulation_run` revalidates the built executable SHA-256 and returns `PASS`, `FAIL`, `INCONCLUSIVE` or `NOT_RUN` based on actual exit code, `$finish`, `$fatal`, and the self-checking token. Exit code 0 alone is not PASS. See [simulation contract](SIMULATION.en.md).

There is no generic `run_command`, shell, Tcl/DO runner, or free-form Verilator flags. Verilator is not a full four-state simulator replacement.
