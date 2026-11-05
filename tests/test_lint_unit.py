"""Ограниченный lint: unit, negative, timeout и проверка записанных артефактов."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verilator_mcp.execution import ProcessResult, run_bounded
from verilator_mcp.lint import lint_run_project


def process(exit_code=0, stdout="", stderr="", *, timeout=False, truncated=False):
    return ProcessResult(
        exit_code=exit_code, stdout=stdout, stderr=stderr,
        stdout_truncated=truncated, stderr_truncated=False,
        duration_ms=3, timed_out=timeout,
    )


class LintUnitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / "rtl"
        self.artifacts = base / "out"
        self.root.mkdir()
        self.artifacts.mkdir()
        self.source = self.root / "top.sv"
        self.source.write_text("module top; endmodule\n", encoding="utf-8")
        (self.root / "project.json").write_text(json.dumps({
            "schema_version": 1,
            "top": "top",
            "sources": ["top.sv"],
            "defines": {"FEATURE": "1"},
            "parameters": {"WIDTH": 8},
        }), encoding="utf-8")
        env_patch = patch.dict(os.environ, {
            "VERILATOR_MCP_WORKSPACE_ROOT": str(self.root),
            "VERILATOR_MCP_ARTIFACT_ROOT": str(self.artifacts),
        })
        env_patch.start()
        self.addCleanup(env_patch.stop)

    async def mocked(self, output=None, *, touch=False):
        calls = []
        output = output if output is not None else process()
        async def fake_runner(argv, cwd, timeout_seconds, **kwargs):
            calls.append((argv, cwd, timeout_seconds))
            if "--version" in argv:
                return process(stdout="Verilator 5.054 2026\n")
            if touch:
                self.source.write_text("module top; wire x; endmodule\n", encoding="utf-8")
            return output

        with (
            patch("verilator_mcp.lint.find_verilator", return_value=Path("/usr/bin/verilator")),
            patch("verilator_mcp.lint.run_bounded", side_effect=fake_runner),
        ):
            result = await lint_run_project("project.json", 4)
        return result, calls

    async def test_success_without_verification_pass(self):
        result, calls = await self.mocked()
        self.assertEqual(result["lint_status"], "PASS")
        self.assertEqual(result["verification_verdict"], "NOT_RUN")
        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(result["executed"])
        self.assertEqual(len(calls), 2)
        self.assertIn("--lint-only", calls[1][0])
        self.assertIn("-DFEATURE=1", calls[1][0])
        self.assertIn("-GWIDTH=8", calls[1][0])
        self.assertNotIn("--binary", calls[1][0])
        self.assertFalse(any(arg.startswith("-f") for arg in calls[1][0]))
        folder = self.artifacts / result["run_id"]
        self.assertTrue((folder / "request.json").is_file())
        self.assertTrue((folder / "result.json").is_file())
        self.assertEqual(
            json.loads((folder / "result.json").read_text(encoding="utf-8"))["lint_status"],
            "PASS",
        )
        self.assertEqual(len(result["source_sha256"]["top.sv"]), 64)
        self.assertNotIn(str(self.root), json.dumps(result))

    async def test_failed_lint_is_not_pass(self):
        result, _ = await self.mocked(process(
            exit_code=1,
            stderr="%Error: top.sv:1:1: Unexpected token\n",
        ))
        self.assertEqual(result["lint_status"], "FAIL")
        self.assertEqual(result["verification_verdict"], "NOT_RUN")
        self.assertEqual(result["diagnostics"]["count"], 1)

    async def test_warnings_and_truncated_logs_are_distinct(self):
        warning = process(stderr="%Warning-WIDTH: top.sv:2:1: Mismatch\n")
        result, _ = await self.mocked(warning)
        self.assertEqual(result["lint_status"], "PASS_WITH_WARNINGS")
        cut, _ = await self.mocked(process(truncated=True))
        self.assertEqual(cut["lint_status"], "INCOMPLETE")
        self.assertTrue(cut["logs_truncated"])

    async def test_timeout_and_input_changed_are_not_success(self):
        result, _ = await self.mocked(process(exit_code=-9, timeout=True))
        self.assertEqual(result["lint_status"], "TIMEOUT")
        changed, _ = await self.mocked(touch=True)
        self.assertEqual(changed["lint_status"], "INPUT_CHANGED")

    async def test_invalid_timeout_and_missing_binary_fail_closed(self):
        for val in (0, 181, True, "4"):
            with self.subTest(val=val):
                with self.assertRaises(ValueError):
                    await lint_run_project("project.json", val)
        with patch("verilator_mcp.lint.find_verilator", return_value=None):
            result = await lint_run_project("project.json", 4)
        self.assertEqual(result["lint_status"], "NOT_AVAILABLE")
        self.assertFalse(result["executed"])
        self.assertEqual(list(self.artifacts.iterdir()), [])


class ProcessExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_process_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = await run_bounded(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                Path(tmp), 1,
            )
            self.assertTrue(result.timed_out)
            self.assertLess(result.duration_ms, 8_000)

    async def test_real_process_log_limit_and_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = await run_bounded(
                [sys.executable, "-c",
                 "import sys; sys.stdout.buffer.write(b'a'*100000); sys.stdout.flush()"],
                Path(tmp), 6, max_log_bytes=256,
            )
            self.assertFalse(result.timed_out)
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(len(result.stdout.encode("utf-8")), 256)
            self.assertTrue(result.stdout_truncated)


if __name__ == "__main__":
    unittest.main()
