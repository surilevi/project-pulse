from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from project_pulse.codex_integration import CodexWatcher
from project_pulse.config import ProjectPulseConfig
from project_pulse.models import (
    PersistedSession,
    PublishDecision,
    SessionRecordResult,
    WorkSession,
)


def _build_config(tmp_path: Path, *, codex_workspace: str = "") -> ProjectPulseConfig:
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
[codex_integration]
enabled = true
workspace = "{codex_workspace}"
process_names = ["Codex.exe"]
poll_seconds = 1
state_path = "{(tmp_path / '.project-pulse-state' / 'codex-state.json').as_posix()}"
""".strip()
    )


class _FakeScanner:
    def __init__(self, session: WorkSession) -> None:
        self.session = session
        self.calls: list[Path] = []

    def scan(self, watched_root: Path | None = None) -> WorkSession:
        self.calls.append((watched_root or self.session.watched_root).resolve())
        return self.session


class _FakeDetector:
    def __init__(self, decision: PublishDecision) -> None:
        self.decision = decision

    def evaluate(self, session: WorkSession) -> PublishDecision:
        return self.decision


class _FakeTracker:
    def __init__(self, result: SessionRecordResult) -> None:
        self.result = result
        self.calls: list[Path] = []

    def record(
        self,
        workspace_root: Path,
        session: WorkSession,
        decision: PublishDecision,
    ) -> SessionRecordResult:
        self.calls.append(workspace_root.resolve())
        return self.result


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


def _build_record_result(workspace_root: Path, store_path: Path) -> SessionRecordResult:
    observed_at = datetime.now(UTC)
    return SessionRecordResult(
        session=PersistedSession(
            session_id="codex-session",
            workspace_root=Path("."),
            workspace_name=workspace_root.name,
            started_at=observed_at,
            updated_at=observed_at,
            latest_activity_at=observed_at,
            last_observed_at=observed_at,
            record_count=1,
            recent_file_count=3,
            recent_code_file_count=2,
            workspaces_with_activity=1,
            repositories_with_uncommitted_changes=0,
            repositories_with_recent_commits=0,
            activity_score=12,
            publishable=True,
        ),
        created=True,
        store_path=store_path,
    )


def test_codex_workspace_resolves_relative_to_watched_root(tmp_path: Path) -> None:
    workspace_root = tmp_path / "nested" / "workspace"
    workspace_root.mkdir(parents=True)
    config = _build_config(tmp_path, codex_workspace="nested/workspace")

    assert config.data.codex_integration.workspace == workspace_root.resolve()


def test_codex_watcher_records_only_on_open_transition(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    config = _build_config(tmp_path, codex_workspace="workspace")
    observed_at = datetime.now(UTC)
    session = _build_session(workspace_root, observed_at)
    decision = PublishDecision(
        publishable=True,
        score=12,
        metrics={
            "repositories_with_uncommitted_changes": 0,
            "repositories_with_recent_commits": 0,
        },
    )
    scanner = _FakeScanner(session)
    tracker = _FakeTracker(
        _build_record_result(
            workspace_root,
            config.data.session_persistence.store_path,
        )
    )
    watcher = CodexWatcher(
        config,
        scanner=scanner,
        detector=_FakeDetector(decision),
        tracker=tracker,
    )

    assert watcher.observe(False) is False
    assert watcher.observe(True) is True
    assert watcher.observe(True) is False
    assert watcher.observe(False) is False
    assert watcher.observe(True) is True
    assert scanner.calls == [workspace_root.resolve(), workspace_root.resolve()]
    assert tracker.calls == [workspace_root.resolve(), workspace_root.resolve()]


def test_codex_record_open_defaults_to_watched_root(tmp_path: Path) -> None:
    config = _build_config(tmp_path)
    session = _build_session(tmp_path.resolve(), datetime.now(UTC))
    decision = PublishDecision(
        publishable=True,
        score=12,
        metrics={
            "repositories_with_uncommitted_changes": 0,
            "repositories_with_recent_commits": 0,
        },
    )
    scanner = _FakeScanner(session)
    tracker = _FakeTracker(
        _build_record_result(
            tmp_path.resolve(),
            config.data.session_persistence.store_path,
        )
    )
    watcher = CodexWatcher(
        config,
        scanner=scanner,
        detector=_FakeDetector(decision),
        tracker=tracker,
    )

    watcher.record_open()

    assert scanner.calls == [tmp_path.resolve()]
    assert tracker.calls == [tmp_path.resolve()]
