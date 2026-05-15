from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .audit import render_audit_report, run_safety_audit
from .codex_integration import CodexIntegrationError, CodexWatcher
from .config import ProjectPulseConfig
from .models import SessionRecordResult
from .policy import MeaningfulChangeDetector
from .publisher import PrivatePublisherError, PrivateRepoPublisher
from .reporting import render_json_report, render_text_report
from .scanner import FilesystemScanner
from .session_tracker import SessionTracker, SessionTrackerError


def _display_path(path: Path, root: Path) -> str:
    try:
        relative_path = path.resolve().relative_to(root.resolve())
    except ValueError:
        return str(path)
    if str(relative_path) == ".":
        return "."
    return str(relative_path)


def _print_session_record(result: SessionRecordResult) -> None:
    print(f"Workspace: {result.session.workspace_root}")
    print(f"Session id: {result.session.session_id}")
    print(f"Store: {_display_path(result.store_path, Path.cwd())}")
    print(f"Created: {'yes' if result.created else 'no'}")
    print(f"Started: {result.session.started_at.isoformat()}")
    print(f"Updated: {result.session.updated_at.isoformat()}")
    print(f"Records: {result.session.record_count}")
    print(f"Activity score: {result.session.activity_score}")
    print(f"Publishable: {'yes' if result.session.publishable else 'no'}")


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
    safety_audit_parser = subparsers.add_parser(
        "safety-audit",
        help="Scan the repository for obvious path, config, and secret-safety issues.",
        parents=[config_parent],
    )
    safety_audit_parser.set_defaults(command="safety-audit")
    legacy_audit_parser = subparsers.add_parser(
        "public-audit",
        help="Compatibility alias for safety-audit.",
        parents=[config_parent],
    )
    legacy_audit_parser.set_defaults(command="safety-audit")
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
    session_record_parser = subparsers.add_parser(
        "session-record",
        help="Persist one workspace scan into the local session store.",
        parents=[config_parent],
    )
    session_record_parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Workspace path inside watched_root to record into the local session store.",
    )
    session_list_parser = subparsers.add_parser(
        "session-list",
        help="List persisted sessions from the local session store.",
        parents=[config_parent],
    )
    session_list_parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Optional workspace path to filter persisted sessions.",
    )
    subparsers.add_parser(
        "codex-record-open",
        help="Record one local session using the configured Codex integration workspace.",
        parents=[config_parent],
    )
    codex_watch_parser = subparsers.add_parser(
        "codex-watch",
        help="Watch for the Codex desktop app and auto-record sessions on app open.",
        parents=[config_parent],
    )
    codex_watch_parser.add_argument(
        "--max-polls",
        type=int,
        default=None,
        help="Optional number of polling loops before the watcher exits.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config_arg = getattr(args, "config", None)
    if config_arg is None:
        try:
            if args.command == "safety-audit":
                config = ProjectPulseConfig.load_safety_audit_default(Path.cwd())
            else:
                config = ProjectPulseConfig.load_default(Path.cwd())
        except ValueError as error:
            parser.exit(2, f"project-pulse: invalid config: {error}\n")
    else:
        config_path = config_arg.resolve()
        if not config_path.exists():
            parser.error(f"Config file not found: {config_path}")
        try:
            config = ProjectPulseConfig.load(config_path)
        except ValueError as error:
            parser.exit(2, f"project-pulse: invalid config: {error}\n")
    scanner = FilesystemScanner(config.data)
    detector = MeaningfulChangeDetector(config.data)

    if args.command == "safety-audit":
        findings = run_safety_audit(Path.cwd(), config)
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

    if args.command == "session-record":
        workspace_root = args.workspace.resolve()
        session = scanner.scan(watched_root=workspace_root)
        decision = detector.evaluate(session)
        tracker = SessionTracker(config)
        try:
            result = tracker.record(workspace_root, session, decision)
        except SessionTrackerError as error:
            parser.exit(1, f"project-pulse session-record: {error}\n")

        _print_session_record(result)
        return 0

    if args.command == "session-list":
        tracker = SessionTracker(config)
        workspace_root = args.workspace.resolve() if args.workspace else None
        try:
            sessions = tracker.list_sessions(workspace_root)
        except SessionTrackerError as error:
            parser.exit(1, f"project-pulse session-list: {error}\n")

        if not sessions:
            print("No persisted sessions found.")
            return 0

        for item in sessions:
            print(
                f"{item.session_id} | {item.workspace_name} | "
                f"updated={item.updated_at.isoformat()} | "
                f"records={item.record_count} | score={item.activity_score} | "
                f"publishable={'yes' if item.publishable else 'no'}"
            )
        return 0

    if args.command == "codex-record-open":
        watcher = CodexWatcher(config)
        try:
            result = watcher.record_open()
        except (CodexIntegrationError, SessionTrackerError) as error:
            parser.exit(1, f"project-pulse codex-record-open: {error}\n")

        _print_session_record(result)
        return 0

    if args.command == "codex-watch":
        watcher = CodexWatcher(config)
        try:
            watcher.watch(max_polls=args.max_polls)
        except (CodexIntegrationError, SessionTrackerError) as error:
            parser.exit(1, f"project-pulse codex-watch: {error}\n")
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
