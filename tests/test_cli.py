"""Smoke tests for the CLI surface (T0.1) plus init (T0.2) and import (T1.2)."""

from pathlib import Path

from typer.testing import CliRunner

from chesscoach.cli import app

runner = CliRunner()

COMMANDS = ("init", "status", "fetch", "import", "analyze", "puzzles", "report", "update")

STUBS = ()


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


def test_import_command_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0

    config_path = tmp_path / "config.toml"
    config_path.write_text(config_path.read_text().replace("CHANGE_ME", "PaulMorphy"))

    fixture = Path(__file__).resolve().parent / "fixtures" / "sample_games.pgn"

    first = runner.invoke(app, ["import", str(fixture)])
    assert first.exit_code == 0, first.output
    assert "imported 1 games" in first.output

    second = runner.invoke(app, ["import", str(fixture)])
    assert second.exit_code == 0, second.output
    assert "imported 0 games" in second.output
    assert "skipped 1 existing" in second.output


def test_puzzles_command_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0

    result = runner.invoke(app, ["puzzles"])
    assert result.exit_code == 0, result.output
    assert "built 0 puzzles" in result.output
    assert (tmp_path / "out" / "puzzles.json").exists()


def test_status_command(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0, result.output
    assert "games: 0" in result.output
    assert "last fetch: never" in result.output
    assert "puzzles: 0" in result.output


def test_update_command_offline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"]).exit_code == 0

    config_path = tmp_path / "config.toml"
    config_path.write_text(config_path.read_text().replace("CHANGE_ME", "PaulMorphy"))

    fixture = Path(__file__).resolve().parent / "fixtures" / "sample_games.pgn"
    assert runner.invoke(app, ["import", str(fixture)]).exit_code == 0

    # make the fetch step fail cleanly (no network in tests)
    from chesscoach import fetch as fetch_mod

    class _Offline:
        def get(self, url, headers):
            return fetch_mod.Response(404, {}, None, "")

    monkeypatch.setattr(fetch_mod, "RequestsTransport", lambda ua: _Offline())

    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0, result.output
    assert "fetch skipped" in result.output
    assert "update done:" in result.output
    assert (tmp_path / "out" / "trainer.html").exists()
    assert (tmp_path / "out" / "index.html").exists()
