from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .audit import render_audit_report, run_public_audit
from .config import ProjectPulseConfig
from .policy import MeaningfulChangeDetector
from .reporting import render_json_report, render_text_report
from .scanner import FilesystemScanner


def build_parser() -> argparse.ArgumentParser:
    config_parent = argparse.ArgumentParser(add_help=False)
    config_parent.add_argument(
        "--config",
        type=Path,
        default=argparse.SUPPRESS,
        help="Optional path to a Project Pulse TOML config file.",
    )

    parser = argparse.ArgumentParser(
        prog="project-pulse",
        description="Scan real local work and turn it into an explainable publishing decision.",
        parents=[config_parent],
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan the watched root and print a report.",
        parents=[config_parent],
    )
    scan_parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Override the watched root for this run.",
    )
    scan_parser.add_argument(
        "--json",
        action="store_true",
        help="Render the scan result as JSON.",
    )
    subparsers.add_parser(
        "public-audit",
        help="Scan the repository for obvious publish-safety issues before going public.",
        parents=[config_parent],
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config_arg = getattr(args, "config", None)
    if config_arg is None:
        if args.command == "public-audit":
            config = ProjectPulseConfig.load_public_audit_default(Path.cwd())
        else:
            config = ProjectPulseConfig.load_default(Path.cwd())
    else:
        config_path = config_arg.resolve()
        if not config_path.exists():
            parser.error(f"Config file not found: {config_path}")
        config = ProjectPulseConfig.load(config_path)
    scanner = FilesystemScanner(config.data)
    detector = MeaningfulChangeDetector(config.data)

    if args.command == "public-audit":
        findings = run_public_audit(Path.cwd(), config)
        print(render_audit_report(findings))
        return 1 if findings else 0

    session = scanner.scan(watched_root=args.root)
    decision = detector.evaluate(session)

    if args.json:
        print(
            render_json_report(
                session,
                decision,
                config.data.maximum_reported_files,
                expose_absolute=config.data.expose_absolute_paths_in_reports,
            )
        )
    else:
        print(
            render_text_report(
                session,
                decision,
                config.data.maximum_reported_files,
                expose_absolute=config.data.expose_absolute_paths_in_reports,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
