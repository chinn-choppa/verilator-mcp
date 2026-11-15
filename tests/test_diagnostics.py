"""Офлайн-контракты разбора диагностик Verilator, без EDA."""
import pytest

from verilator_mcp.diagnostics import parse_diagnostics_text


def test_realistic_log():
    text = ("%Warning-WIDTH: rtl/top.sv:12:4: Operator ADD expects 8 bits\n"
            "%Error-UNSUPPORTED: rtl/top.sv:22:2: Unsupported construct")
    result = parse_diagnostics_text(text, "verilator")
    assert result["count"] == 2
    assert [item["severity"] for item in result["items"]] == ["warning", "error"]
    assert result["truncated"] is False


def test_unknown_lines_do_not_become_success():
    result = parse_diagnostics_text("unknown format\nexit 1", "verilator")
    assert result["count"] == 0
    assert result["items"] == []
    assert "pass" not in result


def test_limit_returns_true_count():
    sample = "%Warning-WIDTH: rtl/top.sv:12:4: Operator ADD expects 8 bits"
    result = parse_diagnostics_text("\n".join([sample] * 3), "verilator", limit=1)
    assert result["count"] == 3
    assert len(result["items"]) == 1
    assert result["truncated"] is True


@pytest.mark.parametrize("limit", [0, 201, -1, True, 1.4])
def test_invalid_limit_rejected(limit):
    with pytest.raises(ValueError):
        parse_diagnostics_text("", "verilator", limit=limit)


def test_oversized_text_rejected():
    with pytest.raises(ValueError):
        parse_diagnostics_text("x" * 1_048_577, "verilator")


def test_windows_drive_path():
    text = r"%Error-UNSUPPORTED: C:\rtl\top.sv:8:3: unsupported"
    result = parse_diagnostics_text(text, "verilator")
    assert result["items"][0]["file"] == r"C:\rtl\top.sv"
    assert result["items"][0]["line"] == 8
    assert result["items"][0]["column"] == 3


def test_unknown_tool_is_rejected():
    with pytest.raises(ValueError):
        parse_diagnostics_text("", "bash")
