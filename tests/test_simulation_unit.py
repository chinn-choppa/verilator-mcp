"""Simulation verdict, trusted build artifact and real cancellation checks."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verilator_mcp.execution import ProcessResult, run_bounded
from verilator_mcp.simulation import simulation_run_project
from verilator_mcp.workspace import ManifestError


def process(exit_code=0, *, out="", err="", timeout=False, truncated=False):
    return ProcessResult(
        exit_code=exit_code,
        stdout=out,
        stderr=err,
        stdout_truncated=truncated,
        stderr_truncated=False,
        duration_ms=11,
        timed_out=timeout,
    )


class SimulationUnitTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.workspace = base / "workspace"
        self.artifacts = base / "artifacts"
        self.workspace.mkdir()
        self.artifacts.mkdir()
        self.build_id = "build-" + "a" * 32
        self.build_dir = self.artifacts / self.build_id
        (self.build_dir / "obj").mkdir(parents=True)
        self.binary = self.build_dir / "obj" / ("Vtb_test.exe" if os.name == "nt" else "Vtb_test")
        self.binary.write_bytes(b"original test binary")
        self.digest = hashlib.sha256(self.binary.read_bytes()).hexdigest()
        toolhash = "f" * 64
        self.request = {
            "build_id": self.build_id, "config_sha256": "1" * 64,
            "source_sha256": {"tb.sv": "2" * 64},
            "project": {"testbench_top": "tb_test"},
        }
        self.record = {
            "build_id": self.build_id, "build_status": "PASS", "executed": True,
            "simulation_status": "NOT_RUN", "config_sha256": "1" * 64,
            "source_sha256": {"tb.sv": "2" * 64},
            "binary_sha256": self.digest,
            "binary_artifact": f"{self.build_id}/obj/{self.binary.name}",
            "tool_versions": {"verilator": "Verilator 5.020", "make": "Make 4", "compiler": "g++ 12"},
            "tool_sha256": {"verilator": toolhash, "make": toolhash, "compiler": toolhash},
        }
        self.save_records()
        env = patch.dict(os.environ, {
            "VERILATOR_MCP_WORKSPACE_ROOT": str(self.workspace),
            "VERILATOR_MCP_ARTIFACT_ROOT": str(self.artifacts),
        })
        env.start()
        self.addCleanup(env.stop)

    def save_records(self):
        (self.build_dir / "request.json").write_text(json.dumps(self.request), encoding="utf-8")
        (self.build_dir / "result.json").write_text(json.dumps(self.record), encoding="utf-8")

    async def emulate(self, *, code=0, marker=True, finish=True, fatal=False, timeout=False, truncated=False):
        calls = []
        async def fake_run(argv, cwd, timeout_seconds, **kwargs):
            calls.append(argv)
            token = argv[-1].split("=", 1)[1]
            content = (f"VERILATOR_MCP_PASS:{token}\n" if marker else "")
            content += ("- tb_test.sv:12: Verilog $finish\n" if finish else "")
            return process(
                code, out=content, err="%Error: Assertion failed\n" if fatal else "",
                timeout=timeout, truncated=truncated,
            )
        with patch("verilator_mcp.simulation.run_bounded", side_effect=fake_run):
            result = await simulation_run_project(self.build_id, 3, seed=42)
        return result, calls

    async def test_success_requires_exact_per_run_marker_and_finish(self):
        result, calls = await self.emulate()
        self.assertEqual(result["run_status"], "PASS")
        self.assertEqual(result["verification_verdict"], "PASS")
        self.assertTrue(result["finish_observed"])
        self.assertTrue(result["pass_marker_observed"])
        self.assertEqual(result["seed"], 42)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], str(self.binary))
        self.assertEqual(calls[0][1], "+verilator+seed+42")
        self.assertTrue(calls[0][2].startswith("+VERILATOR_MCP_TOKEN="))
        self.assertTrue((self.artifacts / result["artifacts"]["result"]).is_file())
        self.assertNotIn(str(self.workspace), json.dumps(result))

    async def test_exit_zero_without_explicit_pass_never_passes(self):
        no_marker, _ = await self.emulate(marker=False)
        self.assertEqual(no_marker["run_status"], "FINISHED_UNVERIFIED")
        self.assertEqual(no_marker["verification_verdict"], "INCONCLUSIVE")
        no_finish, _ = await self.emulate(finish=False)
        self.assertEqual(no_finish["run_status"], "EXIT_ZERO_UNVERIFIED")
        self.assertEqual(no_finish["verification_verdict"], "INCONCLUSIVE")

    async def test_fatal_timeout_and_truncated_logs(self):
        fatal, _ = await self.emulate(code=134, fatal=True)
        self.assertEqual(fatal["run_status"], "RUN_FAIL")
        self.assertEqual(fatal["verification_verdict"], "FAIL")
        self.assertTrue(fatal["fatal_observed"])
        timeout, _ = await self.emulate(timeout=True)
        self.assertEqual(timeout["run_status"], "TIMEOUT")
        self.assertEqual(timeout["verification_verdict"], "FAIL")
        incomplete, _ = await self.emulate(truncated=True)
        self.assertEqual(incomplete["run_status"], "INCOMPLETE")
        self.assertEqual(incomplete["verification_verdict"], "INCONCLUSIVE")

    async def test_tampered_binary_is_never_executed(self):
        self.binary.write_bytes(b"tampered")
        with patch("verilator_mcp.simulation.run_bounded") as runner:
            result = await simulation_run_project(self.build_id)
        self.assertFalse(result["executed"])
        self.assertEqual(result["run_status"], "ARTIFACT_INVALID")
        self.assertEqual(result["verification_verdict"], "NOT_RUN")
        runner.assert_not_called()

    async def test_rejects_invalid_id_bad_provenance_and_invalid_limits(self):
        for build_id in ("../escape", self.build_id + "/obj", "build-x", "/tmp/root"):
            with self.subTest(build_id=build_id):
                with self.assertRaises(ManifestError):
                    await simulation_run_project(build_id)
        for timeout in (0, 181, "10", True):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ManifestError):
                    await simulation_run_project(self.build_id, timeout_seconds=timeout)
        for seed in (0, -1, 2147483648, "7", True):
            with self.subTest(seed=seed):
                with self.assertRaises(ManifestError):
                    await simulation_run_project(self.build_id, seed=seed)
        self.record["build_status"] = "BUILD_FAIL"
        self.save_records()
        with self.assertRaises(ManifestError):
            await simulation_run_project(self.build_id)

    async def test_rejects_path_escape_and_forged_binary_filename(self):
        self.record["binary_artifact"] = "../escape"
        self.save_records()
        with self.assertRaises(ManifestError):
            await simulation_run_project(self.build_id)


class ProcessCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_terminates_real_child_without_waiting_for_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = asyncio.create_task(
                run_bounded(
                    [sys.executable, "-c", "import time; time.sleep(30)"],
                    Path(tmp), 120,
                )
            )
            await asyncio.sleep(0.2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=8)


if __name__ == "__main__":
    unittest.main()
