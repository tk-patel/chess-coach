"""Smoke tests for the CLI surface (T0.1)."""

from typer.testing import CliRunner

from chesscoach.cli import app

runner = CliRunner()

COMMANDS = ("init", "status", "fetch", "import", "analyze", "puzzles", "report", "update")


def test_help_lists_all_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in COMMANDS:
        assert cmd in result.output, f"missing command: {cmd}"
    assert "openings" in result.output


def test_stub_commands_run_without_error():
    for cmd in ("init", "status", "puzzles", "report", "update"):
        result = runner.invoke(app, [cmd])
        assert result.exit_code == 0, result.output
        assert "not implemented" in result.output
