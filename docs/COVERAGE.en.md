# Observed coverage and assertions (M3, first slice)

[Русский](COVERAGE.md) · [Build](BUILD.en.md) · [Simulation](SIMULATION.en.md)

## Instrumented build

`build_run(manifest_path, timeout_seconds=180, coverage_line=false, assertions=true)` now provides two restricted options:

- `coverage_line=true` adds **only** `--coverage-line` during compilation, not unsupported coverage modes.
- `assertions=true` adds `--assert`, important for Verilator versions before 5.038 where assertions were disabled by default.

Coverage-enabled builds use supported `--cc --exe --build --timing` with a **minimal C++ wrapper generated exclusively by the server**. Unlike Verilator 5.020's built-in `main()`, it explicitly calls `coveragep()->write("coverage.dat")` after model completion. The wrapper's SHA-256 is recorded in build evidence. Builds without coverage retain `--binary`.

No caller-provided C++ or free-form CLI flags. Boolean inputs are strictly validated. The build records `coverage_line_enabled` and `assertions_enabled`.

## Capturing runtime data

When `coverage_line` was enabled, `simulation_run` uses Verilator's default `coverage.dat` filename inside its unique `sim-ID` working directory. This avoids a runtime switch unsupported by older Verilator versions (including 5.020); the MCP caller cannot choose the path. The recorded `coverage_status` is:

| Status | Meaning |
| --- | --- |
| `DISABLED` | Binary not instrumented |
| `NOT_OBSERVED` | No expected artifact was created |
| `EMPTY` | Coverage file exists but contains zero bytes |
| `RECORDED` | Non-empty bounded coverage data was recorded |
| `TOO_LARGE`, `UNREADABLE`, `UNSAFE` | Too large, unreadable or unsafe artifact |

**None of these states means 0% coverage.** No percentage is calculated when coverage is missing or invalid.

`assertion_observation` separately reports `NOT_ENABLED`, `FAILURE_OBSERVED`, or `NO_FAILURE_OBSERVED`. No observed assertion failure does **not** demonstrate all assertions have passed. The self-checking testbench result remains a separate `verification_verdict`.

## Separate report

`coverage_report(run_id, timeout_seconds=20)` reads **only** a `sim-<uuid>` artifact under the approved root. For `RECORDED`, it executes the trusted `verilator_coverage --write-info`, stores `coverage.info`, and conservatively reports LCOV `SF`/`DA` line counts, covered lines and source mapping. Absolute external source paths are redacted from MCP responses.

`report_status=READY` requires actual LCOV `DA` records and a successful conversion. Distinct states include `NOT_ENABLED`, `NOT_OBSERVED`, `EMPTY`, `NOT_AVAILABLE`, `INVALID`, `INCOMPLETE`, `TOOL_FAIL`, `TIMEOUT`. Parsing is bounded to 1 MiB/20,000 points, `coverage.dat` to 16 MiB and process output to 64 KiB per stream.

The summary measures **only observed LCOV line coverage** — not functional, full assertion, toggle or branch coverage. Compilation, simulation and coverage statuses must never be conflated into an invented PASS.

## Verification

```bash
uv run python -m unittest discover -s tests -p 'test_coverage_unit.py' -v
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_coverage_integration.py' -v
```

Ubuntu CI installs real Verilator and `verilator_coverage`, runs a synthetic open SystemVerilog design, verifies `coverage.dat` generation, LCOV conversion and positive observed line counts. Windows/MSYS2 EDA remains `NOT_RUN` until independently tested.

**Limitations:** the executable is not OS-sandboxed; inputs/includes/artifacts can be modified by processes with the same privileges. Coverage percentages are not functional correctness proofs. Multi-case regressions and merged coverage will be a separate PR under #7.
