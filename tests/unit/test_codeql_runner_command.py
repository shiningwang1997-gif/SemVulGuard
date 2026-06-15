"""Tests for CodeQL command construction (no CodeQL installation required)."""

from __future__ import annotations

from pathlib import Path

from semvulguard.static.codeql.runner import (
    DEFAULT_QUERY_SUITE,
    CodeQLRunner,
)


def test_build_database_command_basic():
    runner = CodeQLRunner()
    argv = runner.build_database_command(
        Path("repo"), Path("artifacts/db"), "cpp"
    )
    assert argv[:3] == ["codeql", "database", "create"]
    assert "artifacts/db" in argv
    assert "--language=cpp" in argv
    assert "--source-root=repo" in argv


def test_build_database_command_with_build_command():
    runner = CodeQLRunner()
    argv = runner.build_database_command(
        Path("repo"), Path("db"), "cpp", command="make -j4"
    )
    assert "--command=make -j4" in argv


def test_build_database_command_threads_and_ram():
    runner = CodeQLRunner(threads=8, ram=32768)
    argv = runner.build_database_command(Path("repo"), Path("db"), "cpp")
    assert "--threads=8" in argv
    assert "--ram=32768" in argv


def test_build_analyze_command_default_suite():
    runner = CodeQLRunner()
    argv = runner.build_analyze_command(Path("db"), Path("out.sarif"))
    assert argv[:3] == ["codeql", "database", "analyze"]
    assert DEFAULT_QUERY_SUITE in argv
    assert "--format=sarifv2.1.0" in argv
    assert "--output=out.sarif" in argv


def test_build_analyze_command_custom_suite():
    runner = CodeQLRunner()
    suite = "codeql/cpp-queries:codeql-suites/cpp-security-and-quality.qls"
    argv = runner.build_analyze_command(Path("db"), Path("out.sarif"), suite)
    assert suite in argv


def test_custom_codeql_bin():
    runner = CodeQLRunner(codeql_bin="/opt/codeql/codeql")
    argv = runner.build_database_command(Path("repo"), Path("db"), "cpp")
    assert argv[0] == "/opt/codeql/codeql"


def test_dry_run_build_database_does_not_execute():
    runner = CodeQLRunner(dry_run=True)
    argv = runner.build_database(Path("repo"), Path("db"), "cpp")
    assert argv == runner.build_database_command(Path("repo"), Path("db"), "cpp")


def test_dry_run_analyze_does_not_execute(tmp_path: Path):
    runner = CodeQLRunner(dry_run=True)
    out = tmp_path / "nested" / "out.sarif"
    argv = runner.analyze_database(Path("db"), out)
    assert argv == runner.build_analyze_command(Path("db"), out)
    # analyze_database still ensures the output's parent dir exists.
    assert out.parent.exists()


def test_cli_dry_run_prints_commands(capsys):
    from semvulguard.static.codeql.runner import main

    rc = main(
        [
            "--source-root",
            "repo",
            "--database",
            "artifacts/db",
            "--language",
            "cpp",
            "--output",
            "artifacts/out.sarif",
            "--dry-run",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "database create" in out
    assert "database analyze" in out
