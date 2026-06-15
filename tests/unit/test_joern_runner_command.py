"""Tests for Joern command construction (no Joern installation required)."""

from __future__ import annotations

from pathlib import Path

from semvulguard.static.joern.runner import (
    DEFAULT_FORMAT,
    DEFAULT_REPR,
    JoernRunner,
)


def test_build_cpg_command_basic():
    runner = JoernRunner()
    argv = runner.build_cpg_command(Path("repo"), Path("artifacts/cpg.bin"))
    assert argv[0] == "joern-parse"
    assert "repo" in argv
    assert "--output" in argv
    assert "artifacts/cpg.bin" in argv


def test_export_graph_command_defaults():
    runner = JoernRunner()
    argv = runner.export_graph_command(Path("cpg.bin"), Path("out"))
    assert argv[0] == "joern-export"
    assert "cpg.bin" in argv
    assert "--repr" in argv and DEFAULT_REPR in argv
    assert "--format" in argv and DEFAULT_FORMAT in argv
    assert "--out" in argv and "out" in argv


def test_export_graph_command_custom_repr_and_format():
    runner = JoernRunner()
    argv = runner.export_graph_command(
        Path("cpg.bin"), Path("out"), repr="pdg", format="dot"
    )
    assert "pdg" in argv
    assert "dot" in argv


def test_custom_binaries():
    runner = JoernRunner(
        joern_parse_bin="/opt/joern/joern-parse",
        joern_export_bin="/opt/joern/joern-export",
    )
    assert runner.build_cpg_command(Path("r"), Path("c"))[0] == (
        "/opt/joern/joern-parse"
    )
    assert runner.export_graph_command(Path("c"), Path("o"))[0] == (
        "/opt/joern/joern-export"
    )


def test_dry_run_build_cpg_does_not_execute(tmp_path: Path):
    runner = JoernRunner(dry_run=True)
    cpg = tmp_path / "nested" / "cpg.bin"
    argv = runner.build_cpg(Path("repo"), cpg)
    assert argv == runner.build_cpg_command(Path("repo"), cpg)
    assert cpg.parent.exists()


def test_dry_run_export_graph_does_not_execute(tmp_path: Path):
    runner = JoernRunner(dry_run=True)
    out = tmp_path / "export"
    argv = runner.export_graph(Path("cpg.bin"), out)
    assert argv == runner.export_graph_command(Path("cpg.bin"), out)
    assert out.exists()


def test_cli_dry_run_prints_commands(capsys):
    from semvulguard.static.joern.runner import main

    rc = main(
        [
            "--source-root",
            "repo",
            "--cpg",
            "artifacts/joern/cpg.bin",
            "--out",
            "artifacts/joern/export",
            "--format",
            "graphml",
            "--dry-run",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "joern-parse" in out
    assert "joern-export" in out
