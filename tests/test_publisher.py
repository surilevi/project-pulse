from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from project_pulse.config import ProjectPulseConfig
from project_pulse.models import PublishDecision, WorkSession
from project_pulse.publisher import PrivatePublisherError, PrivateRepoPublisher


def test_private_publisher_syncs_workspace_into_target_repo(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (workspace_root / "demo.py").write_text("print('hello')\n", encoding="utf-8")

    target_repo = tmp_path / "private-repo"
    subprocess.run(["git", "init", "-b", "main", str(target_repo)], check=True)
    subprocess.run(
        ["git", "-C", str(target_repo), "config", "user.name", "Mirror Bot"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(target_repo), "config", "user.email", "mirror@example.com"],
        check=True,
    )
    (target_repo / "README.md").write_text("private mirror\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(target_repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(target_repo), "commit", "-m", "init"], check=True)

    config = ProjectPulseConfig.from_text(
        f"""
watched_root = "{tmp_path.as_posix()}"
lookback_window_hours = 24
minimum_recent_files = 4
minimum_recent_code_files = 2
minimum_workspaces_with_activity = 1
minimum_activity_score = 12
maximum_reported_files = 12
require_git_signal = false
expose_absolute_paths_in_reports = false
high_signal_extensions = [".py"]
ignored_directory_names = [".git", "__pycache__"]
low_signal_directory_names = []
ignored_file_names = []
project_marker_names = ["pyproject.toml"]
[weights]
recent_file = 1
recent_code_file = 3
repository_with_uncommitted_changes = 4
repository_with_recent_commit = 5
[publisher]
enabled = true
target_repo_path = "{target_repo.as_posix()}"
mirror_subdirectory = "workspace"
commit_message_prefix = "pulse"
push_after_commit = false
require_explicit_push = true
exclude_globs = []
""".strip()
    )
    session = WorkSession(
        watched_root=workspace_root,
        observed_at=datetime.now(UTC),
        lookback_window=config.data.lookback_window,
        recent_files=[],
        workspaces=[],
        repositories=[],
        recent_code_file_count=0,
        latest_activity_at=None,
        session_started_at=None,
    )
    decision = PublishDecision(publishable=True, score=10)

    result = PrivateRepoPublisher(config).publish(
        workspace_root,
        session,
        decision,
        force=True,
    )

    assert result.commit_created is True
    mirrored_file = target_repo / "workspace" / "demo.py"
    assert mirrored_file.read_text(encoding="utf-8") == "print('hello')\n"
    assert result.metadata_path.exists()


def test_private_publisher_rejects_parent_escaping_mirror_path(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (workspace_root / "demo.py").write_text("print('hello')\n", encoding="utf-8")

    target_repo = tmp_path / "private-repo"
    subprocess.run(["git", "init", "-b", "main", str(target_repo)], check=True)
    subprocess.run(
        ["git", "-C", str(target_repo), "config", "user.name", "Mirror Bot"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(target_repo), "config", "user.email", "mirror@example.com"],
        check=True,
    )
    (target_repo / "README.md").write_text("private mirror\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(target_repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(target_repo), "commit", "-m", "init"], check=True)

    config = ProjectPulseConfig.from_text(
        f"""
watched_root = "{tmp_path.as_posix()}"
lookback_window_hours = 24
minimum_recent_files = 4
minimum_recent_code_files = 2
minimum_workspaces_with_activity = 1
minimum_activity_score = 12
maximum_reported_files = 12
require_git_signal = false
expose_absolute_paths_in_reports = false
high_signal_extensions = [".py"]
ignored_directory_names = [".git", "__pycache__", ".pytest_cache", ".ruff_cache"]
low_signal_directory_names = []
ignored_file_names = []
project_marker_names = ["pyproject.toml"]
[weights]
recent_file = 1
recent_code_file = 3
repository_with_uncommitted_changes = 4
repository_with_recent_commit = 5
[publisher]
enabled = true
target_repo_path = "{target_repo.as_posix()}"
mirror_subdirectory = "../escape"
commit_message_prefix = "pulse"
push_after_commit = false
require_explicit_push = true
exclude_globs = []
[session_persistence]
enabled = true
store_path = "{(tmp_path / '.project-pulse-state' / 'sessions.json').as_posix()}"
session_gap_minutes = 90
max_sessions_per_workspace = 25
""".strip()
    )
    session = WorkSession(
        watched_root=workspace_root,
        observed_at=datetime.now(UTC),
        lookback_window=config.data.lookback_window,
        recent_files=[],
        workspaces=[],
        repositories=[],
        recent_code_file_count=0,
        latest_activity_at=None,
        session_started_at=None,
    )
    decision = PublishDecision(publishable=True, score=10)

    try:
        PrivateRepoPublisher(config).publish(
            workspace_root,
            session,
            decision,
            force=True,
        )
    except PrivatePublisherError:
        pass
    else:
        raise AssertionError("expected PrivatePublisherError for escaping mirror_subdirectory")


def test_private_publisher_excludes_nested_env_variants(tmp_path: Path) -> None:
    config = ProjectPulseConfig.from_text(
        f"""
watched_root = "{tmp_path.as_posix()}"
lookback_window_hours = 24
minimum_recent_files = 4
minimum_recent_code_files = 2
minimum_workspaces_with_activity = 1
minimum_activity_score = 12
maximum_reported_files = 12
require_git_signal = false
expose_absolute_paths_in_reports = false
high_signal_extensions = [".py"]
ignored_directory_names = [".git", "__pycache__"]
low_signal_directory_names = []
ignored_file_names = ["project-pulse.local.toml"]
project_marker_names = ["pyproject.toml"]
[weights]
recent_file = 1
recent_code_file = 3
repository_with_uncommitted_changes = 4
repository_with_recent_commit = 5
[publisher]
enabled = true
target_repo_path = "{(tmp_path / 'target').as_posix()}"
mirror_subdirectory = "workspace"
commit_message_prefix = "pulse"
push_after_commit = false
require_explicit_push = true
exclude_globs = [".env", ".env.*", "project-pulse.local.toml"]
""".strip()
    )

    publisher = PrivateRepoPublisher(config)

    assert publisher._matches_exclude(Path("nested/.env.local"))
    assert publisher._matches_exclude(Path("nested/.env"))
    assert publisher._matches_exclude(Path("nested/project-pulse.local.toml"))
