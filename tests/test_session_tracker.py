from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from project_pulse.config import ProjectPulseConfig
from project_pulse.models import PublishDecision, WorkSession
from project_pulse.session_tracker import SessionTracker, SessionTrackerError


def _build_config(tmp_path: Path) -> ProjectPulseConfig:
    return ProjectPulseConfig.from_text(
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
enabled = false
target_repo_path = ""
mirror_subdirectory = "workspace"
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


def _build_session(workspace_root: Path, observed_at: datetime) -> WorkSession:
    return WorkSession(
        watched_root=workspace_root,
        observed_at=observed_at,
        lookback_window=timedelta(hours=24),
        recent_files=[],
        workspaces=[],
        repositories=[],
        recent_code_file_count=2,
        latest_activity_at=observed_at,
        session_started_at=observed_at,
    )


def test_session_record_continues_within_gap(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    config = _build_config(tmp_path)
    tracker = SessionTracker(config)
    first_time = datetime.now(UTC)
    decision = PublishDecision(
        publishable=True,
        score=10,
        metrics={
            "repositories_with_uncommitted_changes": 0,
            "repositories_with_recent_commits": 0,
        },
    )

    first = tracker.record(workspace_root, _build_session(workspace_root, first_time), decision)
    second = tracker.record(
        workspace_root,
        _build_session(workspace_root, first_time + timedelta(minutes=30)),
        decision,
    )

    assert first.created is True
    assert second.created is False
    assert second.session.session_id == first.session.session_id
    assert second.session.record_count == 2


def test_session_record_creates_new_session_after_gap(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    config = _build_config(tmp_path)
    tracker = SessionTracker(config)
    first_time = datetime.now(UTC)
    decision = PublishDecision(
        publishable=True,
        score=10,
        metrics={
            "repositories_with_uncommitted_changes": 0,
            "repositories_with_recent_commits": 0,
        },
    )

    first = tracker.record(workspace_root, _build_session(workspace_root, first_time), decision)
    second = tracker.record(
        workspace_root,
        _build_session(workspace_root, first_time + timedelta(minutes=120)),
        decision,
    )

    assert first.created is True
    assert second.created is True
    assert second.session.session_id != first.session.session_id


def test_session_record_uses_activity_gap_not_scan_gap(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    config = _build_config(tmp_path)
    tracker = SessionTracker(config)
    decision = PublishDecision(
        publishable=True,
        score=10,
        metrics={
            "repositories_with_uncommitted_changes": 0,
            "repositories_with_recent_commits": 0,
        },
    )
    first_observed = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
    second_observed = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    first_session = WorkSession(
        watched_root=workspace_root,
        observed_at=first_observed,
        lookback_window=timedelta(hours=24),
        recent_files=[],
        workspaces=[],
        repositories=[],
        recent_code_file_count=2,
        latest_activity_at=datetime(2026, 1, 1, 9, 50, tzinfo=UTC),
        session_started_at=datetime(2026, 1, 1, 9, 50, tzinfo=UTC),
    )
    second_session = WorkSession(
        watched_root=workspace_root,
        observed_at=second_observed,
        lookback_window=timedelta(hours=24),
        recent_files=[],
        workspaces=[],
        repositories=[],
        recent_code_file_count=2,
        latest_activity_at=datetime(2026, 1, 1, 11, 55, tzinfo=UTC),
        session_started_at=datetime(2026, 1, 1, 10, 55, tzinfo=UTC),
    )

    first = tracker.record(workspace_root, first_session, decision)
    second = tracker.record(workspace_root, second_session, decision)

    assert first.created is True
    assert second.created is False
    assert second.session.session_id == first.session.session_id


def test_session_tracker_rejects_invalid_store_schema(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    config = _build_config(tmp_path)
    store_path = config.data.session_persistence.store_path
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text("[]", encoding="utf-8")
    tracker = SessionTracker(config)
    decision = PublishDecision(
        publishable=True,
        score=10,
        metrics={
            "repositories_with_uncommitted_changes": 0,
            "repositories_with_recent_commits": 0,
        },
    )

    try:
        tracker.record(workspace_root, _build_session(workspace_root, datetime.now(UTC)), decision)
    except SessionTrackerError:
        pass
    else:
        raise AssertionError("expected SessionTrackerError for invalid session store schema")
