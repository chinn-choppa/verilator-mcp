# RTL workspace contract v1

[Русский](WORKSPACE.md)

## Trust boundary

The operator of the local MCP process configures **two existing absolute directories**:

- `VERILATOR_MCP_WORKSPACE_ROOT`: approved RTL project input root;
- `VERILATOR_MCP_ARTIFACT_ROOT`: separate root for future operation artifacts.

The roots cannot overlap, nest, or be identical. MCP arguments may **not** select these roots, create directories, pass Verilator flags, or change the process configuration. At this stage `project_validate` only inspects the project description; it performs no writes or process execution.

## Versioned manifest

The manifest is a JSON file within the workspace. All JSON paths are **normalized workspace-relative forward-slash paths**, including on Windows. No `../`, `C:/...`, UNC paths, globs or environment expansion. Root shape:

```json
{
  "schema_version": 1,
  "top": "top",
  "sources": ["rtl/top.sv"],
  "filelists": ["lists/common.json"],
  "include_dirs": ["rtl/include"],
  "defines": {"FEATURE": "1"},
  "parameters": {"WIDTH": 8},
  "testbench_top": "tb_top"
}
```

`filelists`, `include_dirs`, `defines`, `parameters`, and `testbench_top` are optional. `sources` may be empty in the root if a nested filelist contributes sources; at least one source is required after expansion. `top` identifies the RTL module, while `testbench_top` is reserved for the future build milestone.

A nested filelist is **also JSON**, not a native Verilator `-f` file:

```json
{
  "schema_version": 1,
  "sources": ["rtl/common.v"],
  "include_dirs": ["rtl/include"],
  "filelists": []
}
```

Nested filelists are expanded **before** local `sources`, in declared order. Repeated references, cycles and duplicate sources are rejected; duplicate include directories retain their first occurrence. `defines` and `parameters` are root-only, sorted by name, and cannot be introduced by nested lists.

Parameter values are integers 0..2147483647. Define values are ASCII letter/digit/underscore strings (empty is allowed). Top and define/parameter names use a deliberately restricted SystemVerilog identifier subset; escaped HDL identifiers are not supported.

## Limits and guarantees

- Each JSON file <=64 KiB; nesting <=8; up to 64 manifest/filelist JSON files, 512 `.v`/`.sv` sources, 64 include directories, and 128 defines/parameters each.
- No RTL source content is read at this stage; only file existence and paths are validated. Contents are handled in later EDA operations.
- Symlinks are canonicalized with `Path.resolve(strict=True)` and rejected if they resolve outside the workspace. Missing files and unexpected extensions fail.
- Unknown JSON fields, repeated JSON keys, Windows device names, free CLI flags and commands are rejected.
- `config_sha256` hashes the **normalized configuration**, not the RTL bytes. Real lint must separately record the contents of its actual inputs.

**Residual risk:** path validation and later execution are not atomic against concurrent source/symlink changes (TOCTOU). The EDA execution milestone must define input revalidation/snapshot policy. A local MCP server is not an OS sandbox; potentially hostile RTL should be processed under OS-level isolation.

## Testing

```bash
uv run python -m unittest tests.test_workspace -v
```

`project_validate("project.json")` returns `state=VALID` and `executed=false` after validating the configuration. This does **not** establish a lint, build, or simulation PASS. A rejected MCP call is an error, not a successful verification.
