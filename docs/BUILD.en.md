# SystemVerilog testbench build (M2)

[Русский](BUILD.md) · [RTL workspace](WORKSPACE.en.md) · [lint](LINT.en.md)

`build_run(manifest_path, timeout_seconds=180)` compiles an **existing** SystemVerilog testbench into a Verilator executable. It does not generate a testbench or execute the produced binary.

## Input contract

The local MCP operator configures existing, non-overlapping `VERILATOR_MCP_WORKSPACE_ROOT` and `VERILATOR_MCP_ARTIFACT_ROOT`. Verilator, a C++ compiler (`c++`, `g++`, or `clang++`) and GNU Make must be installed in the trusted `PATH`.

Example manifest (all source paths are workspace-relative):

```json
{
  "schema_version": 1,
  "top": "counter",
  "testbench_top": "tb_counter",
  "sources": ["rtl/counter.sv", "tb/tb_counter.sv"]
}
```

The [tests/fixtures/build](../tests/fixtures/build/good.json) example uses original synthetic Apache-2.0 RTL. Nested JSON filelists are supported under the [workspace restrictions](WORKSPACE.en.md).

The server constructs the entire command: `verilator --binary --timing --sv -Wall -Wno-fatal --top-module TB --Mdir ARTIFACT/obj`, followed by validated includes/defines/parameters/source files. The timeout is 10–600 seconds (default 180). MCP clients cannot submit arbitrary compiler switches, native `-f` filelists, scripts, shells, make targets, or output paths.

## Evidence and results

Each invocation creates a new `build-<uuid>` directory under the artifact root, containing bounded logs, normalized configuration, versions and SHA-256 hashes for Verilator, Make, C++ compiler, explicitly listed RTL files, and the generated executable.

The returned data includes `build_id`, `build_status`, `executed`, `exit_code`, `duration_ms`, `binary_sha256`, `binary_artifact`, `tool_versions`, `tool_sha256`, `config_sha256`, `source_sha256`, and `artifacts`.

`build_status` is one of `PASS`, `BUILD_FAIL`, `TIMEOUT`, `INPUT_CHANGED`, `INCOMPLETE`, `ARTIFACT_MISSING_OR_UNSAFE`, `TOOLCHAIN_NOT_AVAILABLE`, `NOT_AVAILABLE`, or `NOT_RUN`.

Even when compilation succeeds, `simulation_status=NOT_RUN` and `verification_verdict=NOT_RUN`. HDL compilation failures yield `BUILD_FAIL` and missing compilers `TOOLCHAIN_NOT_AVAILABLE`.

`source_hash_scope=explicit_sources_only` is an important caveat: transitive `include` files are **not yet hashed**. An executable's digest proves its bytes at the moment of hashing, not its trusted origin.

## Security and portability

Verilator build invokes C++ and Make using the MCP server process's privileges. It is **not** an OS sandbox. Hostile HDL, transitive includes, inherited toolchain environment and TOCTOU races may escape manifest boundaries. Build untrusted RTL only in approved container/VM isolation. This operation does not expose generic command execution. The runner attempts best-effort child-tree termination on timeout/cancellation.

Native Windows/MSYS2 Verilator acceptance is separately `NOT_RUN`. Manifest paths always use `/`; executable toolchain candidates must be genuine `.exe` files, not `.bat`/`.cmd` wrappers. Make and the C++ compiler are checked separately.

## Tests

```bash
uv run python -m unittest discover -s tests -p 'test_build_unit.py' -v
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_build_integration.py' -v
```

Without `VERILATOR_MCP_RUN_INTEGRATION=1`, the integration test is explicitly skipped. Ubuntu CI installs Verilator, Make and g++ and tests real `--binary` compilation of passing/failing testbenches through MCP. Executing the built binary belongs strictly to the next milestone #6.
