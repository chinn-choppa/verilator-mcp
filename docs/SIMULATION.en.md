# Simulation and verification verdict contract (M2)

[Русский](SIMULATION.md) · [Build](BUILD.en.md) · [Security](../SECURITY.en.md)

`simulation_run(build_id, timeout_seconds=30, seed=1)` runs **only** an executable from a previously successful `build_run`. MCP callers cannot select arbitrary executables, paths, shells, free-form arguments, or external scripts.

## Trusted input contract

- `build_id` must match `build-` followed by exactly 32 lowercase hexadecimal characters. Build directories must resolve inside the operator-controlled artifact root.
- The server checks both `request.json` and `result.json`: `build_status=PASS`, `executed=true`, matching source/config provenance, and the exact expected binary name.
- The built executable SHA-256 is recomputed immediately before and after execution. Hash mismatches cause a rejected run or `BINARY_CHANGED`.
- The seed is an integer **1..2147483647**. Seed `0` is deliberately prohibited because it requests a random seed from Verilator. Timeout is **1..180** seconds.
- Only `+verilator+seed+N` and `+VERILATOR_MCP_TOKEN=<unique per-run token>` are passed to the binary. No unrestricted plusargs are exposed.
- Each run creates an isolated `sim-<uuid>` directory containing the request, result, and logs capped at 64 KiB per stream.

## Exact PASS criteria

All of the following must hold: real process exit code `0`, no observed `$fatal`/assertion failure, non-truncated logs, an exact `VERILATOR_MCP_PASS:<this run token>` line, and the Verilator `Verilog $finish` termination message. The testbench must print the token **only after completing its self-checks**.

Example SystemVerilog snippet:

```systemverilog
string token;
initial begin
    if (!$value$plusargs("VERILATOR_MCP_TOKEN=%s", token))
        $fatal(1, "missing token");
    // DUT checks...
    if (test_failed)
        $fatal(1, "test failed");
    $display("VERILATOR_MCP_PASS:%s", token);
    $finish;
end
```

This is an illustrative snippet: `test_failed` must be defined by the actual self-checking testbench.

`run_status`: `PASS`, `RUN_FAIL`, `TIMEOUT`, `FINISHED_UNVERIFIED`, `EXIT_ZERO_UNVERIFIED`, `INCOMPLETE`, `BINARY_CHANGED`, `ARTIFACT_INVALID`, `NOT_RUN`.

`verification_verdict`: `PASS`, `FAIL`, `INCONCLUSIVE`, `NOT_RUN`. The result also provides `finish_observed`, `fatal_observed`, `pass_marker_observed`, `exit_code`, `timed_out`, `duration_ms`, `seed`, `build_id`, `run_id`, `binary_sha256`, tool versions and bounded artifact references.

Process exit code `0` **without the success token** only means `INCONCLUSIVE`. A watchdog timeout is an explicit test `FAIL`, but does not necessarily identify a DUT defect. `$fatal` or nonzero exit yields `FAIL`.

## Trust limits

A success marker is not cryptographic proof of RTL correctness; a poorly written testbench can print it without checking anything. The testbench author is responsible for meaningful checks. The server only reports real observed process evidence, never invented signal values.

Verilator is primarily a two-state simulator and does not replace full four-state verification, particularly for X/Z, resets, CDC, and unknown propagation. Filesystem access, CPU and memory are not OS-sandboxed; use a VM/container for potentially untrusted RTL or executables. Build results and binaries inside the artifact root are trusted to the local operator; records can be forged by a user with the same filesystem privileges.

## Tests

```bash
VERILATOR_MCP_RUN_INTEGRATION=1 uv run python -m unittest discover -s tests -p 'test_simulation_integration.py' -v
```

Ubuntu CI verifies PASS, `$fatal`, INCONCLUSIVE, and watchdog timeouts with public RTL. A separate subprocess unit test checks cancellation. Native Windows/MSYS2 Verilator: `NOT_RUN` pending an independent real test.
