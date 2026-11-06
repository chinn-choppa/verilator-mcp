# Reproducible RTL regressions (M3)

[Русский](REGRESSION.md) · [Simulation](SIMULATION.en.md) · [Coverage](COVERAGE.en.md)

`regression_run(cases, timeout_seconds=30)` executes **1–8** previously verified builds in a fixed sequential order. Each typed case contains only a `build_id` from a successful `build_run` and an integer `seed` in 1–2147483647. Timeout **per case** is 1–60 seconds. Clients cannot choose executables, directories, commands, free-form flags, or plusargs.

Example (illustrative, non-existent ID):

```json
{
  "cases": [
    {"build_id": "build-0123456789abcdef0123456789abcdef", "seed": 42},
    {"build_id": "build-0123456789abcdef0123456789abcdef", "seed": 42}
  ],
  "timeout_seconds": 30
}
```

**All** builds are validated before any case runs. Each result includes distinct `build_status`, `simulation_status`, `verification_verdict`, `simulation_id`, exit code and execution evidence. A successful build cannot count as a successful test. Aggregate `regression_status`:

| Condition | Status |
| --- | --- |
| Every self-checking testcase passes | `PASS` |
| At least one actual testcase fails | `FAIL` |
| Some cases did not run but none failed | `INCOMPLETE` |
| Some verdict is inconclusive without skips or failures | `INCONCLUSIVE` |
| No actual results | `NOT_RUN` |

If an artifact changes after prevalidation, this and remaining cases become `NOT_RUN`; no false PASS. Client cancellation saves a partial `CANCELLED` result.

The unique `reg-<uuid>` folder holds `request.json`, `result.json`, and an ordered `replay` array with exact `build_id`/`seed` pairs. Repeated pairs produce different `sim-ID` artifacts. A fixed seed controls reproducible random initialization, but **does not prove** identical behavior across different tools and operating systems. Coverage is measured independently by `coverage_report` for a particular simulation, never inferred from PASS counts.

## Acceptance

```bash
uv run python -m unittest discover -s tests -p 'test_regression_unit.py' -v
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_regression_integration.py' -v
```

Ubuntu CI executes actual Verilator regression including repeated seeds on public synthetic testbenches; Windows CI covers contract, types, and negative cases. Native Windows/MSYS2 EDA remains `NOT_RUN`. A PASS does not replace full four-state verification; isolate untrusted RTL at the operating-system level.
