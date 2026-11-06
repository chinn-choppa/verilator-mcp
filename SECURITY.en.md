# Security policy

[Русский](SECURITY.md)

## Reporting vulnerabilities

Use GitHub Private Vulnerability Reporting if enabled. Do not publish working exploits, credentials, license files, proprietary RTL, or confidential logs in public issues.

## Threat model and actual limits

MCP clients may provide untrusted parameters. `project_validate` inspects project configuration only; `lint_run` launches local Verilator with the MCP process owner's privileges after verifying `--version`. Agents cannot select arbitrary executables, shell, Tcl/DO commands, or unrestricted CLI flags.

- Operator-selected workspace and artifact roots must be absolute and disjoint.
- Input paths are canonicalized, symlink escapes are rejected, and unknown JSON fields/CLI flags fail closed.
- `--lint-only` uses fixed argv and never `shell=True`; Windows `.bat/.cmd` wrappers are refused.
- Process timeouts, bounded logs, and best-effort child process-tree termination are implemented.
- No network listener, unattended download, or telemetry is used.

**Important:** this server is not an OS sandbox. Verilator interprets RTL content, including `include` directives and possible references outside the workspace. Validation and execution have TOCTOU races. Never run untrusted or confidential designs without approved OS isolation and organizational authorization. Verilator's own memory use is not yet capped; apply resource limits through your container or operating system.

Local raw logs can include RTL details. MCP clients and models may transmit tool results even with local stdio. Only a trusted local operator may configure the executable path.

Lint success is not a functional verification verdict, and Verilator is not equivalent to a complete four-state simulator.

## Simulation execution

`simulation_run` executes only a previously successful build artifact, verifies its SHA-256, and restricts `build_id`. The executable can still access files/network with the MCP process privileges. Use OS isolation for untrusted RTL. A `PASS` marker only indicates observed self-checking testbench completion, not general DUT correctness.

## Supported versions

The project is experimental; a stable support policy is not yet established. Vulnerability reports are handled individually.
