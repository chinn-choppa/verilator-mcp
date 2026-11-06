# Testing

[Русский](TESTING.md)

## MCP checks without Verilator

The tests use the official MCP SDK, never a fake server.

```bash
uv sync
uv run python -m compileall -q src tests
uv run python -m unittest discover -s tests -v
```

`tests/test_mcp_protocol.py` exercises two distinct paths:

1. Real `initialize`, `tools/list`, and `tools/call` using the MCP client over in-memory JSON-RPC (`mode="legacy"`).
2. A real stdio child process via `StdioServerParameters`, including `tools/list` and `tools/call`.

Negative cases cover invalid types and oversized input. Any rejected tool call must not be reported as `is_error=false`. Stray output on stdout would corrupt the stdio protocol.

CI runs on Ubuntu and Windows with Python 3.11, 3.13, and 3.14. A successful protocol call establishes only `MCP_TOOL_PASS`, not `EDA_PASS`.

## Acceptance boundaries

Cancellation of a **long-running** operation and EDA descendant termination belong to the executor milestones (#4–#6) and remain `NOT_RUN`. Python 3.15 and actual Verilator invocation are also `NOT_RUN` until independently exercised.

MCP Inspector or another standards-compliant client can provide additional manual acceptance. Use only synthetic public inputs and logs.

## Real Verilator lint

Linux CI installs distribution-packaged Verilator, probes `--version`, and invokes real MCP `lint_run` against public passing `good_top.sv` and failing `bad_top.sv`. It checks distinct `PASS`/`PASS_WITH_WARNINGS` and `FAIL` states, exit codes, real execution evidence, and artifacts.

```bash
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_lint_integration.py' -v
```

Without the flag, the test explicitly skips as `REAL_VERILATOR_NOT_RUN`. Windows runs actual process timeout/log bounds tests, but Verilator/MSYS2 remains `NOT_RUN` pending independent acceptance. See [LINT.en.md](LINT.en.md).

## Real simulation verdicts

A dedicated Ubuntu CI job builds and executes four public testbenches: passing self-check, `$fatal`, `$finish` without evidence, and watchdog. The unit suite also tests cancellation of a real child process.

```bash
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_simulation_integration.py' -v
```

Windows/MSYS2 Verilator and Python 3.15 remain `NOT_RUN` pending independent acceptance. See [SIMULATION.en.md](SIMULATION.en.md).

## Real line coverage (M3)

Positive/negative LCOV parsing tests are joined by a real GitHub Actions run of instrumented `verilator --cc --exe --build --coverage-line` and `verilator_coverage --write-info` against public self-checking RTL.

```bash
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_coverage_integration.py' -v
```

Missing or empty `coverage.dat` is never interpreted as 0% coverage. See [COVERAGE.en.md](COVERAGE.en.md).

## Real seeded regression

Ubuntu CI additionally calls real `regression_run` with mixed verdicts and an identical-seed replay; Windows CI covers unit, contract and negative cases without claiming EDA execution.

```bash
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_regression_integration.py' -v
```

See [REGRESSION.en.md](REGRESSION.en.md).
