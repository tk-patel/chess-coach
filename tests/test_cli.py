"""Smoke tests for the CLI surface (T0.1) plus init (T0.2)."""

from typer.testing import CliRunner

from chesscoach.cli import app

runner = CliRunner()

COMMANDS = ("init", "status", "fetch", "import", "analyze", "puzzles", "report", "update")

STUBS = ("status", "puzzles", "report", "update")


def test_help_lists_all_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in COMMANDS:
        assert cmd in result.output, f"missing command: {cmd}"
    assert "openings" in result.output


def test_stub_commands_run_without_error():
    for cmd in STUBS:
        result = runner.invoke(app, [cmd])
        assert result.exit_code == 0, result.output
        assert "not implemented" in result.output


def test_init_creates_project_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "config.toml").exists()
    assert (tmp_path / "data" / "chesscoach.db").exists()
    assert (tmp_path / "data" / "raw").is_dir()
    assert (tmp_path / "data" / "openings").is_dir()
    assert (tmp_path / "out").is_dir()
