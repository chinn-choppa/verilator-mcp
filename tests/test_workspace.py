"""Негативные и позитивные тесты read-only workspace без MCP/Verilator."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from verilator_mcp.workspace import ManifestError, validate_manifest


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "workspace"
        self.artifacts = self.base / "artifacts"
        self.root.mkdir()
        self.artifacts.mkdir()
        (self.root / "rtl").mkdir()
        (self.root / "includes").mkdir()
        (self.root / "rtl" / "top.sv").write_text("module top; endmodule\n", encoding="utf-8")
        (self.root / "rtl" / "helper.v").write_text("module helper; endmodule\n", encoding="utf-8")
        self.basic = {"schema_version": 1, "top": "top", "sources": ["rtl/top.sv"]}
        self.write("project.json", self.basic)

    def write(self, name: str, obj) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj), encoding="utf-8")

    def validate(self, name="project.json"):
        return validate_manifest(
            name,
            workspace_root=str(self.root),
            artifact_root=str(self.artifacts),
        )

    def test_minimal_project_is_read_only_and_does_not_expose_roots(self):
        before = set(self.root.rglob("*")), set(self.artifacts.rglob("*"))
        project = self.validate()
        after = set(self.root.rglob("*")), set(self.artifacts.rglob("*"))
        self.assertEqual(before, after)
        summary = project.public_summary()
        self.assertEqual(summary["state"], "VALID")
        self.assertFalse(summary["executed"])
        self.assertEqual(summary["project"]["sources"], ["rtl/top.sv"])
        self.assertNotIn(str(self.root), str(summary))
        self.assertEqual(len(summary["config_sha256"]), 64)

    def test_nested_filelist_order_and_canonical_hash(self):
        self.write("lists/a.json", {
            "schema_version": 1, "sources": ["rtl/helper.v"],
            "include_dirs": ["includes"],
        })
        self.write("project.json", {
            **self.basic,
            "filelists": ["lists/a.json"],
            "include_dirs": ["includes"],
            "defines": {"DEBUG": "", "MODE": "FAST"},
            "parameters": {"WIDTH": 8},
            "testbench_top": "tb_top",
        })
        project = self.validate()
        self.assertEqual(
            project.public_summary()["project"]["sources"], ["rtl/helper.v", "rtl/top.sv"]
        )
        self.assertEqual(project.public_summary()["project"]["include_dirs"], ["includes"])
        self.assertEqual(dict(project.defines), {"DEBUG": "", "MODE": "FAST"})
        self.assertEqual(dict(project.parameters), {"WIDTH": 8})
        self.assertEqual(self.validate().public_summary(), project.public_summary())

    def test_parent_escape_and_absolute_and_windows_drive_rejected(self):
        for path in ("../private.sv", "/tmp/a.sv", "C:/private.sv", "rtl\\top.sv", "rtl//top.sv"):
            with self.subTest(path=path):
                self.write("project.json", {**self.basic, "sources": [path]})
                with self.assertRaises(ManifestError):
                    self.validate()

    def test_symlink_escape_is_rejected(self):
        external = self.base / "outside.sv"
        external.write_text("module private; endmodule", encoding="utf-8")
        link = self.root / "rtl" / "link.sv"
        try:
            link.symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("Символьные ссылки недоступны для текущего пользователя Windows")
        self.write("project.json", {**self.basic, "sources": ["rtl/link.sv"]})
        with self.assertRaises(ManifestError):
            self.validate()

    def test_filelist_cycle(self):
        self.write("lists/a.json", {
            "schema_version": 1, "filelists": ["lists/b.json"]
        })
        self.write("lists/b.json", {
            "schema_version": 1, "filelists": ["lists/a.json"]
        })
        self.write("project.json", {**self.basic, "filelists": ["lists/a.json"]})
        with self.assertRaisesRegex(ManifestError, "Циклическая"):
            self.validate()

    def test_duplicate_source_and_unsupported_keys(self):
        self.write("project.json", {**self.basic, "sources": ["rtl/top.sv", "rtl/top.sv"]})
        with self.assertRaises(ManifestError):
            self.validate()
        self.write("project.json", {**self.basic, "verilator_flags": ["--exe"]})
        with self.assertRaisesRegex(ManifestError, "Неизвестное поле"):
            self.validate()

    def test_invalid_defines_and_parameters(self):
        cases = [
            {"defines": {"EVIL": "1; rm -rf /"}},
            {"defines": {"-Wno-fatal": "1"}},
            {"parameters": {"WIDTH": "-1"}},
            {"parameters": {"WIDTH": True}},
            {"top": "--binary"},
            {"schema_version": True},
        ]
        for bad in cases:
            with self.subTest(bad=bad):
                self.write("project.json", {**self.basic, **bad})
                with self.assertRaises(ManifestError):
                    self.validate()

    def test_windows_reserved_names_rejected_everywhere(self):
        self.write("project.json", {**self.basic, "sources": ["rtl/CON.sv"]})
        with self.assertRaises(ManifestError):
            self.validate()

    def test_invalid_root_and_output_overlap(self):
        with self.assertRaises(ManifestError):
            validate_manifest("project.json", workspace_root="relative", artifact_root=str(self.artifacts))
        with self.assertRaises(ManifestError):
            validate_manifest("project.json", workspace_root=str(self.root), artifact_root=str(self.root))
        with self.assertRaises(ManifestError):
            validate_manifest("project.json", workspace_root=str(self.root), artifact_root=str(self.root / "rtl"))

    def test_missing_file_and_include_directory(self):
        self.write("project.json", {**self.basic, "sources": ["rtl/missing.sv"]})
        with self.assertRaises(ManifestError):
            self.validate()
        self.write("project.json", {**self.basic, "include_dirs": ["missing"]})
        with self.assertRaises(ManifestError):
            self.validate()

    def test_duplicate_json_fields_and_malformed_utf8(self):
        (self.root / "project.json").write_text(
            '{"schema_version":1,"top":"top","top":"other","sources":["rtl/top.sv"]}',
            encoding="utf-8",
        )
        with self.assertRaises(ManifestError):
            self.validate()
        (self.root / "project.json").write_bytes(b"\xff\xfe")
        with self.assertRaises(ManifestError):
            self.validate()

    def test_environment_roots_are_authoritative_for_mcp(self):
        with patch.dict(os.environ, {
            "VERILATOR_MCP_WORKSPACE_ROOT": str(self.root),
            "VERILATOR_MCP_ARTIFACT_ROOT": str(self.artifacts),
        }):
            self.assertEqual(
                validate_manifest("project.json").public_summary()["state"], "VALID"
            )


if __name__ == "__main__":
    unittest.main()
