from __future__ import annotations

import argparse
import sys
import time

from .builder import GalleryBuilder
from .config import GalleryConfig
from .discovery import discover
from .progress import ProgressEvent


def _console_progress(event: ProgressEvent) -> None:
    timestamp = time.strftime("%H:%M:%S")
    example = f"  {event.example}" if event.example else ""
    print(
        f"{timestamp}  {event.stage.upper():<9}{example}\n" f"          {'':9}  {event.message}",
        file=sys.stderr,
        flush=True,
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="e2s-gallery")
    result.add_argument("--root", default=".", help="project root (default: current directory)")
    result.add_argument("--config-file", help="gallery TOML file, relative to the project root")
    result.add_argument("--examples-dir", default="examples")
    result.add_argument("--docs-dir", default="docs")
    subcommands = result.add_subparsers(dest="command", required=True)
    list_command = subcommands.add_parser("list", help="list discovered examples")
    list_command.add_argument("selectors", nargs="*")
    build_command = subcommands.add_parser("build", help="execute and render the gallery")
    build_command.add_argument("selectors", nargs="*", help="paths, sections, stems, or globs")
    build_command.add_argument("--execute", choices=("stale", "always", "never"), default=None)
    build_command.add_argument("--force", action="store_true", help="ignore successful cached runs")
    build_command.add_argument(
        "--jobs", type=int, default=None, help="parallel jobs; GPU-safe default is 1"
    )
    subcommands.add_parser(
        "render",
        help="recreate the complete gallery from retained results without execution",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    overrides = {"jobs": args.jobs} if getattr(args, "jobs", None) else None
    config = GalleryConfig.load(
        args.root,
        examples_dir=args.examples_dir,
        docs_dir=args.docs_dir,
        config_file=args.config_file,
        overrides=overrides,
    )
    if args.command == "list":
        for example in discover(config, args.selectors):
            print(f"{example.relative.as_posix():55} {example.title}")
        return 0
    builder = GalleryBuilder(config, progress=_console_progress)
    if args.command == "render":
        build_report = builder.render()
    else:
        build_report = builder.build(args.selectors, execute=args.execute, force=args.force)
    for example, result in build_report.failures:
        print(f"\n{example.relative}:\n{result.error or 'execution failed'}", file=sys.stderr)
    return 1 if build_report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
