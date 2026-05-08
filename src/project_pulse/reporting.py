from __future__ import annotations

import json
from pathlib import Path

from .models import PublishDecision, WorkSession


def _display_path(path: Path, root: Path, expose_absolute: bool) -> str:
    if expose_absolute:
        return str(path)
    try:
        relative_path = path.relative_to(root)
    except ValueError:
        return path.name
    if str(relative_path) == ".":
        return "."
    return str(relative_path)


def render_text_report(
    session: WorkSession,
    decision: PublishDecision,
    max_files: int,
    expose_absolute: bool = False,
) -> str:
    root_label = session.watched_root.name or str(session.watched_root)
    lines: list[str] = []
    lines.append("Project Pulse Scan")
    lines.append(f"Watched root: {root_label}")
    lines.append(f"Observed at: {session.observed_at.isoformat()}")
    lines.append(f"Lookback window: {session.lookback_window}")
    lines.append(f"Publishable: {'yes' if decision.publishable else 'no'}")
    lines.append(f"Activity score: {decision.score}")
    lines.append("")

    lines.append("Metrics")
    for key, value in decision.metrics.items():
        lines.append(f"- {key}: {value}")

    if decision.reasons:
        lines.append("")
        lines.append("Reasons")
        for reason in decision.reasons:
            lines.append(f"- {reason}")

    if decision.blockers:
        lines.append("")
        lines.append("Blockers")
        for blocker in decision.blockers:
            lines.append(f"- {blocker}")

    if session.workspaces:
        lines.append("")
        lines.append("Workspaces")
        for workspace in session.workspaces:
            if workspace.recent_file_count == 0:
                continue
            marker_text = ",".join(workspace.marker_names) if workspace.marker_names else "none"
            repo_label = (
                _display_path(
                    workspace.repository_root,
                    session.watched_root,
                    expose_absolute,
                )
                if workspace.repository_root
                else "none"
            )
            lines.append(
                "- "
                f"{_display_path(workspace.root, session.watched_root, expose_absolute)} "
                f"| recent_files={workspace.recent_file_count} "
                f"markers={marker_text} repo={repo_label}"
            )

    if session.repositories:
        lines.append("")
        lines.append("Repositories")
        for repo in session.repositories:
            if (
                repo.recent_file_count == 0
                and not repo.has_uncommitted_changes
                and not repo.has_recent_commit
            ):
                continue
            lines.append(
                "- "
                f"{_display_path(repo.root, session.watched_root, expose_absolute)} "
                f"| recent_files={repo.recent_file_count} "
                f"tracked={repo.tracked_change_count} untracked={repo.untracked_change_count} "
                f"last_commit={repo.last_commit_at.isoformat() if repo.last_commit_at else 'none'}"
            )
            if repo.last_commit_subject:
                lines.append(f"  subject: {repo.last_commit_subject}")

    if session.recent_files:
        lines.append("")
        lines.append("Recent files")
        for item in session.recent_files[:max_files]:
            repo_label = (
                _display_path(
                    item.repository_root,
                    session.watched_root,
                    expose_absolute,
                )
                if item.repository_root
                else "none"
            )
            lines.append(
                "- "
                f"{_display_path(item.path, session.watched_root, expose_absolute)} "
                f"| modified_at={item.modified_at.isoformat()} "
                f"repo={repo_label}"
            )

    return "\n".join(lines)


def render_json_report(
    session: WorkSession,
    decision: PublishDecision,
    max_files: int,
    expose_absolute: bool = False,
) -> str:
    payload = {
        "session": {
            "watched_root": session.watched_root.name or str(session.watched_root),
            "observed_at": session.observed_at.isoformat(),
            "lookback_window_seconds": int(session.lookback_window.total_seconds()),
            "recent_file_count": session.recent_file_count,
            "recent_code_file_count": session.recent_code_file_count,
            "session_started_at": session.session_started_at.isoformat()
            if session.session_started_at
            else None,
            "latest_activity_at": session.latest_activity_at.isoformat()
            if session.latest_activity_at
            else None,
            "workspaces": [
                {
                    "root": _display_path(workspace.root, session.watched_root, expose_absolute),
                    "marker_names": list(workspace.marker_names),
                    "repository_root": _display_path(
                        workspace.repository_root,
                        session.watched_root,
                        expose_absolute,
                    )
                    if workspace.repository_root
                    else None,
                    "recent_file_count": workspace.recent_file_count,
                }
                for workspace in session.workspaces
            ],
            "repositories": [
                {
                    "root": _display_path(repo.root, session.watched_root, expose_absolute),
                    "tracked_change_count": repo.tracked_change_count,
                    "untracked_change_count": repo.untracked_change_count,
                    "recent_file_count": repo.recent_file_count,
                    "last_commit_at": repo.last_commit_at.isoformat()
                    if repo.last_commit_at
                    else None,
                    "last_commit_subject": repo.last_commit_subject,
                }
                for repo in session.repositories
            ],
            "recent_files": [
                {
                    "path": _display_path(item.path, session.watched_root, expose_absolute),
                    "modified_at": item.modified_at.isoformat(),
                    "extension": item.extension,
                    "repository_root": _display_path(
                        item.repository_root,
                        session.watched_root,
                        expose_absolute,
                    )
                    if item.repository_root
                    else None,
                }
                for item in session.recent_files[:max_files]
            ],
        },
        "decision": decision.to_dict(),
    }
    return json.dumps(payload, indent=2)
