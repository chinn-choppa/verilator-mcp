"""Golden LCOV parsing and bounded coverage-report safety tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verilator_mcp.coverage_report import coverage_report_project, parse_lcov_info
from verilator_mcp.execution import ProcessResult
from verilator_mcp.workspace import ManifestError


class LCOVParserTests(unittest.TestCase):
    def test_golden_line_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "rtl").mkdir()
            text = "TN:synthetic\nSF:rtl/top.sv\nDA:4,3\nDA:5,0\nend_of_record\n"
            got = parse_lcov_info(text, root)
            self.assertEqual(got["status"], "READY")
            self.assertEqual(got["covered_lines"], 1)
            self.assertEqual(got["total_lines"], 2)
            self.assertEqual(got["line_rate"], 0.5)
            self.assertEqual(got["files"], [{
                "source": "rtl/top.sv", "total_lines": 2, "covered_lines": 1,
            }])

    def test_zero_points_not_claimed_as_zero_percent(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = parse_lcov_info("SF:top.sv\nend_of_record\n", Path(tmp))
        self.assertEqual(result["status"], "EMPTY")
        self.assertIsNone(result["total_lines"])
        self.assertNotIn("line_rate", result)

    def test_malformed_and_oversized_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("DA:5,2\n", "SF:top.sv\nDA:five,1\n"):
                with self.subTest(bad=bad):
                    with self.assertRaises(ManifestError):
                        parse_lcov_info(bad, Path(tmp))
            with self.assertRaises(ManifestError):
                parse_lcov_info("x" * 1_048_577, Path(tmp))


class CoverageToolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.workspace = root / "rtl"
        self.artifacts = root / "artifacts"
        self.workspace.mkdir()
        self.artifacts.mkdir()
        self.run_id = "sim-" + "b" * 32
        self.folder = self.artifacts / self.run_id
        self.folder.mkdir()
        (self.folder / "coverage.dat").write_text("C 'dummy' 1\n", encoding="utf-8")
        self.record = {
            "operation": "simulation", "run_id": self.run_id,
            "verification_verdict": "PASS", "coverage_status": "RECORDED",
        }
        self.save()
        env = patch.dict(os.environ, {
            "VERILATOR_MCP_WORKSPACE_ROOT": str(self.workspace),
            "VERILATOR_MCP_ARTIFACT_ROOT": str(self.artifacts),
        })
        env.start()
        self.addCleanup(env.stop)

    def save(self):
        (self.folder / "result.json").write_text(json.dumps(self.record), encoding="utf-8")

    async def test_real_command_shape_and_parsed_summary(self):
        commands = []
        async def fake_run(argv, cwd, timeout_seconds, **kwargs):
            commands.append(argv)
            (cwd / "coverage.info").write_text(
                "SF:rtl/top.sv\nDA:4,2\nDA:5,0\nend_of_record\n", encoding="utf-8"
            )
            return ProcessResult(
                exit_code=0, stdout="", stderr="", duration_ms=2,
                timed_out=False, stdout_truncated=False, stderr_truncated=False,
            )
        with (
            patch("verilator_mcp.coverage_report._trusted_coverage_tool",
                  return_value=Path("/usr/bin/verilator_coverage")),
            patch("verilator_mcp.coverage_report.run_bounded", side_effect=fake_run),
        ):
            result = await coverage_report_project(self.run_id)
        self.assertEqual(result["report_status"], "READY")
        self.assertEqual(result["summary"]["line_rate"], 0.5)
        self.assertEqual(result["simulation_verdict"], "PASS")
        self.assertEqual(commands[0][1], "--write-info")
        self.assertEqual(commands[0][-1], str(self.folder / "coverage.dat"))
        self.assertTrue((self.folder / "coverage_report.json").is_file())

    async def test_missing_data_is_not_zero_coverage(self):
        self.record["coverage_status"] = "NOT_OBSERVED"
        self.save()
        got = await coverage_report_project(self.run_id)
        self.assertEqual(got["report_status"], "NOT_OBSERVED")
        self.assertFalse(got["executed"])
        self.assertNotIn("summary", got)
        self.record["coverage_status"] = "DISABLED"
        self.save()
        got = await coverage_report_project(self.run_id)
        self.assertEqual(got["report_status"], "NOT_ENABLED")

    async def test_missing_tool_is_not_ready(self):
        with patch("verilator_mcp.coverage_report._trusted_coverage_tool", return_value=None):
            got = await coverage_report_project(self.run_id)
        self.assertEqual(got["report_status"], "NOT_AVAILABLE")
        self.assertFalse(got["executed"])

    async def test_invalid_ids_and_limits(self):
        for value in ("../escape", "sim-x", "/etc/passwd"):
            with self.assertRaises(ManifestError):
                await coverage_report_project(value)
        for value in (0, 61, True, "20"):
            with self.assertRaises(ManifestError):
                await coverage_report_project(self.run_id, value)


if __name__ == "__main__":
    unittest.main()
