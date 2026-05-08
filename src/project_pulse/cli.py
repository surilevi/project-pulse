from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import ProjectPulseConfig
from .audit import render_audit_report, run_public_audit
from .policy import MeaningfulChangeDetector
from .reporting import render_json_report, render_text_report
from .scanner import FilesystemScanner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="project-pulse",
        description="Scan real local work and turn it into an explainable publishing decision.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional path to a Project Pulse TOML config file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    scan_parser = subparsers.add_parser("scan", help="Scan the watched root and print a report.")
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
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.config is None:
        config = ProjectPulseConfig.load_default(Path.cwd())
    else:
        config_path = args.config.resolve()
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
