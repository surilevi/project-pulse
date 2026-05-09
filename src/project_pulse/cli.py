from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .audit import render_audit_report, run_public_audit
from .config import ProjectPulseConfig
from .policy import MeaningfulChangeDetector
from .publisher import PrivatePublisherError, PrivateRepoPublisher
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
    publish_parser = subparsers.add_parser(
        "publish-private",
        help="Mirror one workspace into a separate local clone of a private repo.",
        parents=[config_parent],
    )
    publish_parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Workspace path inside watched_root to mirror into the private repo clone.",
    )
    publish_parser.add_argument(
        "--message",
        type=str,
        default=None,
        help="Optional commit message override for the private mirror commit.",
    )
    publish_parser.add_argument(
        "--branch",
        type=str,
        default=None,
        help="Optional branch to switch/create in the target private repo clone.",
    )
    publish_parser.add_argument(
        "--push",
        action="store_true",
        help=(
            "Push after committing. This stays opt-in unless config explicitly "
            "enables auto-push."
        ),
    )
    publish_parser.add_argument(
        "--force",
        action="store_true",
        help="Allow publishing even when the workspace does not meet the current publish policy.",
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

    if args.command == "publish-private":
        workspace_root = args.workspace.resolve()
        session = scanner.scan(watched_root=workspace_root)
        decision = detector.evaluate(session)
        publisher = PrivateRepoPublisher(config)
        try:
            result = publisher.publish(
                workspace_root,
                session,
                decision,
                push=args.push,
                branch=args.branch,
                message=args.message,
                force=args.force,
            )
        except PrivatePublisherError as error:
            parser.exit(1, f"project-pulse publish-private: {error}\n")

        print(f"Workspace: {result.workspace_root}")
        print(f"Target repo: {result.target_repo_path}")
        print(f"Mirror path: {result.mirror_path}")
        print(f"Branch: {result.branch}")
        print(f"Metadata: {result.metadata_path}")
        print(f"Changed files: {len(result.changed_files)}")
        if result.commit_created:
            print(f"Commit: {result.commit_sha}")
            print(f"Message: {result.commit_message}")
            print(f"Pushed: {'yes' if result.pushed else 'no'}")
        else:
            print("No publish commit was needed.")
        return 0

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
