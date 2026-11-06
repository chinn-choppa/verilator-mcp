"""Build selection, negative cases, missing toolchain and provenance."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verilator_mcp.build import build_run_project, _build_arguments
from verilator_mcp.execution import ProcessResult
from verilator_mcp.workspace import ManifestError, validate_manifest


def completed(code: int, out: str = "", err: str = "", *, timeout: bool = False):
    return ProcessResult(
        exit_code=code, stdout=out, stderr=err, timed_out=timeout,
        duration_ms=8, stdout_truncated=False, stderr_truncated=False,
    )


class BuildUnitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.workspace = base / "workspace"
        self.artifacts = base / "artifacts"
        self.workspace.mkdir()
        self.artifacts.mkdir()
        (self.workspace / "top.sv").write_text(
            "module tb_top; initial $finish; endmodule\n", encoding="utf-8"
        )
        self.manifest = {
            "schema_version": 1, "top": "tb_top", "testbench_top": "tb_top",
            "sources": ["top.sv"],
        }
        self.write_manifest(self.manifest)
        env = patch.dict(os.environ, {
            "VERILATOR_MCP_WORKSPACE_ROOT": str(self.workspace),
            "VERILATOR_MCP_ARTIFACT_ROOT": str(self.artifacts),
        })
        env.start()
        self.addCleanup(env.stop)

    def write_manifest(self, data):
        (self.workspace / "project.json").write_text(json.dumps(data), encoding="utf-8")

    def test_fixed_arguments(self):
        project = validate_manifest("project.json")
        args = _build_arguments(project, self.artifacts / "build-123")
        self.assertEqual(args[0:2], ["--binary", "--timing"])
        self.assertIn("--top-module", args)
        self.assertEqual(args[args.index("--top-module") + 1], "tb_top")
        self.assertNotIn("--lint-only", args)
        self.assertNotIn("--exe", args)
        self.assertNotIn("-f", args)

    async def test_missing_verilator_does_not_create_artifacts(self):
        with patch("verilator_mcp.build.find_verilator", return_value=None):
            result = await build_run_project("project.json")
        self.assertEqual(result["build_status"], "NOT_AVAILABLE")
        self.assertFalse(result["executed"])
        self.assertEqual(list(self.artifacts.iterdir()), [])

    async def test_missing_compiler_is_not_build_failure(self):
        with (
            patch("verilator_mcp.build.find_verilator", return_value=Path("/usr/bin/verilator")),
            patch("verilator_mcp.build._trusted_toolchain", return_value=None),
        ):
            result = await build_run_project("project.json")
        self.assertEqual(result["build_status"], "TOOLCHAIN_NOT_AVAILABLE")
        self.assertFalse(result["executed"])
        self.assertEqual(list(self.artifacts.iterdir()), [])

    async def test_rejects_missing_testbench_and_invalid_timeouts(self):
        self.write_manifest({k: v for k, v in self.manifest.items() if k != "testbench_top"})
        with self.assertRaises(ManifestError):
            await build_run_project("project.json")
        self.write_manifest(self.manifest)
        for value in (0, 601, "60", True):
            with self.subTest(value=value):
                with self.assertRaises(ManifestError):
                    await build_run_project("project.json", value)

    async def test_success_and_missing_binary_are_distinguished(self):
        runs = []
        async def fake_run(argv, folder, timeout_seconds, **kwargs):
            runs.append(list(argv))
            if "--version" in argv:
                return completed(0, "Verilator 5.020\n")
            if "--binary" in argv:
                obj = folder / "obj"
                obj.mkdir()
                (obj / ("Vtb_top.exe" if os.name == "nt" else "Vtb_top")).write_bytes(b"fake binary")
                return completed(0)
            raise AssertionError(argv)
        tools = {"make": Path("/usr/bin/make"), "compiler": Path("/usr/bin/g++")}
        with (
            patch("verilator_mcp.build.find_verilator", return_value=Path("/usr/bin/verilator")),
            patch("verilator_mcp.build._trusted_toolchain", return_value=tools),
            patch("verilator_mcp.build._hash_file", return_value="f" * 64),
            patch("verilator_mcp.build.run_bounded", side_effect=fake_run),
        ):
            result = await build_run_project("project.json", 100)
        self.assertEqual(result["build_status"], "PASS", result)
        self.assertEqual(result["binary_sha256"], "f" * 64)
        self.assertEqual(result["verification_verdict"], "NOT_RUN")
        self.assertEqual(result["simulation_status"], "NOT_RUN")
        self.assertEqual(len(runs), 4)
        self.assertIn("--binary", runs[-1])
        self.assertTrue((self.artifacts / result["artifacts"]["result"]).is_file())
        self.assertNotIn(str(self.workspace), json.dumps(result))

    async def test_success_exit_without_binary_is_not_pass(self):
        async def fake_run(argv, folder, timeout_seconds, **kwargs):
            if "--version" in argv:
                return completed(0, "Verilator 5.020\n")
            return completed(0)
        with (
            patch("verilator_mcp.build.find_verilator", return_value=Path("/usr/bin/verilator")),
            patch("verilator_mcp.build._trusted_toolchain", return_value={
                "make": Path("/usr/bin/make"), "compiler": Path("/usr/bin/c++")
            }),
            patch("verilator_mcp.build._hash_file", return_value="f" * 64),
            patch("verilator_mcp.build.run_bounded", side_effect=fake_run),
        ):
            result = await build_run_project("project.json", 100)
        self.assertEqual(result["build_status"], "ARTIFACT_MISSING_OR_UNSAFE")
        self.assertIsNone(result["binary_sha256"])
        self.assertIsNone(result["binary_artifact"])


if __name__ == "__main__":
    unittest.main()
