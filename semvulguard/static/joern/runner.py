"""Lightweight wrapper around the Joern CLI.

Joern is *optional*: command construction is separated from execution so unit
tests can validate argv lists without Joern installed. The flow mirrors Joern's
own tooling: ``joern-parse`` builds a CPG from a source tree, then
``joern-export`` writes a graph representation (e.g. GraphML) to a directory.

Nothing here runs at import time and no network calls are made.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from semvulguard.utils.logging import get_logger

LOGGER = get_logger("semvulguard.static.joern.runner")

DEFAULT_REPR = "cpg14"
DEFAULT_FORMAT = "graphml"


class JoernRunner:
    """Build (and optionally execute) Joern CLI commands.

    The ``build_*_command`` methods return argv lists for inspection/testing.
    ``build_cpg`` and ``export_graph`` execute them via ``subprocess.run``
    unless ``dry_run`` is set, in which case they only log and return the argv.
    """

    def __init__(
        self,
        joern_bin: str = "joern",
        joern_parse_bin: str = "joern-parse",
        joern_export_bin: str = "joern-export",
        dry_run: bool = False,
    ) -> None:
        self.joern_bin = joern_bin
        self.joern_parse_bin = joern_parse_bin
        self.joern_export_bin = joern_export_bin
        self.dry_run = dry_run

    # -- command construction (pure, testable) ------------------------------

    def build_cpg_command(
        self, source_root: Path, output_cpg: Path
    ) -> list[str]:
        """Construct the ``joern-parse`` argv that builds a CPG."""
        return [
            self.joern_parse_bin,
            str(source_root),
            "--output",
            str(output_cpg),
        ]

    def export_graph_command(
        self,
        cpg_path: Path,
        output_dir: Path,
        repr: str = DEFAULT_REPR,
        format: str = DEFAULT_FORMAT,
    ) -> list[str]:
        """Construct the ``joern-export`` argv for a graph representation."""
        return [
            self.joern_export_bin,
            str(cpg_path),
            "--repr",
            repr,
            "--format",
            format,
            "--out",
            str(output_dir),
        ]

    # -- execution ----------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if both parse/export binaries are resolvable on PATH."""
        return (
            shutil.which(self.joern_parse_bin) is not None
            and shutil.which(self.joern_export_bin) is not None
        )

    def _run(self, argv: list[str]) -> list[str]:
        """Execute ``argv`` unless in dry-run mode; return the argv."""
        if self.dry_run:
            LOGGER.info("dry-run: %s", " ".join(argv))
            return argv
        LOGGER.info("running: %s", " ".join(argv))
        subprocess.run(argv, check=True)  # noqa: S603 - argv is constructed here
        return argv

    def build_cpg(self, source_root: Path, output_cpg: Path) -> list[str]:
        """Build a CPG from a source tree."""
        Path(output_cpg).parent.mkdir(parents=True, exist_ok=True)
        return self._run(self.build_cpg_command(source_root, output_cpg))

    def export_graph(
        self,
        cpg_path: Path,
        output_dir: Path,
        repr: str = DEFAULT_REPR,
        format: str = DEFAULT_FORMAT,
    ) -> list[str]:
        """Export a graph representation from a CPG."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return self._run(
            self.export_graph_command(cpg_path, output_dir, repr, format)
        )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semvulguard.static.joern.runner",
        description="Build a Joern CPG and export a graph representation.",
    )
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--cpg", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--repr", default=DEFAULT_REPR)
    parser.add_argument("--format", default=DEFAULT_FORMAT)
    parser.add_argument("--joern-parse-bin", default="joern-parse")
    parser.add_argument("--joern-export-bin", default="joern-export")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the commands without executing them",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    runner = JoernRunner(
        joern_parse_bin=args.joern_parse_bin,
        joern_export_bin=args.joern_export_bin,
        dry_run=args.dry_run,
    )
    if not args.dry_run and not runner.is_available():
        LOGGER.error(
            "joern binaries not found on PATH; use --dry-run to preview"
        )
        return 2
    parse = runner.build_cpg(args.source_root, args.cpg)
    export = runner.export_graph(args.cpg, args.out, args.repr, args.format)
    if args.dry_run:
        print(" ".join(parse))
        print(" ".join(export))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["JoernRunner", "DEFAULT_REPR", "DEFAULT_FORMAT"]
